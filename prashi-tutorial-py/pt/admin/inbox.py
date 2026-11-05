"""Enquiries & admissions inbox: search, filter, assign, notes, status, CSV export."""
import json
import math
import re
from urllib.parse import urlencode

from flask import Blueprint, abort, g, redirect, request

from ..audit import audit
from ..db import all_, one, run
from ..tz import show_utc
from ..web import body, denied, flash, render

bp = Blueprint('inbox', __name__)
STATUSES = [['new', 'New'], ['contacted', 'Contacted'], ['demo_booked', 'Demo booked'], ['enrolled', 'Enrolled'], ['closed', 'Closed']]
FORMS = [['admission', 'Admission'], ['enquiry', 'Enquiry'], ['counselling', 'Counselling'], ['contact', 'Contact message'], ['newsletter', 'Newsletter']]
BASE = 'SELECT s.*, u.name AS assignee FROM submissions s LEFT JOIN users u ON u.id = s.assigned_to'


def parse(r):
    try:
        d = json.loads(r['data_json'])
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def name_of(d):
    return d.get('student_name') or d.get('name') or d.get('email') or '—'


def filter_query():
    """Builds the WHERE clause from the query string (shared by the list and the CSV export)."""
    a = request.args
    where, args = [], []
    f = {'form': str(a.get('form', '')), 'kind': str(a.get('kind', '')), 'status': str(a.get('status', '')), 'who': str(a.get('who', '')), 'q': str(a.get('q', '')).strip()[:100]}
    if f['form']:
        where.append('s.form = ?')
        args.append(f['form'])
    if f['kind'] == 'enquiries':
        where.append("s.form != 'admission'")
    if f['status']:
        where.append('s.status = ?')
        args.append(f['status'])
    if f['who'] == 'me':
        where.append('s.assigned_to = ?')
        args.append(g.user['id'])
    elif f['who'] == 'none':
        where.append('s.assigned_to IS NULL')
    elif re.fullmatch(r'\d+', f['who']):
        where.append('s.assigned_to = ?')
        args.append(int(f['who']))
    if f['q']:
        where.append('s.data_json LIKE ?')
        args.append('%' + re.sub(r'[%_]', '', f['q']) + '%')
    return (' WHERE ' + ' AND '.join(where) if where else ''), args, f


def counsellors():
    return all_("SELECT id, name FROM users WHERE role IN ('admin','staff') AND active = 1 ORDER BY name")


@bp.get('/', strict_slashes=False)
def list_():
    W, args, f = filter_query()
    a = request.args
    sort = a.get('sort') if a.get('sort') in ('created_at', 'status', 'form') else 'created_at'
    dir_ = 'asc' if a.get('dir') == 'asc' else 'desc'
    per = 25
    total = one(f'SELECT COUNT(*) n FROM submissions s{W}', *args)['n']
    pages = max(1, math.ceil(total / per))
    try:
        page = int(a.get('page', ''))
    except ValueError:
        page = 1
    page = min(pages, max(1, page))
    rows = []
    for r in all_(f'{BASE}{W} ORDER BY s.{sort} {dir_}, s.id DESC LIMIT {per} OFFSET {(page - 1) * per}', *args):
        d = parse(r)
        rows.append({**r, 'who': name_of(d), 'phone': d.get('phone') or '', 'course': d.get('course') or d.get('class_level') or ''})
    p = [(k, v) for k, v in f.items() if v]
    return render('admin/inbox', {
        'title': 'Enquiries & admissions', 'nav': '/admin/inbox', 'rows': rows, 'total': total, 'page': page, 'pages': pages, 'f': f, 'sort': sort, 'dir': dir_,
        'STATUSES': STATUSES, 'FORMS': FORMS, 'counsellors': counsellors(), 'qs': urlencode(p), 'qsp': urlencode(p + [('sort', sort), ('dir', dir_)]),
        'help': '<p>Everyone who filled in a form on the website lands here.</p><ul><li><b>Search</b> looks through names, phone numbers and answers.</li><li>Click a name to see details, <b>assign</b> it to a counsellor, write <b>private notes</b> and change the <b>status</b> as you follow up: New → Contacted → Demo booked → Enrolled (or Closed).</li><li><b>Download CSV</b> exports exactly what you are looking at, to open in Excel.</li></ul>'})


@bp.get('/export.csv')
def export_csv():
    """CSV: opens in Excel. Cells starting with = + - @ are neutralised so a hostile enquiry can't run formulas."""
    from datetime import date
    W, args, _ = filter_query()
    rows = all_(f'{BASE}{W} ORDER BY s.id DESC LIMIT 20000', *args)
    labels = {}
    for form in ('admission', 'enquiry', 'counselling', 'contact'):
        for x in all_('SELECT name, label FROM form_fields WHERE form = ?', form):
            labels.setdefault(x['name'], x['label'])
    keys = []
    for r in rows:
        for k in parse(r):
            if k not in keys:
                keys.append(k)

    def cell(v):
        s = '' if v is None else str(v)
        if re.match(r'[=+\-@\t\r]', s):
            s = "'" + s
        return '"' + s.replace('"', '""') + '"'

    head = ['ID', 'Received', 'Form', 'Status', 'Assigned to'] + [labels.get(k, k) for k in keys]
    lines = [','.join(cell(h) for h in head)]
    for r in rows:
        d = parse(r)
        lines.append(','.join(cell(x) for x in [r['id'], show_utc(r['created_at']), r['form'], r['status'], r['assignee'] or ''] + [d.get(k, '') if d.get(k) is not None else '' for k in keys]))
    audit('export', 'submissions', None, f'Downloaded CSV of {len(rows)} enquiries/admissions')
    return ('\ufeff' + '\r\n'.join(lines), 200, {'Content-Type': 'text/csv; charset=utf-8',
                                                 'Content-Disposition': f'attachment; filename="enquiries-{date.today().isoformat()}.csv"'})


@bp.get('/<int:id>')
def detail(id):
    r = one(f'{BASE} WHERE s.id = ?', id)
    if not r:
        abort(404)
    data = parse(r)
    labels = {x['name']: x['label'] for x in all_('SELECT name, label FROM form_fields WHERE form = ?', r['form'])}
    answers = [[labels.get(k, k), v] for k, v in data.items()]
    notes = all_('SELECT n.*, u.name AS author FROM submission_notes n LEFT JOIN users u ON u.id = n.author_id WHERE n.submission_id = ? ORDER BY n.id DESC', r['id'])
    student = one('SELECT u.id FROM users u JOIN students s ON s.user_id = u.id WHERE lower(u.name) = lower(?) LIMIT 1', data['student_name']) if data.get('student_name') else None
    return render('admin/inbox-detail', {
        'title': name_of(data), 'nav': '/admin/inbox', 'r': r, 'answers': answers, 'notes': notes, 'STATUSES': STATUSES, 'counsellors': counsellors(), 'existing': student,
        'help': '<p>Everything the visitor told us. Use <b>Status</b> to track your follow-up, <b>Assign</b> to hand it to a counsellor, and <b>Notes</b> for private remarks – visitors never see notes.</p><p>When they join, click <b>Create student account</b> to copy their details into a new student.</p>'})


def submission(id_):
    r = one('SELECT * FROM submissions WHERE id = ?', id_)
    if not r:
        abort(404)
    return r


@bp.post('/<int:id>/status')
def status(id):
    r = submission(id)
    b = body()
    if not any(s[0] == b.get('status') for s in STATUSES):
        flash('err', 'Choose a valid status.')
        return redirect(f"/admin/inbox/{r['id']}")
    run('UPDATE submissions SET status = ? WHERE id = ?', b['status'], r['id'])
    audit('update', 'submission', r['id'], f"Status of {name_of(parse(r))}: {r['status']} → {b['status']}")
    flash('ok', 'Status updated.')
    return redirect('/admin/inbox' if b.get('back') == 'list' else f"/admin/inbox/{r['id']}")


@bp.post('/<int:id>/assign')
def assign(id):
    r = submission(id)
    uid_raw = body().get('user')
    uid = int(uid_raw) if uid_raw and re.fullmatch(r'\d+', str(uid_raw)) else None
    u = uid and one("SELECT name FROM users WHERE id = ? AND role IN ('admin','staff') AND active = 1", uid)
    if (uid_raw and uid is None) or (uid and not u):
        flash('err', 'Choose a counsellor from the list.')
        return redirect(f"/admin/inbox/{r['id']}")
    run('UPDATE submissions SET assigned_to = ? WHERE id = ?', uid, r['id'])
    audit('update', 'submission', r['id'], f"Assigned {name_of(parse(r))} to {u['name'] if u else 'nobody'}")
    flash('ok', f"Assigned to {u['name']}." if u else 'Now unassigned.')
    return redirect(f"/admin/inbox/{r['id']}")


@bp.post('/<int:id>/note')
def note(id):
    r = submission(id)
    text = str(body().get('note') or '').strip()[:2000]
    if not text:
        flash('err', 'Type a note first.')
        return redirect(f"/admin/inbox/{r['id']}")
    run('INSERT INTO submission_notes (submission_id, author_id, note) VALUES (?,?,?)', r['id'], g.user['id'], text)
    audit('create', 'submission_note', r['id'], f'Added a note on {name_of(parse(r))}')
    flash('ok', 'Note added.')
    return redirect(f"/admin/inbox/{r['id']}")


@bp.post('/<int:id>/delete')
def delete(id):
    if g.user['role'] != 'admin':
        return denied()
    r = submission(id)
    run('DELETE FROM submissions WHERE id = ?', r['id'])
    audit('delete', 'submission', r['id'], f"Deleted {r['form']} from {name_of(parse(r))}")
    flash('ok', 'Deleted.')
    return redirect('/admin/inbox')
