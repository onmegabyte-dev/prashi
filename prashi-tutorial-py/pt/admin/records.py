"""Tutorial records: study material, notes, test papers, mock results, remarks - each with a
"visible to student" switch, and bulk release."""
import math
import re
from pathlib import Path
from urllib.parse import urlencode

from flask import Blueprint, abort, g, redirect, request, send_from_directory

from ..audit import audit
from ..db import all_, one, run, tx
from ..admin.student_import import parse_csv
from ..tz import today_local, utc_stamp, valid_day
from ..uploads import PRIVATE_DIR, UploadError, read_uploads, remove_private, safe_name, save_document
from ..web import back_url, body, flash, render

bp = Blueprint('records', __name__)
TYPES = [['material', 'Study material'], ['notes', 'Notes'], ['test_paper', 'Test paper'], ['mock_result', 'Result'], ['remark', 'Remark']]
TYPE_LABEL = dict(TYPES)


def batch_students(bid):
    return all_("SELECT u.id AS v, u.name || ' (' || s.admission_no || ')' AS l, s.admission_no AS adm, u.name AS n FROM enrollments e JOIN students s ON s.user_id = e.student_id JOIN users u ON u.id = s.user_id "
                "WHERE e.batch_id = ? AND e.status = 'active' AND u.role = 'student' ORDER BY u.name", bid)


def batches():
    return all_("SELECT b.id AS v, c.name || ' – ' || b.name AS l FROM batches b JOIN courses c ON c.id = b.course_id ORDER BY c.name, b.name")


# ───── List ─────
@bp.get('/', strict_slashes=False)
def list_():
    a = request.args
    f = {'type': str(a.get('type', '')), 'vis': str(a.get('vis', '')), 'student': str(a.get('student', '')), 'batch': str(a.get('batch', '')), 'q': str(a.get('q', '')).strip()[:100]}
    # The student filter only exists once a batch is chosen, and only lists that batch's students
    batch_studs = batch_students(int(f['batch'])) if re.fullmatch(r'\d+', f['batch']) else []
    if f['student'] not in [str(x['v']) for x in batch_studs]:
        f['student'] = ''
    where, args = [], []
    if any(t[0] == f['type'] for t in TYPES):
        where.append('r.type = ?')
        args.append(f['type'])
    if f['vis'] == 'visible':
        where.append('r.visible_to_student = 1')
    elif f['vis'] == 'hidden':
        where.append('r.visible_to_student = 0')
    if re.fullmatch(r'\d+', f['student']):
        where.append('r.student_id = ?')
        args.append(int(f['student']))
    if re.fullmatch(r'\d+', f['batch']) and not f['student']:
        where.append("(r.batch_id = ? OR r.student_id IN (SELECT student_id FROM enrollments WHERE batch_id = ? AND status = 'active'))")
        args += [int(f['batch'])] * 2
    if f['q']:
        where.append('(r.title LIKE ? OR r.body LIKE ? OR u.name LIKE ?)')
        args += ['%' + f['q'] + '%'] * 3
    W = ' WHERE ' + ' AND '.join(where) if where else ''
    sort = a.get('sort') if a.get('sort') in ('title', 'type', 'record_date', 'created_at') else 'created_at'
    dir_ = 'asc' if a.get('dir') == 'asc' else 'desc'
    FROM = 'FROM records r LEFT JOIN users u ON u.id = r.student_id LEFT JOIN batches b ON b.id = r.batch_id'
    per = 25
    total = one(f'SELECT COUNT(*) n {FROM}{W}', *args)['n']
    pages = max(1, math.ceil(total / per))
    try:
        page = int(a.get('page', ''))
    except ValueError:
        page = 1
    page = min(pages, max(1, page))
    rows = all_(f'SELECT r.*, u.name AS student_name, b.name AS batch_name {FROM}{W} ORDER BY r.{sort} {dir_}, r.id DESC LIMIT {per} OFFSET {(page - 1) * per}', *args)
    p = [(k, v) for k, v in f.items() if v]
    return render('admin/records', {
        'title': 'Tutorial records', 'nav': '/admin/records', 'rows': rows, 'total': total, 'page': page, 'pages': pages, 'f': f, 'sort': sort, 'dir': dir_,
        'TYPES': TYPES, 'typeLabel': TYPE_LABEL, 'students': batch_studs, 'batches': batches(), 'qs': urlencode(p), 'qsp': urlencode(p + [('sort', sort), ('dir', dir_)]),
        'help': '<p>Study material, notes, test papers, mock-test results and remarks for your students.</p><ul><li>Each record has a <b>“Visible to student”</b> switch. Students only ever see records that are switched on.</li><li>New records start <b>hidden</b>, so you can check them first.</li><li>To publish many at once: tick them and click <b>Release selected</b>, or use <b>Release a whole batch</b> at the bottom.</li><li>A record can be for <b>one student</b> (like a personal remark) or for a <b>whole batch</b> (like class notes).</li></ul>'})


# ───── Bulk release / hide ─────
def set_visible(ids, on):
    at = utc_stamp() if on else None
    for id_ in ids:
        run('UPDATE records SET visible_to_student = ?, released_at = ? WHERE id = ?', on, at, id_)


@bp.post('/bulk')
def bulk():
    b = body()
    ids = [int(x) for x in b.getlist('ids') if re.fullmatch(r'\d+', str(x))][:500]
    act = b.get('action')
    if not ids:
        flash('err', 'Tick at least one record first.')
    elif act in ('release', 'hide'):
        set_visible(ids, 1 if act == 'release' else 0)
        n = len(ids)
        audit('update', 'record', ','.join(map(str, ids)), f"{'Released to students' if act == 'release' else 'Hid from students'}: {n} record(s)")
        flash('ok', f"{n} record{'' if n == 1 else 's'} {'released to students' if act == 'release' else 'hidden from students'}.")
    return redirect(back_url('/admin/records'))


@bp.post('/release-batch')
def release_batch():
    b = body()
    bid = int(b['batch_id']) if re.fullmatch(r'\d+', b.get('batch_id') or '') else None
    bt = bid and one('SELECT name FROM batches WHERE id = ?', bid)
    if not bt:
        flash('err', 'Choose a batch.')
        return redirect('/admin/records')
    type_ok = any(t[0] == b.get('type') for t in TYPES)
    ids = [r['id'] for r in all_(
        f"SELECT id FROM records WHERE visible_to_student = 0 AND (batch_id = ? OR student_id IN (SELECT student_id FROM enrollments WHERE batch_id = ? AND status = 'active')){' AND type = ?' if type_ok else ''}",
        bid, bid, *([b['type']] if type_ok else []))]
    set_visible(ids, 1)
    audit('update', 'record', bid, f"Released {len(ids)} hidden record(s) to batch “{bt['name']}”{' (' + TYPE_LABEL[b['type']] + ' only)' if type_ok else ''}")
    n = len(ids)
    flash('ok', f"Released {n} record{'' if n == 1 else 's'} to {bt['name']}." if n else 'Nothing to release – every record for this batch is already visible.')
    return redirect('/admin/records')


# ───── Result sheets ─────
# One uploaded sheet (student id, marks, out of) becomes one private record per student, so each student sees only their own marks.
RESULT_COLS = {'id': ['student id', 'studentid', 'id', 'admission no', 'admission number', 'admission_no', 'roll no'],
               'marks': ['marks', 'marks obtained', 'obtained', 'score', 'full mark', 'full marks', 'mark'],
               'out_of': ['out of', 'outof', 'max', 'maximum', 'max marks', 'total', 'total marks']}


def sheet_rows(f):
    """Rows of a .csv or .xlsx upload as lists of strings."""
    name = f.originalname.lower()
    if name.endswith('.xlsx'):
        import io
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(f.buffer), read_only=True, data_only=True).active
        return [['' if c is None else (str(int(c)) if isinstance(c, float) and c == int(c) else str(c)) for c in row] for row in ws.iter_rows(values_only=True)
                if any(c not in (None, '') for c in row)]
    if name.endswith(('.csv', '.txt')):
        return parse_csv(f.buffer.decode('utf-8-sig', errors='replace'))
    return None


def read_results(f, batch_id):
    """Returns (error text, [(student_user_id, marks, out_of), ...]). Nothing is saved if any row is wrong."""
    if not f:
        return 'Upload the Excel marksheet.', []
    try:
        rows = sheet_rows(f)
    except Exception:                                                 # unreadable / corrupt spreadsheet
        return 'That file could not be read. Save it as .csv or .xlsx and try again.', []
    if rows is None:
        return 'A result sheet must be an Excel (.xlsx) or .csv file.', []
    if len(rows) < 2 or len(rows) > 501:
        return 'The sheet needs a heading row and 1 to 500 students.', []
    head = [re.sub(r'[\s_]+', ' ', str(h).strip().lower()) for h in rows[0]]
    idx = {k: next((i for i, h in enumerate(head) if h in v), None) for k, v in RESULT_COLS.items()}
    if None in idx.values():
        return 'The first row must have the headings: Student ID, Marks, Out of.', []
    roster = {r['admission_no'].lower(): r['user_id'] for r in all_(
        "SELECT s.admission_no, s.user_id FROM enrollments e JOIN students s ON s.user_id = e.student_id WHERE e.batch_id = ? AND e.status = 'active'", batch_id)}
    out, seen, problems = [], set(), []
    for n, row in enumerate(rows[1:], start=2):
        cell = lambda k: str(row[idx[k]]).strip() if idx[k] < len(row) else ''       # noqa: E731
        sid, marks, mx = cell('id').lower(), numval(cell('marks')), numval(cell('out_of'))
        ok = lambda x: x is not None and math.isfinite(x)                              # noqa: E731
        if sid not in roster:
            problems.append(f'Row {n}: “{cell("id")}” is not a student of this batch.')
        elif sid in seen:
            problems.append(f'Row {n}: “{cell("id")}” appears twice.')
        elif not ok(marks) or not ok(mx) or mx <= 0 or marks < 0 or marks > mx:
            problems.append(f'Row {n}: marks must be a number from 0 up to “Out of” (which must be above zero).')
        else:
            seen.add(sid)
            out.append((roster[sid], marks, mx))
    if problems:
        return ' '.join(problems[:8]) + (f' …and {len(problems) - 8} more.' if len(problems) > 8 else '') + ' Nothing was saved.', []
    return '', out


@bp.get('/result-template.xlsx')
def result_template():
    """An Excel marksheet with the chosen batch's students already filled in; the teacher only types Marks and Out of."""
    import io
    from flask import Response
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    bid = request.args.get('batch', '')
    rows = batch_students(int(bid)) if re.fullmatch(r'\d+', bid) else []
    wb = Workbook()
    ws = wb.active
    ws.title = 'Marksheet'
    ws.append(['Student ID', 'Name', 'Marks', 'Out of'])
    for c in ws[1]:
        c.font, c.fill, c.alignment = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='3B6CFF'), Alignment(horizontal='center')
    for x in rows:
        ws.append([x['adm'], x['n'], None, None])
    last = max(len(rows) + 1, 2)
    for col, w in zip('ABCD', (16, 32, 12, 12)):
        ws.column_dimensions[col].width = w
    for r in range(2, last + 1):
        ws.cell(r, 1).number_format = '@'                                        # keep admission numbers as text
        for col in (1, 2):
            ws.cell(r, col).fill = PatternFill('solid', fgColor='EEF1FF')
    dv = DataValidation(type='decimal', operator='greaterThanOrEqual', formula1='0', allow_blank=True,
                        errorTitle='Marks', error='Enter a number, 0 or more.')
    ws.add_data_validation(dv)
    dv.add(f'C2:D{max(last, 500)}')
    ws.freeze_panes = 'A2'
    note = wb.create_sheet('How to fill')
    for line in ('1. Type each student\'s marks in the Marks column and the full marks of the test in Out of (for example 78 and 100).',
                 '2. Leave the Student ID column as it is. The Name column is only for your reference.',
                 '3. Save the file as .xlsx and upload it on the Add record page (type: Result).'):
        note.append([line])
    note.column_dimensions['A'].width = 110
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), 200, {'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                          'Content-Disposition': 'attachment; filename="marksheet-template.xlsx"'})


# ───── Add / edit ─────
def form_page(rec, vals, errs, status=200):
    return render('admin/record-form', {
        'title': 'Edit record' if rec else 'Add record', 'nav': '/admin/records', 'rec': rec, 'vals': vals, 'errs': errs, 'TYPES': TYPES, 'batches': batches(),
        'action': f"/admin/records/{rec['id']}/edit" if rec else '/admin/records/new',
        'help': '<p>Choose the batch, what kind it is, then add a file and/or some text. Every student in that batch can see it once you release it.</p><ul><li><b>Result:</b> upload a sheet with the columns <b>Student ID, Marks, Out of</b>. Each student sees only their own marks.</li><li>Leave “Visible to student” <b>off</b> until you are ready – you can release it later.</li><li>Files: PDF, Word, PowerPoint, Excel, text, ZIP, JPG or PNG, up to 20 MB. Only the right students can download them.</li></ul>'}, status)


@bp.get('/new')
def new():
    bid = request.args.get('batch', '') if re.fullmatch(r'\d+', request.args.get('batch', '')) else ''
    return form_page(None, {'batch_id': bid, 'record_date': today_local(), 'type': 'material'}, {})


@bp.get('/<int:id>/edit')
def edit(id):
    rec = one('SELECT r.*, u.name AS student_name FROM records r LEFT JOIN users u ON u.id = r.student_id WHERE r.id = ?', id)
    if not rec:
        abort(404)
    return form_page(rec, rec, {})


def numval(x):
    """Number(x) for form text: None when blank, nan when not a number."""
    if x is None or str(x).strip() == '':
        return None
    try:
        return float(x)
    except ValueError:
        return float('nan')


def read_record(files, rec):
    b, errs = body(), {}
    typ = b.get('type') if any(t[0] == b.get('type') for t in TYPES) else None
    batch_id = int(b['batch_id']) if re.fullmatch(r'\d+', b.get('batch_id') or '') and one('SELECT 1 FROM batches WHERE id = ?', int(b['batch_id'])) else None
    title, text = str(b.get('title') or '').strip(), str(b.get('body') or '').strip() or None
    if not typ:
        errs['type'] = 'Choose a type.'
    if not batch_id:
        errs['batch_id'] = 'Choose a batch.'
    if not title or len(title) > 200:
        errs['title'] = 'Give it a title (up to 200 characters).'
    if text and len(text) > 5000:
        errs['body'] = 'Too long (5000 characters max).'
    day = str(b.get('record_date') or '').strip() or None
    if day and not valid_day(day):
        errs['record_date'] = 'Enter a valid date.'
    file = next((f for f in files if f.fieldname == 'file' and f.size), None)
    has_file = bool(file) or bool(rec and rec['file_path'] and not b.get('_remove_file'))
    if typ == 'mock_result':
        pass                                  # the sheet is checked in save_record
    elif typ in ('material', 'notes', 'test_paper') and not has_file and not text:
        errs['file'] = 'Attach a file or write some text.'
    if typ == 'remark' and not text:
        errs['body'] = 'Write the remark.'
    return errs, {'type': typ, 'batch_id': batch_id, 'title': title, 'body': text,
                  'record_date': day, 'visible': 1 if b.get('visible_to_student') else 0}, file


def save_record(rec):
    files, upload_err = read_uploads(request)
    errs, d, file = read_record(files, rec)
    b = body()
    if upload_err:
        errs['file'] = 'That file is too large (limit 20 MB).' if upload_err == 'LIMIT_FILE_SIZE' else 'The upload failed. Please try again.'
    if rec and rec['type'] == 'mock_result' and rec['student_id']:        # one student's result row: only the wording, date and visibility can change
        return save_result_row(rec, errs, d)
    results = []
    if not rec and d['type'] == 'mock_result' and not errs:
        msg, results = read_results(file, d['batch_id'])
        if msg:
            errs['file'] = msg
    stored = None
    if not errs and file and d['type'] != 'mock_result':
        try:
            stored, _ = save_document(file)
        except UploadError as e:
            errs['file'] = str(e)
    if errs:
        return form_page(rec, b, errs, 422)
    at = ((rec and rec['released_at']) or utc_stamp()) if d['visible'] else None
    if results:
        with tx():
            for uid, marks, mx in results:
                run('INSERT INTO records (type, title, body, student_id, batch_id, score, max_score, record_date, visible_to_student, released_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    'mock_result', d['title'], d['body'], uid, d['batch_id'], marks, mx, d['record_date'], d['visible'], at, g.user['id'])
        audit('create', 'record', d['batch_id'], f"Added results “{d['title']}” for {len(results)} student(s) ({'visible' if d['visible'] else 'hidden'} to students)")
        flash('ok', f"Results saved for {len(results)} student{'' if len(results) == 1 else 's'}." + ('' if d['visible'] else ' They are hidden until you release them.'))
        return redirect('/admin/records')
    file_path = rec['file_path'] if rec else None
    if stored:
        if file_path:
            remove_private(file_path)
        file_path = stored
    elif rec and b.get('_remove_file') and file_path:
        remove_private(file_path)
        file_path = None
    if rec:
        run('UPDATE records SET type=?, title=?, body=?, file_path=?, student_id=NULL, batch_id=?, score=NULL, max_score=NULL, record_date=?, visible_to_student=?, released_at=? WHERE id=?',
            d['type'], d['title'], d['body'], file_path, d['batch_id'], d['record_date'], d['visible'], at, rec['id'])
        vis = (' – now visible to student' if d['visible'] else ' – now hidden from student') if d['visible'] != rec['visible_to_student'] else ''
        audit('update', 'record', rec['id'], f"Edited {TYPE_LABEL[d['type']].lower()} “{d['title']}”{vis}")
        flash('ok', 'Record saved.')
    else:
        r = run('INSERT INTO records (type, title, body, file_path, batch_id, record_date, visible_to_student, released_at, created_by) VALUES (?,?,?,?,?,?,?,?,?)',
                d['type'], d['title'], d['body'], file_path, d['batch_id'], d['record_date'], d['visible'], at, g.user['id'])
        audit('create', 'record', r.lastrowid, f"Added {TYPE_LABEL[d['type']].lower()} “{d['title']}” ({'visible' if d['visible'] else 'hidden'} to student)")
        flash('ok', 'Record added and visible to the student.' if d['visible'] else 'Record added. It is hidden from the student until you release it.')
    return redirect('/admin/records')


def save_result_row(rec, errs, d):
    errs.pop('file', None)
    errs.pop('batch_id', None)
    if errs:
        return form_page(rec, {**rec, **body()}, errs, 422)
    at = (rec['released_at'] or utc_stamp()) if d['visible'] else None
    run('UPDATE records SET title=?, body=?, record_date=?, visible_to_student=?, released_at=? WHERE id=?', d['title'], d['body'], d['record_date'], d['visible'], at, rec['id'])
    audit('update', 'record', rec['id'], f"Edited result “{d['title']}”")
    flash('ok', 'Record saved.')
    return redirect('/admin/records')


@bp.post('/new')
def new_post():
    return save_record(None)


@bp.post('/<int:id>/edit')
def edit_post(id):
    rec = one('SELECT * FROM records WHERE id = ?', id)
    if not rec:
        abort(404)
    return save_record(rec)


@bp.post('/<int:id>/toggle')
def toggle(id):
    rec = one('SELECT * FROM records WHERE id = ?', id)
    if not rec:
        abort(404)
    on = 0 if rec['visible_to_student'] else 1
    set_visible([rec['id']], on)
    audit('update', 'record', rec['id'], f"{'Released to student' if on else 'Hidden from student'}: “{rec['title']}”")
    return redirect(back_url('/admin/records'))


@bp.post('/<int:id>/delete')
def delete(id):
    rec = one('SELECT * FROM records WHERE id = ?', id)
    if not rec:
        abort(404)
    run('DELETE FROM records WHERE id = ?', rec['id'])
    if rec['file_path']:
        remove_private(rec['file_path'])
    audit('delete', 'record', rec['id'], f"Deleted {TYPE_LABEL[rec['type']].lower()} “{rec['title']}”")
    flash('ok', 'Record deleted.')
    return redirect(back_url('/admin/records'))


@bp.get('/<int:id>/file')
def file_(id):
    rec = one('SELECT * FROM records WHERE id = ?', id)
    if not rec or not safe_name(rec['file_path']):
        abort(404)
    name = re.sub(r'[^\w\- ]+', '', rec['title']).strip()[:80] or 'file'
    resp = send_from_directory(PRIVATE_DIR, rec['file_path'], as_attachment=True, download_name=name + Path(rec['file_path']).suffix)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp
