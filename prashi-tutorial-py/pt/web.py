"""Shared web plumbing: server-side sessions, CSRF, rate limits, access control and small helpers."""
import json
import os
import re
import secrets
import time
from collections.abc import MutableMapping
from functools import wraps
from urllib.parse import quote, urlsplit

from flask import g, jsonify, redirect, render_template, request, session
from flask.sessions import SessionInterface, SessionMixin

from . import db
from .db import all_, one, run

PROD = os.environ.get('NODE_ENV') == 'production' or os.environ.get('APP_ENV') == 'production'
SESSION_COOKIE = 'pt_sid'
CSRF_COOKIE = 'pt_csrf'
SESSION_SECONDS = 8 * 60 * 60                        # signed out after 8 idle hours


def site_url():
    return (os.environ.get('SITE_URL') or 'http://localhost:3000').rstrip('/')


# ───────────────────────── Sessions ─────────────────────────
# Kept in the same SQLite database. The "uid" column lets us log a user out everywhere
# (for example after a password reset or when an account is switched off).
class DbSession(SessionMixin, MutableMapping):
    """Loaded from the database the first time it is touched (static files and /healthz never touch it)."""

    def __init__(self, sid):
        self.sid, self._data, self.loaded = sid, None, False
        self.is_new = sid is None
        self.destroyed = False
        self.drop_sid = None                          # an old id to delete (after regenerate)

    def _load(self):
        if self._data is None:
            self._data = {}
            if self.sid:
                r = one('SELECT sess, expires FROM sessions WHERE sid = ?', self.sid)
                if r and r['expires'] >= int(time.time() * 1000):
                    try:
                        self._data = json.loads(r['sess'])
                    except ValueError:
                        self._data = {}
                else:
                    self.sid, self.is_new = None, True
        return self._data

    @property
    def touched(self):
        return self._data is not None

    def __getitem__(self, k): return self._load()[k]
    def __setitem__(self, k, v): self._load()[k] = v; self.modified = True
    def __delitem__(self, k): del self._load()[k]; self.modified = True
    def __iter__(self): return iter(self._load())
    def __len__(self): return len(self._load())

    def regenerate(self):
        """New session id (stops 'session fixation' attacks). Keeps nothing from the old session."""
        self._load()
        if self.sid:
            self.drop_sid = self.sid
        self.sid, self.is_new, self._data, self.modified = None, True, {}, True

    def destroy(self):
        self._load()
        self.destroyed = True
        self._data = {}


class DbSessionInterface(SessionInterface):
    def open_session(self, app, req):
        sid = req.cookies.get(SESSION_COOKIE)
        return DbSession(sid if sid and re.fullmatch(r'[A-Za-z0-9_\-]{20,80}', sid) else None)

    def save_session(self, app, sess, response):
        if not sess.touched:
            return
        if sess.destroyed:
            if sess.sid:
                run('DELETE FROM sessions WHERE sid = ?', sess.sid)
            response.delete_cookie(SESSION_COOKIE, path='/')
            return
        if sess.drop_sid:
            run('DELETE FROM sessions WHERE sid = ?', sess.drop_sid)
        data = dict(sess._data)
        if sess.is_new and not data:
            return                                    # an empty brand-new session is never stored
        if not sess.sid:
            sess.sid = secrets.token_urlsafe(32)
        expires = int((time.time() + SESSION_SECONDS) * 1000)
        uid = (data.get('user') or {}).get('id')
        run('INSERT OR REPLACE INTO sessions (sid, sess, expires, uid) VALUES (?,?,?,?)', sess.sid, json.dumps(data), expires, uid)
        response.set_cookie(SESSION_COOKIE, sess.sid, max_age=SESSION_SECONDS, httponly=True, samesite='Lax', secure=PROD, path='/')


def destroy_user_sessions(uid):
    run('DELETE FROM sessions WHERE uid = ?', uid)


def purge_expired_sessions():
    run('DELETE FROM sessions WHERE expires < ?', int(time.time() * 1000))


# ───────────────────────── Request helpers ─────────────────────────
class Body(dict):
    """The submitted data: JSON, or a normal form. Repeated fields are available with getlist()."""

    def __init__(self, data=None, lists=None):
        super().__init__(data or {})
        self._lists = lists or {}

    def getlist(self, k):
        if k in self._lists:
            return self._lists[k]
        v = self.get(k)
        return [] if v is None else (v if isinstance(v, list) else [v])


def body():
    if hasattr(g, '_body'):
        return g._body
    b = Body()
    mt = request.mimetype
    if mt == 'application/json':
        j = request.get_json(silent=True)
        b = Body(j if isinstance(j, dict) else {})
    elif mt in ('application/x-www-form-urlencoded', 'multipart/form-data'):
        try:
            f = request.form
            b = Body({k: f.get(k) for k in f}, {k: f.getlist(k) for k in f})
        except Exception:                             # noqa: BLE001  (too large / malformed: treated as empty)
            b = Body()
    g._body = b
    return b


def flash(kind, msg):
    session['flash'] = {'type': kind, 'msg': msg}


def render(view, data=None, status=200, **extra):
    """Renders templates/<view>.html. `data` may be a dict; extra keyword arguments are added to it."""
    ctx = {**(data or {}), **extra}
    return render_template(view + '.html', **ctx), status


def wants_json():
    accept = request.headers.get('Accept', '')
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or ('application/json' in accept and 'text/html' not in accept)


def js_quote(s):
    """encodeURIComponent"""
    return quote(s, safe="!~*'()")


def back_url(fallback):
    """Where to send the user after a button on a list page: the page they came from, only if it is on this same site."""
    ref = request.headers.get('Referer')
    if ref:
        try:
            u = urlsplit(ref)
            if u.netloc == request.host:
                return u.path + ('?' + u.query if u.query else '')
        except ValueError:
            pass
    return fallback


def home_for(role):
    return '/portal' if role == 'student' else '/admin'


# ───────────────────────── Access control ─────────────────────────
def to_login():
    if wants_json():
        return jsonify(ok=False, message='Please sign in again.'), 401
    nxt = ''
    if request.method == 'GET':
        full = request.path + ('?' + request.query_string.decode() if request.query_string else '')
        nxt = '?next=' + js_quote(full)
    return redirect('/login' + nxt)


def denied():
    if wants_json():
        return jsonify(ok=False, message='Access denied.'), 403
    from .status_pages import status_page
    return status_page(403)


def check_role(*roles):
    """Returns a response to stop the request, or None to let it through."""
    u = g.user
    if not u:
        return to_login()
    if u['role'] not in roles:
        return denied()
    if u['must_change_password'] and request.path != '/account/password':
        return redirect('/account/password')
    return None


def require_role(*roles):
    def deco(fn):
        @wraps(fn)
        def inner(*a, **kw):
            r = check_role(*roles)
            return r if r is not None else fn(*a, **kw)
        return inner
    return deco


admin_only = require_role('admin')


def load_user():
    """Runs on every request: turns the session into a fresh, current user record.
    Re-reading from the database means a switched-off account loses access immediately."""
    g.user, g.flash = None, None
    s = session.get('user')
    if s:
        u = one('SELECT u.id, u.role, u.name, u.email, u.username, u.active, u.must_change_password, s.photo '
                'FROM users u LEFT JOIN students s ON s.user_id = u.id WHERE u.id = ?', s['id'])
        if u and u['active']:
            g.user = u
        else:
            session.pop('user', None)
    f = session.get('flash')
    if f:
        g.flash = f
        session.pop('flash', None)


# ───────────────────────── Rate limits (per process, in memory) ─────────────────────────
class Limiter:
    """Fixed-window limiter, like express-rate-limit: `limit` requests per `window` seconds per key."""

    def __init__(self, window_seconds, limit):
        self.window, self.limit, self.hits = window_seconds, limit, {}

    def hit(self, key):
        """Counts a request. Returns True if it is allowed."""
        now = time.time()
        n, reset = self.hits.get(key, (0, 0))
        if now >= reset:
            n, reset = 0, now + self.window
        n += 1
        self.hits[key] = (n, reset)
        if len(self.hits) > 5000:
            self.hits = {k: v for k, v in self.hits.items() if v[1] > now}
        return n <= self.limit

    def refund(self, key):
        if key in self.hits:
            n, reset = self.hits[key]
            self.hits[key] = (max(0, n - 1), reset)


def client_ip():
    return request.remote_addr or ''


# ───────────────────────── CSRF (double-submit cookie) ─────────────────────────
# A random token is set in a cookie and also placed in the page. Every POST must send the same value in the
# "x-csrf-token" header, a "_csrf" form field, or a "_csrf" query value (file-upload forms). A site on another
# domain can't read our page, so it can't copy the token.
CSRF_MSG = ('This page was open too long, or the website was updated. Nothing was saved. Please refresh the page '
            '(or press Back, then reload) and try again.')


def csrf_check():
    token = request.cookies.get(CSRF_COOKIE)
    g.csrf_new = False
    if not token or not re.fullmatch(r'[a-f0-9]{64}', token):
        token = secrets.token_hex(32)
        g.csrf_new = True
    g.csrf_token = token
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return None
    sent = request.headers.get('x-csrf-token') or ''
    if not sent:
        mt = request.mimetype
        if mt == 'application/json':
            j = request.get_json(silent=True)
            sent = str((j or {}).get('_csrf', '')) if isinstance(j, dict) else ''
        elif mt == 'application/x-www-form-urlencoded':
            sent = request.form.get('_csrf', '')
    sent = sent or request.args.get('_csrf', '')
    if not secrets.compare_digest(sent.encode(), token.encode()):
        if request.headers.get('x-csrf-token') or request.mimetype == 'application/json':
            return jsonify(ok=False, message=CSRF_MSG), 403
        from .status_pages import status_page
        return status_page(403, CSRF_MSG)
    return None


def js_round(x):
    """Math.round: halves round up."""
    import math
    return int(math.floor(x + 0.5))


def days_ago(days):
    """'YYYY-MM-DD' (UTC) for N days ago."""
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')


def send_private(name, inline=True):
    """Serves a file from the private folder (callers must already have checked who may see it)."""
    from flask import send_from_directory
    from .uploads import PRIVATE_DIR
    resp = send_from_directory(PRIVATE_DIR, name)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Cache-Control'] = 'private, max-age=300'
    resp.headers['Content-Disposition'] = 'inline'
    return resp


def int_in(v, lo, hi):
    """A whole number between lo and hi (like Number(v) + Number.isInteger), else None. Blank counts as 0."""
    if v is None:
        return None
    t = str(v).strip()
    try:
        n = float(t) if t else 0.0
    except ValueError:
        return None
    return int(n) if n == int(n) and lo <= n <= hi else None
