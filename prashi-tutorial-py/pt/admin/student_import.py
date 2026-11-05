"""Import existing students from a spreadsheet saved as CSV.
Step 1 upload -> Step 2 preview (nothing is created, every row's problems are shown) -> Step 3 confirm.
The confirm step re-reads and re-checks the file on the server; the preview is never trusted."""
import re
from datetime import datetime

from flask import Blueprint, g, redirect, request

from .. import pw
from ..audit import audit
from ..db import all_, one, run, tx
from ..student_rules import CLASSES, next_admission_no, read_student
from ..tz import today_local
from ..uploads import read_uploads
from ..web import body, flash, render

bp = Blueprint('student_import', __name__)
MAX_ROWS, MAX_BYTES = 200, 1024 * 1024

COLUMNS = [
    ['name', 'Student name (required)', 'Riya Sharma'], ['class', 'Class: 6 to 12 or “Class 10”', 'Class 10'], ['school', 'School', 'City Public School'],
    ['date_of_birth', 'Date of birth: 2010-05-21 or 21/05/2010', '2010-05-21'], ['parent_name', 'Parent / guardian name', 'Mrs Sharma'],
    ['parent_phone', 'Parent phone (this or parent email is required)', '9876543210'], ['parent_email', 'Parent email', 'parent@example.com'],
    ['student_email', 'Student’s own email (optional, must be unique)', ''],
    ['address', 'Address', ''], ['joined_on', 'Joining date (blank = today)', '2026-04-01'],
    ['batch', 'Batch: its name, or “Course – Batch” exactly as in the admin (blank = not enrolled)', 'JEE 2026-28 Morning'],
    ['admission_no', 'Admission number (blank = we create one)', ''],
    ['fee_total', 'Fee ₹ (blank = the course fee)', '145000'], ['discount', 'Discount ₹', '0'], ['fees_paid_so_far', 'Fees already paid before today, ₹', '50000'],
]
ALIASES = {'student_name': 'name', 'class_level': 'class', 'dob': 'date_of_birth', 'birth_date': 'date_of_birth', 'email': 'student_email',
           'joining_date': 'joined_on', 'date_of_joining': 'joined_on', 'fee': 'fee_total', 'fees': 'fee_total', 'paid': 'fees_paid_so_far',
           'fees_paid': 'fees_paid_so_far', 'phone': 'parent_phone', 'admission_number': 'admission_no', 'admission': 'admission_no'}


def parse_csv(text):
    """Reads CSV text (quotes, commas inside cells, line breaks inside cells, Excel's BOM, Windows line endings, ; separators)."""
    text = text.lstrip('\ufeff') if text.startswith('\ufeff') else text
    first = re.split(r'\r?\n', text)[0] if text else ''
    delim = ',' if ',' in first else (';' if ';' in first else ',')
    rows, row, cur, q, i = [], [], '', False, 0
    while i < len(text):
        c = text[i]
        if q:
            if c == '"':
                if text[i + 1:i + 2] == '"':
                    cur += '"'
                    i += 1
                else:
                    q = False
            else:
                cur += c
        elif c == '"':
            q = True
        elif c == delim:
            row.append(cur)
            cur = ''
        elif c in '\n\r':
            if c == '\r' and text[i + 1:i + 2] == '\n':
                i += 1
            row.append(cur)
            cur = ''
            rows.append(row)
            row = []
        else:
            cur += c
        i += 1
    if cur != '' or row:
        row.append(cur)
        rows.append(row)
    return [r for r in rows if any(str(x).strip() != '' for x in r)]


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[–—]', '-', str(s or '').lower())).strip()


def key(h):
    k = re.sub(r'^_|_$', '', re.sub(r'[^a-z0-9]+', '_', str(h).strip().lower()))
    return ALIASES.get(k, k)


def to_date(v):
    v = str(v or '').strip()
    if not v:
        return {'v': None}
    m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', v)
    if m:
        y, mo, d = m.groups()
    else:
        m = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', v)
        if not m:
            return {'err': f'Date “{v}” is not understood (use 2010-05-21 or 21/05/2010).'}
        d, mo, y = m.groups()
    iso = f'{y}-{mo.zfill(2)}-{d.zfill(2)}'
    try:
        ok = datetime.strptime(iso, '%Y-%m-%d').strftime('%Y-%m-%d') == iso
    except ValueError:
        ok = False
    return {'v': iso} if ok else {'err': f'“{v}” is not a real date.'}


def to_money(v, label):
    v = re.sub(r'[₹,\s]', '', str(v or ''))
    if not v:
        return {'v': None}
    return {'v': int(v)} if re.fullmatch(r'\d{1,9}', v) else {'err': f'{label} must be a whole number of rupees.'}


def analyse(text):
    rows = parse_csv(text)
    if len(rows) < 2:
        return {'fatal': 'The file has no student rows. The first line must be the column names, then one student per line.'}
    head = [key(h) for h in rows[0]]
    if 'name' not in head:
        return {'fatal': 'The first line must contain a “name” column. Download the template to see the exact column names.'}
    if len(rows) - 1 > MAX_ROWS:
        return {'fatal': f'Please import at most {MAX_ROWS} students at a time (your file has {len(rows) - 1}). Split it into smaller files.'}
    known = {c[0] for c in COLUMNS}
    unknown = [h for h in head if h and h not in known]
    batches = all_('SELECT b.id, b.name, b.status, c.name AS course, c.fee_amount FROM batches b JOIN courses c ON c.id = b.course_id')
    seen = {'adm': {}, 'email': {}, 'person': {}}
    out = []
    for idx, cells in enumerate(rows[1:]):
        line, gg, errs = idx + 2, {}, []
        for i, h in enumerate(head):
            if h:
                gg[h] = str(cells[i] if i < len(cells) and cells[i] is not None else '').strip()
        cls = gg.get('class', '')
        if re.fullmatch(r'\d{1,2}', cls):
            cls = 'Class ' + cls
        hit = next((x for x in CLASSES if norm(x) == norm(cls)), None)
        if cls and not hit:
            errs.append(f'Class “{gg.get("class")}” is not recognised (use 6 to 12).')
        dob, joined = to_date(gg.get('date_of_birth')), to_date(gg.get('joined_on'))
        if dob.get('err'):
            errs.append(dob['err'])
        if joined.get('err'):
            errs.append(joined['err'])
        # the same checks as the Add-student form
        v, e2 = read_student({'name': gg.get('name'), 'class_level': hit or '', 'school': gg.get('school'), 'dob': dob.get('v'), 'parent_name': gg.get('parent_name'),
                              'parent_phone': gg.get('parent_phone'), 'parent_email': gg.get('parent_email'), 'email': gg.get('student_email'),
                              'address': gg.get('address'), 'joined_on': joined.get('v') or today_local()}, 0)
        errs.extend(e2.values())
        # batch + fees
        batch = None
        if gg.get('batch'):
            n = norm(gg['batch'])
            m = [b for b in batches if norm(f"{b['course']} - {b['name']}") == n or norm(b['name']) == n]
            if not m:
                errs.append(f'Batch “{gg["batch"]}” was not found. Use the batch name exactly as shown in the admin.')
            elif len(m) > 1:
                errs.append(f'Batch “{gg["batch"]}” matches several batches – write it as “Course – Batch”.')
            elif m[0]['status'] == 'closed':
                errs.append(f"Batch “{m[0]['name']}” is closed.")
            else:
                batch = m[0]
        fee, disc, paid = to_money(gg.get('fee_total'), 'Fee'), to_money(gg.get('discount'), 'Discount'), to_money(gg.get('fees_paid_so_far'), 'Fees paid so far')
        for x in (fee, disc, paid):
            if x.get('err'):
                errs.append(x['err'])
        fee_total, discount, paid_so_far = None, 0, 0
        if not batch and (fee.get('v') is not None or disc.get('v') is not None or paid.get('v') is not None) and not gg.get('batch'):
            errs.append('Fees can only be entered together with a batch.')
        if batch and not fee.get('err') and not disc.get('err') and not paid.get('err'):
            fee_total = fee['v'] if fee.get('v') is not None else (batch['fee_amount'] or 0)
            discount = disc['v'] if disc.get('v') is not None else 0
            paid_so_far = paid['v'] if paid.get('v') is not None else 0
            if discount > fee_total:
                errs.append('Discount is more than the fee.')
            elif paid_so_far > fee_total - discount:
                errs.append('Fees paid so far is more than the fee payable.')
        # admission number + duplicates
        adm = gg.get('admission_no', '')
        if adm and not re.fullmatch(r'[A-Za-z0-9-]{3,20}', adm):
            errs.append('Admission number: 3–20 letters, numbers or dashes.')
        if adm and one('SELECT 1 FROM students WHERE lower(admission_no) = lower(?)', adm):
            errs.append(f'Admission number {adm} is already used.')
        if adm and adm.lower() in seen['adm']:
            errs.append(f"Same admission number as line {seen['adm'][adm.lower()]}.")
        elif adm:
            seen['adm'][adm.lower()] = line
        em = (v['email'] or '').lower()
        if em and em in seen['email']:
            errs.append(f"Same student email as line {seen['email'][em]}.")
        elif em:
            seen['email'][em] = line
        # Duplicate student? Same name + same parent phone (or, with no phone, same parent email) - in the system already or earlier in the file.
        phone = re.sub(r'\D', '', str(v['parent_phone'] or ''))[-10:]
        pemail = (v['parent_email'] or '').lower()
        contact = phone or pemail
        person = norm(v['name']) + '|' + contact
        if contact and one("""SELECT 1 FROM users u JOIN students s ON s.user_id = u.id WHERE lower(u.name) = lower(?) AND (
            (? != '' AND replace(replace(replace(s.parent_phone,' ',''),'-',''),'+','') LIKE ?) OR (? != '' AND lower(s.parent_email) = ?))""",
                           v['name'] or '', phone, '%' + phone, pemail, pemail):
            errs.append('A student with this name and parent contact already exists – skipped to avoid a duplicate.')
        if contact and person in seen['person']:
            errs.append(f"Looks like a duplicate of line {seen['person'][person]}.")
        elif contact:
            seen['person'][person] = line
        out.append({'line': line, 'g': gg, 'v': v, 'adm': adm or None, 'batch': batch, 'feeTotal': fee_total, 'discount': discount,
                    'paidSoFar': paid_so_far, 'errs': list(dict.fromkeys(errs))})
    return {'rows': out, 'unknown': unknown, 'ok': len([r for r in out if not r['errs']])}


# ───── Steps ─────
def page(view, data, status=200):
    return render('admin/' + view, {'nav': '/admin/students', **data}, status)


HELP = '<p>Bring in students you already have, from a spreadsheet.</p><ol style="margin-left:20px"><li><b>Download the template</b>, open it in Excel or Google Sheets, and fill one student per row (delete the sample row).</li><li>Save it as <b>CSV</b> (Excel: File → Save As → “CSV UTF-8”).</li><li><b>Upload</b> it here. You will see a <b>preview</b> – nothing is created yet, and every problem is explained.</li><li>Click <b>Import</b>. Each student gets a login and a temporary password, shown <b>once</b> – print or download that list straight away.</li></ol>'


@bp.get('/', strict_slashes=False)
def index():
    return page('student-import', {'title': 'Import students', 'COLUMNS': COLUMNS, 'error': '', 'help': HELP})


@bp.get('/template.csv')
def template():
    return ('\ufeff' + ','.join(c[0] for c in COLUMNS) + '\r\n', 200,
            {'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="students-template.csv"'})


@bp.post('/preview')
def preview():
    def back(error):
        return page('student-import', {'title': 'Import students', 'COLUMNS': COLUMNS, 'error': error, 'help': HELP}, 422)

    files, err = read_uploads(request, accept='file')
    if err:
        return back('That file is too large.' if err == 'LIMIT_FILE_SIZE' else 'The upload failed. Please try again.')
    f = files[0] if files else None
    if not f or not f.size:
        return back('Choose a CSV file first.')
    if not re.search(r'\.(csv|txt)$', f.originalname, re.I):
        return back('Please upload a .csv file (in Excel: File → Save As → CSV UTF-8).')
    if f.size > MAX_BYTES:
        return back('That file is too large (limit 1 MB).')
    if b'\x00' in f.buffer:
        return back('That does not look like a CSV text file. In Excel use File → Save As → “CSV UTF-8”.')
    text = f.buffer.decode('utf8', errors='replace')
    a = analyse(text)
    if a.get('fatal'):
        return back(a['fatal'])
    return page('student-import-preview', {'title': 'Check before importing', 'a': a, 'csv': text, 'token': None,
                                           'help': '<p>Nothing has been created yet. Rows marked ✘ explain what to fix; you can fix the file and upload again, or import only the good rows now.</p>'})


@bp.post('/confirm')
def confirm():
    text = str(body().get('csv') or '')
    if not text or len(text) > MAX_BYTES:
        flash('err', 'The file data was missing. Please upload it again.')
        return redirect('/admin/students/import')
    a = analyse(text)                                              # re-checked on the server - the preview is never trusted
    if a.get('fatal'):
        flash('err', a['fatal'])
        return redirect('/admin/students/import')
    good = [r for r in a['rows'] if not r['errs']]
    skipped = [r for r in a['rows'] if r['errs']]
    created = []
    for r in good:
        temp = pw.temp_password()
        hashed = pw.hash_password(temp)
        adm = r['adm'] or next_admission_no()
        username = adm.lower()
        if one('SELECT 1 FROM students WHERE lower(admission_no) = ?', username) or one('SELECT 1 FROM users WHERE username = ?', username):
            skipped.append({**r, 'errs': ['Admission number was taken a moment ago.']})
            continue
        with tx():
            v = r['v']
            uid = run("INSERT INTO users (role, name, email, username, password_hash, must_change_password) VALUES ('student',?,?,?,?,1)",
                      v['name'], v['email'], username, hashed).lastrowid
            run('INSERT INTO students (user_id, admission_no, class_level, school, dob, parent_name, parent_phone, parent_email, address, joined_on) VALUES (?,?,?,?,?,?,?,?,?,?)',
                uid, adm, v['class_level'], v['school'], v['dob'], v['parent_name'], v['parent_phone'], v['parent_email'], v['address'], v['joined_on'] or today_local())
            if r['batch']:
                e = run('INSERT INTO enrollments (student_id, batch_id, fee_total, discount) VALUES (?,?,?,?)', uid, r['batch']['id'], r['feeTotal'], r['discount']).lastrowid
                if r['paidSoFar'] > 0:
                    p = run("INSERT INTO payments (enrollment_id, amount, paid_on, mode, note, recorded_by) VALUES (?,?,?,'Imported',?,?)",
                            e, r['paidSoFar'], v['joined_on'] or today_local(), 'Paid before this system (imported)', g.user['id']).lastrowid
                    run('UPDATE payments SET receipt_no = ? WHERE id = ?', 'PT-R-' + str(p).zfill(5), p)
        created.append({'id': uid, 'name': r['v']['name'], 'adm': adm, 'username': username, 'temp': temp, 'batch': r['batch']['name'] if r['batch'] else ''})
    audit('import', 'student', None, f"Imported {len(created)} student(s) from a spreadsheet{', ' + str(len(skipped)) + ' row(s) skipped' if skipped else ''}")
    return page('student-import-done', {'title': 'Import finished', 'created': created, 'skipped': skipped, 'help': ''})
