"""Students: accounts, parent contact, batches, fees and payments."""
import json
import math
import re
from urllib.parse import urlencode

from flask import Blueprint, abort, g, redirect, request

from .. import pw
from ..audit import audit
from ..db import all_, one, run, tx
from ..fmt import locale
from ..receipt import load_receipt
from ..student_rules import CLASSES, fields as student_fields, next_admission_no, read_student
from ..tz import today_local
from ..uploads import remove_private, safe_name
from ..web import admin_only, body, days_ago, destroy_user_sessions, flash, int_in, js_round, render, send_private

bp = Blueprint('students', __name__)
MODES = ['Cash', 'UPI', 'Card', 'Bank transfer', 'Cheque', 'Other']


def fee_rows(sid):
    """Fees for one student: per enrolment and in total. Balance is always calculated, never stored."""
    rows = all_("""SELECT e.*, b.name AS batch_name, c.name AS course_name, e.fee_total - e.discount AS payable,
    (SELECT COALESCE(SUM(amount),0) FROM payments p WHERE p.enrollment_id = e.id) AS paid
    FROM enrollments e JOIN batches b ON b.id = e.batch_id JOIN courses c ON c.id = b.course_id WHERE e.student_id = ? ORDER BY e.id DESC""", sid)
    return [{**e, 'balance': e['payable'] - e['paid'],
             'payments': all_('SELECT p.*, u.name AS by_name FROM payments p LEFT JOIN users u ON u.id = p.recorded_by WHERE p.enrollment_id = ? ORDER BY p.paid_on DESC, p.id DESC', e['id'])}
            for e in rows]


# ───── List ─────
@bp.get('/', strict_slashes=False)
def list_():
    a = request.args
    q, cls, batch, st = str(a.get('q', '')).strip()[:100], str(a.get('cls', '')), str(a.get('batch', '')), str(a.get('st', ''))
    where, args = [], []
    if q:
        where.append('(t.name LIKE ? OR t.admission_no LIKE ? OR t.parent_phone LIKE ? OR t.parent_name LIKE ? OR (SELECT email FROM users WHERE id = t.id) LIKE ?)')
        args += ['%' + q + '%'] * 5
    if cls:
        where.append('t.class_level = ?')
        args.append(cls)
    if re.fullmatch(r'\d+', batch):
        where.append("EXISTS (SELECT 1 FROM enrollments e WHERE e.student_id = t.id AND e.batch_id = ? AND e.status = 'active')")
        args.append(int(batch))
    if st == 'active':
        where.append('t.active = 1')
    elif st == 'off':
        where.append('t.active = 0')
    elif st == 'due':
        where.append('t.balance > 0')
    sort_map = {'name': 'name', 'adm': 'admission_no', 'balance': 'balance', 'joined': 'joined_on'}
    sort = a.get('sort') if a.get('sort') in sort_map else 'name'
    dir_ = 'desc' if a.get('dir') == 'desc' else 'asc'
    inner = """SELECT u.id, u.name, u.active, u.last_login_at, s.admission_no, s.class_level, s.parent_name, s.parent_phone, s.joined_on,
    (SELECT COALESCE(SUM(e.fee_total - e.discount),0) FROM enrollments e WHERE e.student_id = u.id AND e.status != 'dropped') AS fee,
    (SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN enrollments e ON e.id = p.enrollment_id WHERE e.student_id = u.id AND e.status != 'dropped') AS paid,
    (SELECT COALESCE(SUM(e.fee_total - e.discount),0) FROM enrollments e WHERE e.student_id = u.id AND e.status != 'dropped') -
    (SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN enrollments e ON e.id = p.enrollment_id WHERE e.student_id = u.id AND e.status != 'dropped') AS balance,
    (SELECT GROUP_CONCAT(b.name, ', ') FROM enrollments e JOIN batches b ON b.id = e.batch_id WHERE e.student_id = u.id AND e.status = 'active') AS batches
    FROM users u JOIN students s ON s.user_id = u.id WHERE u.role = 'student'"""
    outer = ' WHERE ' + ' AND '.join(where) if where else ''
    per = 25
    n = one(f'SELECT COUNT(*) n FROM ({inner}) t{outer}', *args)['n']
    pages = max(1, math.ceil(n / per))
    try:
        page = int(a.get('page', ''))
    except ValueError:
        page = 1
    page = min(pages, max(1, page))
    rows = all_(f'SELECT t.* FROM ({inner}) t{outer} ORDER BY t.{sort_map[sort]} {dir_}, t.id LIMIT {per} OFFSET {(page - 1) * per}', *args)
    p = [(k, v) for k, v in (('q', q), ('cls', cls), ('batch', batch), ('st', st)) if v]
    return render('admin/students', {
        'title': 'Students', 'nav': '/admin/students', 'rows': rows, 'total': n, 'page': page, 'pages': pages, 'q': q, 'cls': cls, 'batch': batch, 'st': st,
        'sort': sort, 'dir': dir_, 'CLASSES': CLASSES, 'qs': urlencode(p), 'qsp': urlencode(p + [('sort', sort), ('dir', dir_)]),
        'batches': all_("SELECT b.id, c.name || ' – ' || b.name AS label FROM batches b JOIN courses c ON c.id = b.course_id ORDER BY c.name, b.name"),
        'help': '<p>Everyone enrolled at the institute.</p><ul><li><b>Add student</b> creates their login. A temporary password is shown once – print it or write it down for the family.</li><li>Open a student to see their parents’ contact, batches, <b>fees paid and balance</b>, attendance and records.</li><li>Use the filters to find, for example, everyone in a batch or everyone with fees still due.</li></ul>'})


# ───── Create ─────
def new_form(vals, errs, status=200):
    batches = all_("SELECT b.id AS v, c.name || ' – ' || b.name || ' (' || b.status || ')' AS l FROM batches b JOIN courses c ON c.id = b.course_id WHERE b.status != 'closed' ORDER BY c.name, b.name")
    return render('admin/student-form', {
        'title': 'Add student', 'nav': '/admin/students', 'fields': student_fields(), 'vals': vals, 'errs': errs, 'batches': batches, 'st': None, 'action': '/admin/students/new',
        'help': '<p>Fill in the student’s details. When you save, we create their login and show you a temporary password <b>once</b>.</p><ul><li>Choose a batch to enrol them straight away; the fee is taken from the course and you can change it later.</li></ul>'}, status)


@bp.get('/new')
def new():
    vals = {'joined_on': today_local()}
    frm = request.args.get('from', '')
    s = re.fullmatch(r'\d+', frm) and one("SELECT * FROM submissions WHERE id = ? AND form = 'admission'", int(frm))
    if s:
        d = json.loads(s['data_json'] or '{}')
        course = d.get('course') and one('SELECT id FROM courses WHERE slug = ?', d['course'])
        b = course and one("SELECT id FROM batches WHERE course_id = ? AND status != 'closed' ORDER BY start_date LIMIT 1", course['id'])
        vals = {**vals, 'name': d.get('student_name'), 'parent_phone': d.get('phone'), 'parent_email': d.get('email'),
                'class_level': d.get('class_level') if d.get('class_level') in CLASSES else '', 'batch_id': b['id'] if b else '', 'from': s['id']}
    return new_form(vals, {})


@bp.post('/new')
def new_post():
    b = body()
    v, errs = read_student(b, 0)
    batch_id = int(b['batch_id']) if re.fullmatch(r'\d+', b.get('batch_id') or '') else None
    if batch_id and not one('SELECT 1 FROM batches WHERE id = ?', batch_id):
        errs['batch_id'] = 'Choose a batch from the list.'
    if errs:
        return new_form(dict(b), errs, 422)
    temp = pw.temp_password()
    hashed = pw.hash_password(temp)
    adm = next_admission_no()
    username = adm.lower()
    with tx():
        uid = run("INSERT INTO users (role, name, email, username, password_hash, must_change_password) VALUES ('student',?,?,?,?,1)",
                  v['name'], v['email'], username, hashed).lastrowid
        run('INSERT INTO students (user_id, admission_no, class_level, school, dob, parent_name, parent_phone, parent_email, address, joined_on, notes_internal) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            uid, adm, v['class_level'], v['school'], v['dob'], v['parent_name'], v['parent_phone'], v['parent_email'], v['address'], v['joined_on'] or today_local(), v['notes_internal'])
        if batch_id:
            fee = one('SELECT c.fee_amount FROM batches b JOIN courses c ON c.id = b.course_id WHERE b.id = ?', batch_id)['fee_amount'] or 0
            run('INSERT INTO enrollments (student_id, batch_id, fee_total) VALUES (?,?,?)', uid, batch_id, fee)
        if re.fullmatch(r'\d+', b.get('from') or ''):
            run("UPDATE submissions SET status = 'enrolled' WHERE id = ? AND form = 'admission'", int(b['from']))
    audit('create', 'student', uid, f"Created student {v['name']} ({adm})")
    return render('admin/secret', {'title': 'Student created', 'nav': '/admin/students', 'who': v['name'], 'login': f'{username}  (admission no. {adm})',
                                   'secret': temp, 'back': f'/admin/students/{uid}'})


# ───── One student ─────
def load(id_):
    s = one("SELECT u.*, s.* FROM users u JOIN students s ON s.user_id = u.id WHERE u.id = ? AND u.role = 'student'", id_)
    if not s:
        abort(404)
    return s


@bp.get('/<int:id>')
def show(id):
    s = load(id)
    fees = fee_rows(s['id'])
    live = [f for f in fees if f['status'] != 'dropped']
    totals = {'payable': sum(f['payable'] for f in live), 'paid': sum(f['paid'] for f in live)}
    totals['balance'] = totals['payable'] - totals['paid']
    att = all_('SELECT status, COUNT(*) n FROM attendance WHERE student_id = ? AND day >= ? GROUP BY status', s['id'], days_ago(90))
    att_total = sum(x['n'] for x in att)
    present = sum(x['n'] for x in att if x['status'] in ('present', 'late'))
    enrolled = {f['batch_id'] for f in fees}
    open_ = [b for b in all_("SELECT b.id AS v, c.name || ' – ' || b.name AS l, c.fee_amount FROM batches b JOIN courses c ON c.id = b.course_id WHERE b.status != 'closed' ORDER BY c.name, b.name") if b['v'] not in enrolled]
    records = all_('SELECT id, type, title, visible_to_student, record_date FROM records WHERE student_id = ? ORDER BY id DESC LIMIT 6', s['id'])
    return render('admin/student', {
        'title': s['name'], 'nav': '/admin/students', 's': s, 'fees': fees, 'totals': totals, 'att': att,
        'attPct': js_round(present / att_total * 100) if att_total else None, 'attTotal': att_total, 'open': open_, 'records': records,
        'MODES': MODES, 'today': today_local(),
        'help': '<p>Everything about one student.</p><ul><li><b>Fees:</b> add the amount whenever the family pays. The balance updates by itself.</li><li><b>Assign to a batch</b> to enrol them (fee defaults to the course fee – change it if you gave a discount).</li><li><b>Reset password</b> gives a new temporary password if they forget it.</li><li><b>Switch off</b> blocks their login without deleting anything.</li></ul>'})


@bp.get('/<int:id>/edit')
def edit(id):
    s = load(id)
    return render('admin/student-form', {'title': 'Edit ' + s['name'], 'nav': '/admin/students', 'fields': student_fields(), 'vals': s, 'errs': {}, 'batches': [], 'st': s,
                                         'action': f"/admin/students/{s['id']}/edit", 'help': '<p>Update the student’s details. Their login name (admission number) does not change.</p>'})


@bp.post('/<int:id>/edit')
def edit_post(id):
    s = load(id)
    b = body()
    v, errs = read_student(b, s['id'])
    if errs:
        return render('admin/student-form', {'title': 'Edit ' + s['name'], 'nav': '/admin/students', 'fields': student_fields(), 'vals': dict(b), 'errs': errs, 'batches': [],
                                             'st': s, 'action': f"/admin/students/{s['id']}/edit", 'help': ''}, 422)
    with tx():
        run('UPDATE users SET name = ?, email = ? WHERE id = ?', v['name'], v['email'], s['id'])
        run('UPDATE students SET class_level=?, school=?, dob=?, parent_name=?, parent_phone=?, parent_email=?, address=?, joined_on=?, notes_internal=? WHERE user_id=?',
            v['class_level'], v['school'], v['dob'], v['parent_name'], v['parent_phone'], v['parent_email'], v['address'], v['joined_on'], v['notes_internal'], s['id'])
    audit('update', 'student', s['id'], f"Edited student {v['name']} ({s['admission_no']})")
    flash('ok', 'Student saved.')
    return redirect(f"/admin/students/{s['id']}")


@bp.post('/<int:id>/reset-password')
def reset_password(id):
    s = load(id)
    temp = pw.temp_password()
    run('UPDATE users SET password_hash = ?, must_change_password = 1, failed_logins = 0, locked_until = NULL WHERE id = ?', pw.hash_password(temp), s['id'])
    destroy_user_sessions(s['id'])
    audit('password_reset', 'student', s['id'], f"Reset password for {s['name']} ({s['admission_no']})")
    return render('admin/secret', {'title': 'Password reset', 'nav': '/admin/students', 'who': s['name'], 'login': f"{s['username']}  (admission no. {s['admission_no']})",
                                   'secret': temp, 'back': f"/admin/students/{s['id']}"})


@bp.post('/<int:id>/toggle')
def toggle(id):
    s = load(id)
    now = 0 if s['active'] else 1
    run('UPDATE users SET active = ? WHERE id = ?', now, s['id'])
    if not now:
        destroy_user_sessions(s['id'])
    audit('update', 'student', s['id'], f"{'Switched on' if now else 'Switched off'} login for {s['name']} ({s['admission_no']})")
    flash('ok', f"{s['name']}’s login is now {'on' if now else 'switched off'}.")
    return redirect(f"/admin/students/{s['id']}")


@bp.post('/<int:id>/delete')
@admin_only
def delete(id):
    s = load(id)
    files = [r['file_path'] for r in all_('SELECT file_path FROM records WHERE student_id = ? AND file_path IS NOT NULL', s['id'])]
    if s['photo']:
        files.append(s['photo'])
    destroy_user_sessions(s['id'])
    run('DELETE FROM users WHERE id = ?', s['id'])                 # cascades to profile, enrolments, payments, records, attendance, doubts
    for f in files:
        remove_private(f)
    audit('delete', 'student', s['id'], f"Deleted student {s['name']} ({s['admission_no']}) and all their records")
    flash('ok', f"Deleted {s['name']}.")
    return redirect('/admin/students')


# ───── Batches and fees ─────
@bp.post('/<int:id>/enroll')
def enroll(id):
    s = load(id)
    b = body()
    batch = re.fullmatch(r'\d+', b.get('batch_id') or '') and one('SELECT b.*, c.fee_amount, c.name AS course_name FROM batches b JOIN courses c ON c.id = b.course_id WHERE b.id = ?', int(b['batch_id']))
    ft = b.get('fee_total')
    fee = ((batch['fee_amount'] or 0) if batch else 0) if ft in ('', None) else int_in(ft, 0, 100000000)
    disc = int_in(b.get('discount'), 0, 100000000) if b.get('discount') else 0
    back = f"/admin/students/{s['id']}"
    if not batch:
        flash('err', 'Choose a batch.')
        return redirect(back)
    if fee is None or disc is None or disc > fee:
        flash('err', 'Check the fee and discount: whole rupees, and the discount cannot be more than the fee.')
        return redirect(back)
    if one('SELECT 1 FROM enrollments WHERE student_id = ? AND batch_id = ?', s['id'], batch['id']):
        flash('err', 'Already in that batch.')
        return redirect(back)
    run('INSERT INTO enrollments (student_id, batch_id, fee_total, discount) VALUES (?,?,?,?)', s['id'], batch['id'], fee, disc)
    audit('create', 'enrollment', s['id'], f"Enrolled {s['name']} in {batch['course_name']} – {batch['name']} (fee ₹{fee}, discount ₹{disc})")
    flash('ok', f"Enrolled in {batch['name']}." + (' Note: this batch is marked full.' if batch['status'] == 'full' else ''))
    return redirect(back)


def enrolment(s, eid):
    e = one('SELECT * FROM enrollments WHERE id = ? AND student_id = ?', eid, s['id'])
    if not e:
        abort(404)
    return e


@bp.post('/<int:id>/enrollment/<int:eid>')
def enrollment_update(id, eid):
    s = load(id)
    e = enrolment(s, eid)
    b = body()
    fee, disc = int_in(b.get('fee_total'), 0, 100000000), int_in(b.get('discount') or 0, 0, 100000000)
    status = b.get('status') if b.get('status') in ('active', 'completed', 'dropped') else e['status']
    if fee is None or disc is None or disc > fee:
        flash('err', 'Check the fee and discount.')
    else:
        run('UPDATE enrollments SET fee_total=?, discount=?, status=? WHERE id=?', fee, disc, status, e['id'])
        audit('update', 'enrollment', e['id'], f"Updated fees/status for {s['name']}: fee ₹{fee}, discount ₹{disc}, {status}")
        flash('ok', 'Fees updated.')
    return redirect(f"/admin/students/{s['id']}")


@bp.post('/<int:id>/enrollment/<int:eid>/delete')
def enrollment_delete(id, eid):
    s = load(id)
    e = enrolment(s, eid)
    run('DELETE FROM enrollments WHERE id = ?', e['id'])
    audit('delete', 'enrollment', e['id'], f"Removed {s['name']} from a batch (and its payment records)")
    flash('ok', 'Removed from the batch.')
    return redirect(f"/admin/students/{s['id']}")


@bp.post('/<int:id>/enrollment/<int:eid>/payments')
def payment_add(id, eid):
    s = load(id)
    e = enrolment(s, eid)
    b = body()
    back = f"/admin/students/{s['id']}"
    amount = int_in(b.get('amount'), 1, 100000000)
    paid_on = str(b.get('paid_on') or '')
    paid = one('SELECT COALESCE(SUM(amount),0) n FROM payments WHERE enrollment_id = ?', e['id'])['n']
    balance = e['fee_total'] - e['discount'] - paid
    from ..tz import valid_day
    if not amount:
        flash('err', 'Enter the amount in whole rupees.')
    elif not valid_day(paid_on):
        flash('err', 'Enter the payment date.')
    elif amount > balance:
        flash('err', f'That is more than the balance (₹{locale(balance)}). Check the amount or the fee.')
    else:
        mode = b.get('mode') if b.get('mode') in MODES else 'Other'
        note = str(b.get('note') or '').strip()[:200] or None
        receipt = str(b.get('receipt_no') or '').strip()[:40] or None
        pid = run('INSERT INTO payments (enrollment_id, amount, paid_on, mode, receipt_no, note, recorded_by) VALUES (?,?,?,?,?,?,?)',
                  e['id'], amount, paid_on, mode, receipt, note, g.user['id']).lastrowid
        if not receipt:
            receipt = 'PT-R-' + str(pid).zfill(5)
            run('UPDATE payments SET receipt_no = ? WHERE id = ?', receipt, pid)
        audit('create', 'payment', pid, f"Recorded ₹{locale(amount)} ({mode}) from {s['name']} – receipt {receipt}")
        flash('ok', f'Payment of ₹{locale(amount)} recorded (receipt {receipt}). Balance: ₹{locale(balance - amount)}.')
    return redirect(back)


@bp.post('/<int:id>/payments/<int:pid>/delete')
def payment_delete(id, pid):
    s = load(id)
    p = one('SELECT p.* FROM payments p JOIN enrollments e ON e.id = p.enrollment_id WHERE p.id = ? AND e.student_id = ?', pid, s['id'])
    if not p:
        abort(404)
    run('DELETE FROM payments WHERE id = ?', p['id'])
    audit('delete', 'payment', p['id'], f"Deleted payment ₹{locale(p['amount'])} (receipt {p['receipt_no']}) for {s['name']}")
    flash('ok', 'Payment deleted.')
    return redirect(f"/admin/students/{s['id']}")


# ───── Student's profile picture, for staff ─────
@bp.get('/<int:id>/photo')
def photo(id):
    s = load(id)
    if not safe_name(s['photo']):
        abort(404)
    return send_private(s['photo'])


# ───── Printable receipt ─────
@bp.get('/<int:id>/receipt/<pid>')
def receipt(id, pid):
    s = load(id)
    rc = load_receipt(pid, s['id'])
    if not rc:
        abort(404)
    return render('receipt', {'rc': rc, 'back': f"/admin/students/{s['id']}"})
