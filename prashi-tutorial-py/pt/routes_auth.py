"""Sign in, sign out, forgotten password, change password."""
import secrets

from flask import Blueprint, g, redirect, request, session

from . import pw
from .audit import audit
from .db import one, run
from .mail import send_mail
from .tz import iso_now
from .web import (Limiter, admin_only, body, client_ip, destroy_user_sessions, flash, home_for, render,  # noqa: F401
                  require_role, site_url)

bp = Blueprint('auth', __name__)
MAX_FAILS, LOCK_MINUTES = 5, 15

login_limiter = Limiter(15 * 60, 10)
reset_limiter = Limiter(15 * 60, 5)


def page(view, data=None, status=200):
    return render('auth/' + view, {'noindex': True, 'desc': '', **(data or {})}, status)


def safe_next(nxt, role):
    """Only same-site paths, and only inside the area the user's role may use."""
    if not isinstance(nxt, str) or not nxt.startswith('/') or nxt.startswith('//') or '\\' in nxt:
        return home_for(role)
    staff = role != 'student'
    if nxt.startswith('/admin') and not staff:
        return home_for(role)
    if nxt.startswith('/portal') and staff:
        return home_for(role)
    return nxt


_dummy = {}


def _dummy_hash():                                  # so "no such user" takes as long as "wrong password"
    if 'h' not in _dummy:
        _dummy['h'] = pw.hash_password('not-a-real-password')
    return _dummy['h']


# ── Sign in ──
@bp.get('/login')
def login():
    if g.user and not g.user['must_change_password']:
        return redirect(home_for(g.user['role']))
    return page('login', {'title': 'Sign in', 'next': request.args.get('next', ''), 'error': '', 'identifier': ''})


@bp.post('/login')
def login_post():
    ip = client_ip()
    if not login_limiter.hit(ip):
        return page('login', {'title': 'Sign in', 'next': '', 'error': 'Too many attempts. Please wait 15 minutes and try again.', 'identifier': ''}, 429)
    b = body()
    ident = str(b.get('identifier') or '').strip().lower()[:200]
    password = str(b.get('password') or '')[:300]

    def fail(msg):
        return page('login', {'title': 'Sign in', 'next': b.get('next') or '', 'error': msg, 'identifier': ident}, 401)

    if not ident or not password:
        return fail('Enter your email or username and your password.')
    u = one('SELECT * FROM users WHERE lower(email) = ? OR lower(username) = ?', ident, ident)
    if u and u['locked_until'] and u['locked_until'] > iso_now():
        return fail('This account is locked for a few minutes after too many wrong passwords. Try again later or ask the office to reset it.')
    if u:
        ok = pw.verify(u['password_hash'], password)
    else:
        pw.verify(_dummy_hash(), password)
        ok = False
    if not u or not u['active'] or not ok:
        if u:
            n = u['failed_logins'] + 1
            run('UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?', n,
                iso_now(LOCK_MINUTES * 60) if n >= MAX_FAILS else None, u['id'])
        audit('login_failed', 'user', u['id'] if u else None, f'Failed sign-in for "{ident}"')
        return fail('Incorrect email/username or password.')
    run("UPDATE users SET failed_logins = 0, locked_until = NULL, last_login_at = datetime('now') WHERE id = ?", u['id'])
    login_limiter.refund(ip)                        # successful sign-ins are not counted against the limit
    session.regenerate()                            # New session id on login stops "session fixation" attacks.
    session['user'] = {'id': u['id'], 'role': u['role'], 'name': u['name']}
    audit('login', 'user', u['id'], f"{u['name']} signed in")
    if u['must_change_password']:
        return redirect('/account/password')
    return redirect(safe_next(b.get('next'), u['role']))


@bp.post('/logout')
def logout():
    if g.user:
        audit('logout', 'user', g.user['id'], f"{g.user['name']} signed out")
    session.destroy()
    return redirect('/login')


# ── Forgot / reset password ──
@bp.get('/forgot')
def forgot():
    return page('forgot', {'title': 'Forgot password', 'sent': False, 'error': ''})


@bp.post('/forgot')
def forgot_post():
    if not reset_limiter.hit(client_ip()):
        return page('forgot', {'title': 'Forgot password', 'sent': False, 'error': 'Too many requests. Please wait 15 minutes.'}, 429)
    ident = str(body().get('identifier') or '').strip().lower()[:200]
    u = ident and one('SELECT u.*, s.parent_email FROM users u LEFT JOIN students s ON s.user_id = u.id '
                      'WHERE u.active = 1 AND (lower(u.email) = ? OR lower(u.username) = ?)', ident, ident)
    to = u and (u['email'] or u['parent_email'])
    if u and to:
        token = secrets.token_hex(32)
        run('DELETE FROM password_resets WHERE user_id = ?', u['id'])
        run('INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?,?,?)', u['id'], pw.sha256(token), iso_now(3600))
        audit('password_reset_requested', 'user', u['id'], f"Reset link requested for {u['name']}")
        send_mail(to, 'Reset your password',
                  f"Hello {u['name']},\n\nUse this link within 1 hour to choose a new password:\n{site_url()}/reset/{token}\n\nIf you did not ask for this, ignore this email.")
    # Same answer whether or not the account exists, so nobody can test which logins are real.
    return page('forgot', {'title': 'Forgot password', 'sent': True, 'error': ''})


def find_reset(token):
    import re
    if not re.fullmatch(r'[a-f0-9]{64}', token or ''):
        return None
    return one('SELECT * FROM password_resets WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?', pw.sha256(token), iso_now())


@bp.get('/reset/<token>')
def reset(token):
    return page('reset', {'title': 'Choose a new password', 'valid': bool(find_reset(token)), 'error': ''})


@bp.post('/reset/<token>')
def reset_post(token):
    r = find_reset(token)

    def show(error):
        return page('reset', {'title': 'Choose a new password', 'valid': bool(r), 'error': error})

    if not r:
        return show('')
    b = body()
    p = str(b.get('password') or '')
    if p != str(b.get('confirm') or ''):
        return show('The two passwords do not match.')
    bad = pw.password_problem(p)
    if bad:
        return show(bad)
    run('UPDATE users SET password_hash = ?, must_change_password = 0, failed_logins = 0, locked_until = NULL WHERE id = ?',
        pw.hash_password(p), r['user_id'])
    run("UPDATE password_resets SET used_at = datetime('now') WHERE id = ?", r['id'])
    destroy_user_sessions(r['user_id'])
    audit('password_reset', 'user', r['user_id'], 'Password changed using a reset link', user={'id': r['user_id']})
    flash('ok', 'Password changed. Please sign in.')
    return redirect('/login')


# ── Change own password (also forced after an admin sets a temporary password) ──
anyone = require_role('admin', 'staff', 'student')


@bp.get('/account/password')
@anyone
def password():
    return page('password', {'title': 'Change password', 'error': '', 'forced': bool(g.user['must_change_password'])})


@bp.post('/account/password')
@anyone
def password_post():
    u = one('SELECT * FROM users WHERE id = ?', g.user['id'])

    def show(error):
        return page('password', {'title': 'Change password', 'error': error, 'forced': bool(u['must_change_password'])})

    b = body()
    if not pw.verify(u['password_hash'], str(b.get('current') or '')):
        return show('Your current password is not correct.')
    p = str(b.get('password') or '')
    if p != str(b.get('confirm') or ''):
        return show('The two new passwords do not match.')
    bad = pw.password_problem(p)
    if bad:
        return show(bad)
    if p == str(b.get('current')):
        return show('Choose a password different from the current one.')
    run('UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?', pw.hash_password(p), u['id'])
    destroy_user_sessions(u['id'])
    audit('password_change', 'user', u['id'], 'Changed own password')
    session.regenerate()
    session['user'] = {'id': u['id'], 'role': u['role'], 'name': u['name']}
    flash('ok', 'Password updated.')
    return redirect(home_for(u['role']))
