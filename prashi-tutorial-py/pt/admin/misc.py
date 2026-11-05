"""Dashboard, activity log, previews, image upload, staff logins and student doubts."""
import json
import math
import re
from urllib.parse import urlencode

from flask import Blueprint, abort, g, jsonify, redirect, request

from .. import content, pw
from ..audit import audit
from ..db import all_, one, run
from ..tz import today_local, utc_stamp
from ..uploads import UploadError, read_uploads, save_image
from ..web import admin_only, body, destroy_user_sessions, flash, render

bp = Blueprint('misc', __name__)


# ───── Dashboard ─────
@bp.get('/', strict_slashes=False)
def dashboard():
    today = today_local()
    since = utc_stamp(-30 * 86400)
    stats = {
        'newEnquiries': one("SELECT COUNT(*) n FROM submissions WHERE status = 'new' AND form != 'admission'")['n'],
        'newRegs': one("SELECT COUNT(*) n FROM submissions WHERE status = 'new' AND form = 'admission'")['n'],
        'regs30': one("SELECT COUNT(*) n FROM submissions WHERE form = 'admission' AND created_at >= ?", since)['n'],
        'enq30': one("SELECT COUNT(*) n FROM submissions WHERE form != 'admission' AND created_at >= ?", since)['n'],
        'students': one("SELECT COUNT(*) n FROM users WHERE role = 'student' AND active = 1")['n'],
        'batches': one("SELECT COUNT(*) n FROM batches WHERE status != 'closed' AND start_date >= ?", today)['n'],
        'doubts': one("SELECT COUNT(*) n FROM doubts WHERE status = 'open'")['n'],
    }
    upcoming = all_("""SELECT b.*, c.name AS course_name, b.seats_total - (SELECT COUNT(*) FROM enrollments e WHERE e.batch_id = b.id AND e.status='active') AS seats_left
    FROM batches b JOIN courses c ON c.id = b.course_id WHERE b.status != 'closed' AND b.start_date >= ? ORDER BY b.start_date LIMIT 5""", today)

    def who(r):
        try:
            d = json.loads(r['data_json'])
            return d.get('student_name') or d.get('name') or d.get('email') or '—'
        except (ValueError, AttributeError):
            return '—'

    recent = [{**r, 'who': who(r)} for r in all_('SELECT id, form, data_json, status, created_at FROM submissions ORDER BY id DESC LIMIT 6')]
    activity = all_('SELECT * FROM audit_log ORDER BY id DESC LIMIT 8') if g.user['role'] == 'admin' else []
    return render('admin/dashboard', {
        'title': 'Dashboard', 'nav': '/admin', 'stats': stats, 'upcoming': upcoming, 'recent': recent, 'activity': activity,
        'help': '<p>A quick look at how things are going. Click any number to open the full list.</p><ul><li><b>New enquiries / registrations</b> are people who filled a form on the website and have not been contacted yet.</li><li>Set their status in <b>Enquiries & admissions</b> as you call them.</li></ul>'})


# ───── Activity log (admin only) ─────
@bp.get('/activity')
@admin_only
def activity():
    a = request.args
    f = {'user': str(a.get('user', '')), 'entity': str(a.get('entity', '')), 'action': str(a.get('action', '')), 'q': str(a.get('q', '')).strip()[:100],
         'from': str(a.get('from', '')), 'to': str(a.get('to', ''))}
    where, args = [], []
    if f['user']:
        where.append('user_name = ?')
        args.append(f['user'])
    if f['entity']:
        where.append('entity = ?')
        args.append(f['entity'])
    if f['action']:
        where.append('action = ?')
        args.append(f['action'])
    if f['q']:
        where.append('summary LIKE ?')
        args.append('%' + f['q'] + '%')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', f['from']):
        where.append('created_at >= ?')
        args.append(f['from'])
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', f['to']):
        where.append("created_at < date(?, '+1 day')")
        args.append(f['to'])
    W = ' WHERE ' + ' AND '.join(where) if where else ''
    per = 50
    total = one(f'SELECT COUNT(*) n FROM audit_log{W}', *args)['n']
    pages = max(1, math.ceil(total / per))
    try:
        page = int(a.get('page', ''))
    except ValueError:
        page = 1
    page = min(pages, max(1, page))
    rows = all_(f'SELECT * FROM audit_log{W} ORDER BY id DESC LIMIT {per} OFFSET {(page - 1) * per}', *args)
    return render('admin/activity', {
        'title': 'Activity log', 'nav': '/admin/activity', 'rows': rows, 'total': total, 'page': page, 'pages': pages, 'f': f,
        'qsp': urlencode([(k, v) for k, v in f.items() if v]),
        'users': all_('SELECT DISTINCT user_name AS v FROM audit_log WHERE user_name IS NOT NULL ORDER BY 1'),
        'entities': all_('SELECT DISTINCT entity AS v FROM audit_log ORDER BY 1'), 'actions': all_('SELECT DISTINCT action AS v FROM audit_log ORDER BY 1'),
        'help': '<p>A record of who changed what and when. Entries cannot be edited, but you can clear old ones with the button at the bottom (download the log first from <b>Download data</b> if you may need it). Use the filters to find a person, a kind of change or a date range. Times are shown in Indian time.</p>'})


CLEAR_CHOICES = {'30': 30, '90': 90, '365': 365, 'all': None}


@bp.post('/activity/clear')
@admin_only
def activity_clear():
    keep = str(body().get('older_than') or '')
    if keep not in CLEAR_CHOICES:
        flash('err', 'Choose which entries to clear.')
        return redirect('/admin/activity')
    days = CLEAR_CHOICES[keep]
    # The clearing is recorded afterwards, so there is always a trace of who emptied the log and when.
    if days is None:
        n = run('DELETE FROM audit_log').rowcount
    else:
        n = run("DELETE FROM audit_log WHERE created_at < datetime('now', ?)", f'-{days} days').rowcount
    audit('delete', 'activity log', None, f"Cleared {n} activity log entr{'y' if n == 1 else 'ies'} ({'all' if days is None else 'older than ' + str(days) + ' days'})")
    flash('ok', f"Cleared {n} entr{'y' if n == 1 else 'ies'}." if n else 'Nothing to clear.')
    return redirect('/admin/activity')


# ───── Previews: see hidden items exactly as the public will ─────
def preview_banner():
    g.locals.update(s={**content.settings(), 'banner_text': '👁 PREVIEW – only you can see this. Close the tab when done.'}, noindex=True)


@bp.get('/preview/courses/<int:id>')
@admin_only
def preview_course(id):
    c = content.course_any(id)
    if not c:
        abort(404)
    preview_banner()
    return render('public/course', {'title': c['name'] + ' (preview)', 'desc': '', 'c': c, 'batches': content.course_batches(c['id']), 'faqs': content.faqs(c['id'])})


@bp.get('/preview/articles/<int:id>')
@admin_only
def preview_article(id):
    a = content.article_any(id)
    if not a:
        abort(404)
    preview_banner()
    return render('public/article', {'title': a['title'] + ' (preview)', 'desc': '', 'a': a})


# ─���─── Image upload for the rich-text editor ─────
@bp.post('/upload-image')
def upload_image():
    files, err = read_uploads(request, accept='image')
    if err or not files:
        return jsonify(ok=False, message='Choose an image under 5 MB.'), 400
    try:
        name = save_image(files[0])
    except UploadError as e:
        return jsonify(ok=False, message=str(e)), 400
    audit('upload', 'image', name, 'Uploaded an image in the editor')
    return jsonify(ok=True, url='/uploads/' + name)


# ───── Staff logins (admin only) ─────
ROLE_OPTS = [{'v': 'staff', 'l': 'Staff – can use enquiries, students, records, attendance, doubts'}, {'v': 'admin', 'l': 'Admin – can do everything'}]


@bp.get('/users')
@admin_only
def users():
    rows = all_("SELECT id, name, email, role, active, last_login_at FROM users WHERE role IN ('admin','staff') ORDER BY role, name")
    return render('admin/users', {
        'title': 'Staff logins', 'nav': '/admin/users', 'rows': rows, 'roleOpts': ROLE_OPTS, 'secret': None,
        'help': '<p>People who can sign in to this admin panel. Give counsellors the <b>Staff</b> role so they can follow up enquiries and manage students without touching the website content or settings.</p><ul><li>A temporary password is shown <b>once</b> when you add someone or reset their password. They must choose their own at first sign-in.</li><li><b>Switch off</b> blocks the person immediately.</li></ul>'})


@bp.post('/users')
@admin_only
def users_add():
    b = body()
    name, email = str(b.get('name') or '').strip()[:100], str(b.get('email') or '').strip().lower()[:200]
    role = 'admin' if b.get('role') == 'admin' else 'staff'
    if not name or not re.fullmatch(r'\S+@\S+\.\S+', email):
        flash('err', 'Enter a name and a valid email.')
        return redirect('/admin/users')
    if one('SELECT id FROM users WHERE lower(email) = ?', email):
        flash('err', 'Someone already uses that email.')
        return redirect('/admin/users')
    temp = pw.temp_password()
    r = run('INSERT INTO users (role, name, email, password_hash, must_change_password) VALUES (?,?,?,?,1)', role, name, email, pw.hash_password(temp))
    audit('create', 'user', r.lastrowid, f'Added {role} login for {name} ({email})')
    return render('admin/secret', {'title': 'Login created', 'nav': '/admin/users', 'who': name, 'login': email, 'secret': temp, 'back': '/admin/users'})


@bp.post('/users/<int:id>/reset')
@admin_only
def users_reset(id):
    u = one("SELECT * FROM users WHERE id = ? AND role IN ('admin','staff')", id)
    if not u:
        abort(404)
    temp = pw.temp_password()
    run('UPDATE users SET password_hash = ?, must_change_password = 1, failed_logins = 0, locked_until = NULL WHERE id = ?', pw.hash_password(temp), u['id'])
    destroy_user_sessions(u['id'])
    audit('password_reset', 'user', u['id'], f"Reset password for {u['name']}")
    return render('admin/secret', {'title': 'Password reset', 'nav': '/admin/users', 'who': u['name'], 'login': u['email'], 'secret': temp, 'back': '/admin/users'})


@bp.post('/users/<int:id>/toggle')
@admin_only
def users_toggle(id):
    u = one("SELECT * FROM users WHERE id = ? AND role IN ('admin','staff')", id)
    if not u:
        abort(404)
    if u['id'] == g.user['id']:
        flash('err', 'You cannot switch off your own login.')
        return redirect('/admin/users')
    now = 0 if u['active'] else 1
    run('UPDATE users SET active = ? WHERE id = ?', now, u['id'])
    if not now:
        destroy_user_sessions(u['id'])
    audit('update', 'user', u['id'], f"{'Switched on' if now else 'Switched off'} login for {u['name']}")
    flash('ok', f"{u['name']} is now {'active' if now else 'switched off'}.")
    return redirect('/admin/users')


# ───── Student doubts ─────
@bp.get('/doubts')
def doubts():
    status = request.args.get('status') if request.args.get('status') in ('open', 'answered', 'closed') else ''
    rows = all_(f"""SELECT d.*, u.name AS student_name, s.admission_no FROM doubts d JOIN users u ON u.id = d.student_id JOIN students s ON s.user_id = d.student_id
    {'WHERE d.status = ?' if status else ''} ORDER BY (d.status = 'open') DESC, d.id DESC LIMIT 100""", *([status] if status else []))
    return render('admin/doubts', {
        'title': 'Student doubts', 'nav': '/admin/doubts', 'rows': rows, 'status': status,
        'help': '<p>Questions that students send from their portal. Type a reply and click <b>Send reply</b>; the student sees it in their portal. Open questions are listed first.</p>'})


@bp.post('/doubts/<int:id>/reply')
def doubt_reply(id):
    d = one('SELECT * FROM doubts WHERE id = ?', id)
    if not d:
        abort(404)
    reply = str(body().get('reply') or '').strip()[:3000]
    if not reply:
        flash('err', 'Type a reply first.')
        return redirect('/admin/doubts')
    run("UPDATE doubts SET reply = ?, replied_by = ?, status = 'answered', replied_at = datetime('now') WHERE id = ?", reply, g.user['id'], d['id'])
    audit('update', 'doubt', d['id'], 'Replied to a student doubt')
    flash('ok', 'Reply sent.')
    return redirect('/admin/doubts')


@bp.post('/doubts/<int:id>/close')
def doubt_close(id):
    d = one('SELECT * FROM doubts WHERE id = ?', id)
    if not d:
        abort(404)
    run("UPDATE doubts SET status = 'closed' WHERE id = ?", d['id'])
    audit('update', 'doubt', d['id'], 'Closed a student doubt')
    return redirect('/admin/doubts')
