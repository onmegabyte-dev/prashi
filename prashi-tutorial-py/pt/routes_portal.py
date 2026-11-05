"""Student portal. Everything here is read from the database using the signed-in student's own id
(g.user['id']) - there is no id in any URL that selects a student, so one student can never ask for another's data."""
import os
import re
from pathlib import Path

from flask import Blueprint, abort, g, redirect, request, send_from_directory

from .audit import audit
from .db import all_, one, run
from .mail import send_mail
from .receipt import load_receipt
from .tz import now_local
from .uploads import PRIVATE_DIR, UploadError, read_uploads, remove_private, safe_name, save_image_private
from .web import Limiter, body, days_ago, flash, js_round, render, send_private
from . import content

bp = Blueprint('portal', __name__)
TYPE = {'material': 'Study material', 'notes': 'Notes', 'test_paper': 'Test paper', 'mock_result': 'Test result', 'remark': 'Teacher’s remark'}


@bp.before_request
def area():
    g.locals.update(noindex=True, nav=request.path, TYPE=TYPE)


def S():
    return content.settings()


def my_batch_ids(sid):
    """The student's batches (dropped ones lose access to batch material)."""
    return [r['batch_id'] for r in all_("SELECT batch_id FROM enrollments WHERE student_id = ? AND status != 'dropped'", sid)]


def visible_records(sid, extra_where='', *args):
    """A record is visible only when the admin released it AND it is addressed to this student or one of their batches."""
    b = my_batch_ids(sid)
    marks = ','.join('?' for _ in b)
    return all_(f"""SELECT r.*, bt.name AS batch_name FROM records r LEFT JOIN batches bt ON bt.id = r.batch_id
    WHERE r.visible_to_student = 1 AND (r.student_id = ?{f' OR (r.student_id IS NULL AND r.batch_id IN ({marks}))' if b else ''}) {extra_where}
    ORDER BY COALESCE(r.record_date, substr(r.created_at, 1, 10)) DESC, r.id DESC""", sid, *b, *args)


def fees(sid):
    rows = all_("""SELECT e.*, b.name AS batch_name, c.name AS course_name, b.timing, b.start_date, e.fee_total - e.discount AS payable,
      (SELECT COALESCE(SUM(amount), 0) FROM payments p WHERE p.enrollment_id = e.id) AS paid
      FROM enrollments e JOIN batches b ON b.id = e.batch_id JOIN courses c ON c.id = b.course_id WHERE e.student_id = ? ORDER BY e.id DESC""", sid)
    return [{**e, 'balance': e['payable'] - e['paid']} for e in rows]


def my_notices(sid):
    n, b = now_local(), my_batch_ids(sid)
    marks = ','.join('?' for _ in b)
    return all_(f"""SELECT * FROM notices WHERE visible = 1 AND audience = 'students' AND (publish_at IS NULL OR publish_at <= ?) AND (expires_at IS NULL OR expires_at > ?)
    AND (batch_id IS NULL{f' OR batch_id IN ({marks})' if b else ''}) ORDER BY pinned DESC, created_at DESC LIMIT 30""", n, n, *b)


def attendance_summary(sid, days):
    rows = all_('SELECT a.*, b.name AS batch_name FROM attendance a JOIN batches b ON b.id = a.batch_id WHERE a.student_id = ? AND a.day >= ? ORDER BY a.day DESC', sid, days_ago(days))
    present = len([r for r in rows if r['status'] in ('present', 'late')])
    return {'rows': rows, 'total': len(rows), 'present': present, 'pct': js_round(present / len(rows) * 100) if rows else None}


def pct(r):
    return js_round(r['score'] / r['max_score'] * 100) if r['max_score'] else None


def with_pct(rows):
    return [{**r, 'pct': pct(r)} for r in rows]


def totals_of(fee_rows):
    t = {'payable': sum(e['payable'] for e in fee_rows), 'paid': sum(e['paid'] for e in fee_rows)}
    t['balance'] = t['payable'] - t['paid']
    return t


@bp.get('/')
def dashboard():
    sid = g.user['id']
    f = [e for e in fees(sid) if e['status'] != 'dropped']
    remarks = visible_records(sid, "AND r.type = 'remark'")
    return render('portal/dashboard', {
        'title': 'My dashboard', 'batches': [e for e in f if e['status'] == 'active'], 'totals': totals_of(f), 'att': attendance_summary(sid, 90),
        'scores': with_pct(visible_records(sid, "AND r.type = 'mock_result'")[:5]),
        'materials': visible_records(sid, "AND r.type IN ('material','notes','test_paper')")[:5], 'notices': my_notices(sid)[:3],
        'openDoubts': one("SELECT COUNT(*) n FROM doubts WHERE student_id = ? AND status = 'open'", sid)['n'],
        'answered': one("SELECT COUNT(*) n FROM doubts WHERE student_id = ? AND status = 'answered'", sid)['n'],
        'remark': remarks[0] if remarks else None})


@bp.get('/profile')
def profile():
    s = one('SELECT u.name, u.email, u.username, u.last_login_at, s.admission_no, s.class_level, s.school, s.dob, s.parent_name, s.parent_phone, s.parent_email, s.joined_on '
            'FROM users u JOIN students s ON s.user_id = u.id WHERE u.id = ?', g.user['id'])
    return render('portal/profile', {'title': 'My profile', 's': s, 'batches': [e for e in fees(g.user['id']) if e['status'] != 'dropped']})


# ───── Profile picture (the only part of the profile a student can change) ─────
photo_limiter = Limiter(60 * 60, 20)


@bp.get('/photo')
def photo():
    row = one('SELECT photo FROM students WHERE user_id = ?', g.user['id'])
    if not row or not safe_name(row['photo']):
        abort(404)
    return send_private(row['photo'])


@bp.post('/profile/photo')
def photo_upload():
    def back(kind, msg):
        flash(kind, msg)
        return redirect('/portal/profile')

    if not photo_limiter.hit('p%s' % g.user['id']):
        return back('err', 'Too many picture changes. Please try again later.')
    files, err = read_uploads(request, accept='photo')
    if err:
        return back('err', 'That picture is too large (limit 5 MB).' if err == 'LIMIT_FILE_SIZE' else 'The upload failed. Please try again.')
    if not files or not files[0].size:
        return back('err', 'Choose a picture first.')
    try:
        name = save_image_private(files[0])
    except UploadError as e:
        return back('err', str(e))
    old = one('SELECT photo FROM students WHERE user_id = ?', g.user['id'])
    run('UPDATE students SET photo = ? WHERE user_id = ?', name, g.user['id'])
    if old and old['photo']:
        remove_private(old['photo'])
    audit('update', 'student', g.user['id'], f"{g.user['name']} changed their profile picture")
    return back('ok', 'Your profile picture has been updated.')


@bp.post('/profile/photo/remove')
def photo_remove():
    old = one('SELECT photo FROM students WHERE user_id = ?', g.user['id'])
    if old and old['photo']:
        run('UPDATE students SET photo = NULL WHERE user_id = ?', g.user['id'])
        remove_private(old['photo'])
        audit('update', 'student', g.user['id'], f"{g.user['name']} removed their profile picture")
    flash('ok', 'Your profile picture has been removed.')
    return redirect('/portal/profile')


@bp.get('/fees')
def fees_page():
    f = fees(g.user['id'])
    live = [e for e in f if e['status'] != 'dropped']
    payments = all_("""SELECT p.*, c.name AS course_name FROM payments p JOIN enrollments e ON e.id = p.enrollment_id JOIN batches b ON b.id = e.batch_id JOIN courses c ON c.id = b.course_id
    WHERE e.student_id = ? ORDER BY p.paid_on DESC, p.id DESC""", g.user['id'])
    return render('portal/fees', {'title': 'Fees', 'fees': f, 'totals': totals_of(live), 'payments': payments})


@bp.get('/receipts/<pid>')
def receipt(pid):
    rc = load_receipt(pid, g.user['id'])
    if not rc:
        abort(404)
    return render('receipt', {'rc': rc, 'back': '/portal/fees'})


@bp.get('/attendance')
def attendance():
    return render('portal/attendance', {'title': 'Attendance', 'att': attendance_summary(g.user['id'], 120)})


@bp.get('/scores')
def scores():
    return render('portal/scores', {'title': 'Test scores', 'rows': with_pct(visible_records(g.user['id'], "AND r.type = 'mock_result'"))})


@bp.get('/materials')
def materials():
    typ = request.args.get('type') if request.args.get('type') in ('material', 'notes', 'test_paper') else ''
    q = str(request.args.get('q', '')).strip()[:80]
    rows = visible_records(g.user['id'], "AND r.type IN ('material','notes','test_paper')")
    if typ:
        rows = [r for r in rows if r['type'] == typ]
    if q:
        rows = [r for r in rows if q.lower() in (r['title'] + ' ' + (r['body'] or '')).lower()]
    return render('portal/materials', {'title': 'Study material', 'rows': rows, 'type': typ, 'q': q})


@bp.get('/remarks')
def remarks():
    return render('portal/remarks', {'title': 'Teacher’s remarks', 'rows': visible_records(g.user['id'], "AND r.type = 'remark'")})


@bp.get('/notices')
def notices():
    return render('portal/notices', {'title': 'Notices', 'notices': my_notices(g.user['id'])})


@bp.get('/files/<fid>')
def file_(fid):
    """A file is served only if the record is released AND belongs to this student or one of their batches."""
    if not re.fullmatch(r'\d+', fid):
        abort(404)
    rows = visible_records(g.user['id'], 'AND r.id = ?', int(fid))
    r = rows[0] if rows else None
    if not r or not safe_name(r['file_path']):
        abort(404)
    name = re.sub(r'[^\w\- ]+', '', r['title']).strip()[:80] or 'file'
    resp = send_from_directory(PRIVATE_DIR, r['file_path'], as_attachment=True, download_name=name + Path(r['file_path']).suffix)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


# ───── Doubts ─────
doubt_limiter = Limiter(60 * 60, 10)


def _doubts(sid):
    return all_('SELECT * FROM doubts WHERE student_id = ? ORDER BY id DESC LIMIT 50', sid)


@bp.get('/doubts')
def doubts():
    return render('portal/doubts', {'title': 'Ask a doubt', 'rows': _doubts(g.user['id']), 'vals': {}, 'error': ''})


@bp.post('/doubts')
def doubts_post():
    sid = g.user['id']
    if not doubt_limiter.hit('u%s' % sid):
        flash('err', 'You have sent a lot of questions in the last hour. Please wait a little before asking more.')
        return redirect('/portal/doubts')
    b = body()
    subject, message = str(b.get('subject') or '').strip()[:150], str(b.get('message') or '').strip()
    if not message:
        return render('portal/doubts', {'title': 'Ask a doubt', 'rows': _doubts(sid), 'vals': {'subject': subject}, 'error': 'Please type your question.'}, 422)
    if len(message) > 3000:
        return render('portal/doubts', {'title': 'Ask a doubt', 'rows': _doubts(sid), 'vals': {'subject': subject, 'message': message},
                                        'error': 'Please keep your question under 3000 characters.'}, 422)
    r = run('INSERT INTO doubts (student_id, subject, message) VALUES (?,?,?)', sid, subject or None, message)
    audit('create', 'doubt', r.lastrowid, f"{g.user['name']} sent a doubt")
    send_mail(S().get('admin_inbox_email'), f"New student doubt from {g.user['name']}",
              f"{subject + chr(10) + chr(10) if subject else ''}{message}\n\nReply from Admin → Student doubts.")
    flash('ok', 'Your question has been sent. A teacher will reply here.')
    return redirect('/portal/doubts')
