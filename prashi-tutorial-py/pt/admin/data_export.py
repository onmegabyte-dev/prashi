"""Admin "Data export": one .xlsx file per database table, plus a ZIP of all of them.
Mounted at /admin/data-export, admin role only. Files are generated fresh from the live database."""
import io
import re
import zipfile
from datetime import date

from flask import Blueprint, Response, abort
from openpyxl import Workbook
from openpyxl.styles import Font

from ..audit import audit
from ..db import all_, one
from ..web import check_role, render

bp = Blueprint('data_export', __name__)


@bp.before_request
def only_admin():                                                   # enforced on the server for every route below
    return check_role('admin')


# Columns that must never leave the server, even to an admin.
HIDDEN_COLUMNS = {'users': ['password_hash'], 'password_resets': ['token_hash']}

# Plain-English names and descriptions shown on the export page.
TABLE_INFO = {
    'users': ['Login accounts', 'Admin, staff and student logins (passwords are never exported).'],
    'password_resets': ['Password reset requests', 'Reset requests and when they expire (secret tokens are never exported).'],
    'faculty': ['Faculty', 'Teachers shown on the website.'],
    'courses': ['Courses', 'All courses, including hidden ones.'],
    'batches': ['Batches', 'Batches with start date, timing, seats and status.'],
    'testimonials': ['Testimonials', 'Student quotes and approval status.'],
    'results': ['Results', 'Rank holders and yearly success figures.'],
    'faqs': ['FAQs', 'Questions and answers.'],
    'notices': ['Notices', 'Public and student-only announcements.'],
    'articles': ['Articles', 'Blog and resource articles.'],
    'settings': ['Site settings', 'Contact details, social links, banner text.'],
    'holidays': ['Holidays', 'Closure dates.'],
    'form_fields': ['Form fields', 'Fields on the admission, enquiry, counselling and contact forms.'],
    'submissions': ['Enquiries and admissions', 'Every form submission with status and assignee.'],
    'submission_notes': ['Internal notes', 'Notes staff added to enquiries.'],
    'students': ['Student profiles', 'Admission number, class, parent contact.'],
    'enrollments': ['Enrolments', 'Which student is in which batch, and fee totals.'],
    'payments': ['Fee payments', 'Every payment recorded.'],
    'records': ['Tutorial records', 'Materials, notes, papers, mock results and remarks.'],
    'attendance': ['Attendance', 'Daily attendance per student.'],
    'doubts': ['Student doubts', 'Questions students asked and the replies.'],
    'audit_log': ['Activity log', 'Who changed what, and when.'],
    'drafts': ['Unpublished drafts', 'Edits saved for preview but not yet published.'],
}


def safe_cell(v):
    """Spreadsheet apps run text that starts with = + - @ as a formula. Neutralise it."""
    return "'" + v if isinstance(v, str) and re.match(r'[=+\-@\t\r]', v) else v


def list_tables():
    # Table names come from the database itself, never from the URL, so they can't be injected.
    return [r['name'] for r in all_("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'sessions' ORDER BY name")]


def build_workbook(table):
    hidden = HIDDEN_COLUMNS.get(table, [])
    cols = [c['name'] for c in all_(f'PRAGMA table_info("{table}")') if c['name'] not in hidden]
    rows = all_(f"SELECT {','.join(chr(34) + c + chr(34) for c in cols)} FROM \"{table}\"")
    wb = Workbook()
    wb.properties.creator = 'Prashi Tutorial'
    ws = wb.active
    ws.title = table[:31]
    ws.append(cols)
    for i, c in enumerate(cols):
        ws.cell(row=1, column=i + 1).font = Font(bold=True)
        ws.column_dimensions[ws.cell(row=1, column=i + 1).column_letter].width = min(40, max(12, len(c) + 4))
    ws.freeze_panes = 'A2'
    for r in rows:
        ws.append([safe_cell(r[c]) for c in cols])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def stamp():
    return date.today().isoformat()


@bp.get('/', strict_slashes=False)
def index():
    tables = [{'name': t, 'title': TABLE_INFO.get(t, [t])[0], 'help': (TABLE_INFO.get(t) or [None, ''])[1], 'rows': one(f'SELECT COUNT(*) n FROM "{t}"')['n']} for t in list_tables()]
    return render('admin/data-export', {
        'title': 'Download your data', 'nav': '/admin/data-export', 'tables': tables,
        'help': '<p>Each box is one table of your data. Click <b>Download Excel</b> to get it as a spreadsheet, or download all of them in one ZIP file. Files are created the moment you click, so they are always up to date. Passwords are never included.</p>'})


@bp.get('/all.zip')
def all_zip():
    audit('export', 'all tables')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for t in list_tables():
            z.writestr(f'{t}.xlsx', build_workbook(t))
    return Response(buf.getvalue(), mimetype='application/zip', headers={'Content-Disposition': f'attachment; filename="prashi-tutorial-all-data-{stamp()}.zip"'})


@bp.get('/<table>.xlsx')
def one_table(table):
    if table not in list_tables():
        return Response('No such table', 404, mimetype='text/html')
    audit('export', table)
    return Response(build_workbook(table), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="{table}-{stamp()}.xlsx"'})
