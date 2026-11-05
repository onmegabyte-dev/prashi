"""Quick self-check of the whole site against a throw-away database.   Run:  python tests/test_site.py
(Uses a temporary database and removes any files it uploads; your real data is never touched.)"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = tempfile.mkdtemp()
os.environ.update(DB_FILE=os.path.join(TMP, 'test.db'), SESSION_SECRET='t' * 40, FORM_RATE_LIMIT='1000')
os.environ.pop('NODE_ENV', None)
os.environ.pop('APP_ENV', None)

from app import app  # noqa: E402
from pt import pw  # noqa: E402
from pt.db import one, run  # noqa: E402

PASS = 'correct horse battery 1'
PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63f8cfc0f01f0005850180aa8b6e210000000049454e44ae426082')


def mk(role, name, email, username=None):
    return run('INSERT INTO users (role,name,email,username,password_hash,must_change_password) VALUES (?,?,?,?,?,0)',
               role, name, email, username, pw.hash_password(PASS)).lastrowid


class Browser:
    def __init__(self):
        self.c = app.test_client()

    def token(self):
        return re.search(r'csrf-token" content="([a-f0-9]+)"', self.c.get('/').text).group(1)

    def post(self, url, data=None, **kw):
        return self.c.post(url, data={'_csrf': self.token(), **(data or {})}, **kw)

    def login(self, who, password=PASS):
        return self.post('/login', {'identifier': who, 'password': password})


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mk('admin', 'Test Admin', 'admin@test.example')
        mk('staff', 'Test Staff', 'staff@test.example')
        sid = mk('student', 'Test Pupil', None, 'pt000001')
        run("INSERT INTO students (user_id, admission_no, class_level, parent_phone) VALUES (?, 'PT000001', 'Class 10', '9876543210')", sid)
        cls.before_files = {p: set(os.listdir(ROOT / p)) for p in ('uploads/public', 'storage/private')}

    @classmethod
    def tearDownClass(cls):
        for p, was in cls.before_files.items():
            for f in set(os.listdir(ROOT / p)) - was:
                (ROOT / p / f).unlink(missing_ok=True)

    def test_public_pages(self):
        b = Browser().c
        for p in ['/', '/about', '/courses', '/courses/jee', '/faculty', '/results', '/resources', '/admissions', '/contact', '/privacy', '/terms', '/login', '/forgot']:
            r = b.get(p)
            self.assertEqual(r.status_code, 200, p)
            self.assertIn('Prashi Tutorial', r.text, p)
        self.assertEqual(b.get('/courses/nope').status_code, 404)
        self.assertIn('/courses/jee', b.get('/sitemap.xml').text)
        self.assertIn('Disallow: /admin', b.get('/robots.txt').text)
        self.assertEqual(b.get('/healthz').text, 'ok')
        self.assertIn("script-src 'self'", b.get('/').headers['Content-Security-Policy'])

    def test_forms_need_token_and_consent(self):
        b = Browser()
        good = {'student_name': 'Test Student', 'phone': '+91 98765 43210', 'email': 'a@b.co', 'class_level': 'Class 10', 'course': 'jee', 'consent': True}
        self.assertEqual(b.c.post('/forms/admission', json=good).status_code, 403)
        h = {'x-csrf-token': b.token()}
        self.assertEqual(b.c.post('/forms/admission', json={**good, 'consent': False}, headers=h).status_code, 422)
        self.assertEqual(b.c.post('/forms/admission', json={**good, 'phone': 'abc'}, headers=h).status_code, 422)
        n = one('SELECT COUNT(*) n FROM submissions')['n']
        self.assertEqual(b.c.post('/forms/admission', json=good, headers=h).status_code, 200)
        self.assertEqual(one('SELECT COUNT(*) n FROM submissions')['n'], n + 1)

    def test_access_control(self):
        anon = Browser()
        for u in ['/admin', '/admin/students', '/admin/c/courses', '/admin/settings', '/portal']:
            r = anon.c.get(u)
            self.assertEqual(r.status_code, 302, u)
            self.assertTrue(r.headers['Location'].startswith('/login'), u)
        stu = Browser()
        self.assertEqual(stu.login('pt000001').headers['Location'], '/portal')
        self.assertEqual(stu.c.get('/portal').status_code, 200)
        for u in ['/admin', '/admin/students', '/admin/c/courses', '/admin/data-export']:
            self.assertEqual(stu.c.get(u).status_code, 403, u)
        staff = Browser()
        staff.login('staff@test.example')
        self.assertEqual(staff.c.get('/admin/students').status_code, 200)
        self.assertEqual(staff.c.get('/admin/settings').status_code, 403)

    def test_login_rules(self):
        b = Browser()
        r = b.login('admin@test.example', 'wrong password')
        self.assertEqual(r.status_code, 401)
        self.assertIn('Incorrect email/username or password', r.text)
        self.assertEqual(Browser().c.post('/login', data={'identifier': 'admin@test.example', 'password': PASS}).status_code, 403)
        self.assertEqual(b.post('/login', {'identifier': 'admin@test.example', 'password': PASS, 'next': '//evil.example/x'}).headers['Location'], '/admin')
        self.assertTrue(one("SELECT password_hash h FROM users WHERE email='admin@test.example'")['h'].startswith('$argon2id$'))

    def test_admin_screens_and_content(self):
        a = Browser()
        a.login('admin@test.example')
        for u in ['/admin', '/admin/inbox', '/admin/students', '/admin/students/new', '/admin/students/import', '/admin/records', '/admin/attendance', '/admin/doubts',
                  '/admin/forms', '/admin/settings', '/admin/pages', '/admin/users', '/admin/activity', '/admin/data-export',
                  *[f'/admin/c/{k}' for k in ('courses', 'batches', 'faculty', 'testimonials', 'results', 'faqs', 'notices', 'articles', 'holidays')],
                  '/admin/c/courses/1/edit', '/admin/preview/courses/1']:
            self.assertEqual(a.c.get(u).status_code, 200, u)
        r = a.post('/admin/c/courses/new', {'name': 'ZZ Test', 'fee_amount': '-5'})
        self.assertEqual(r.status_code, 422)
        r = a.post('/admin/c/courses/new', {'name': 'ZZ Test', 'fee_amount': '1000', 'description_html': '<p>Hi</p><script>alert(1)</script>', 'publish': '0'})
        self.assertEqual(r.status_code, 302)
        c = one("SELECT * FROM courses WHERE name = 'ZZ Test'")
        self.assertEqual(c['visible'], 0)
        self.assertNotIn('<script', c['description_html'])
        self.assertEqual(Browser().c.get('/courses/' + c['slug']).status_code, 404)        # drafts are hidden
        a.post(f"/admin/c/courses/{c['id']}/toggle")
        self.assertEqual(Browser().c.get('/courses/' + c['slug']).status_code, 200)

    def test_student_fees_and_private_files(self):
        a = Browser()
        a.login('admin@test.example')
        r = a.post('/admin/students/new', {'name': 'ZZ Child', 'class_level': 'Class 10', 'parent_phone': '98765 43211', 'batch_id': '1'})
        self.assertEqual(r.status_code, 200)
        self.assertRegex(r.text, r'class="secret">[^<]{12,}<')
        kid = one("SELECT id FROM users WHERE name = 'ZZ Child'")
        en = one('SELECT id FROM enrollments WHERE student_id = ?', kid['id'])
        a.post(f"/admin/students/{kid['id']}/enrollment/{en['id']}/payments", {'amount': '50000', 'paid_on': '2026-10-20', 'mode': 'UPI'})
        self.assertIn('95,000', a.c.get(f"/admin/students/{kid['id']}").text)           # Indian number grouping: 1,45,000 - 50,000
        r = a.post('/admin/records/new?_csrf=' + a.token(), {'type': 'material', 'target': 'batch', 'batch_id': '1', 'title': 'ZZ Notes', 'file': (__import__('io').BytesIO(b'%PDF-1.4'), 'n.pdf')},
                   content_type='multipart/form-data')
        rec = one("SELECT * FROM records WHERE title = 'ZZ Notes'")
        self.assertIsNotNone(rec, r.text[:200])
        self.assertEqual(Browser().c.get('/' + rec['file_path']).status_code, 404)        # private files are never reachable by URL
        self.assertEqual(Browser().c.get('/uploads/' + rec['file_path']).status_code, 404)

    def test_result_sheet_is_private_per_student(self):
        import io
        a = Browser()
        a.login('admin@test.example')
        for n in ('ZZ Ann', 'ZZ Ben'):
            a.post('/admin/students/new', {'name': n, 'class_level': 'Class 10', 'parent_phone': '98765 43212', 'batch_id': '1'})
        ann, ben = (one("SELECT u.id, s.admission_no FROM users u JOIN students s ON s.user_id = u.id WHERE u.name = ?", n) for n in ('ZZ Ann', 'ZZ Ben'))

        def upload(csv):
            return a.post('/admin/records/new?_csrf=' + a.token(), {'type': 'mock_result', 'batch_id': '1', 'title': 'ZZ Mock 1', 'visible_to_student': '1',
                                                                 'file': (io.BytesIO(csv.encode()), 'r.csv')}, content_type='multipart/form-data')
        bad = upload(f"Student ID,Marks,Out of\n{ann['admission_no']},50,100\nNOPE,1,2\n")
        self.assertEqual(bad.status_code, 422)
        self.assertIsNone(one("SELECT 1 FROM records WHERE title = 'ZZ Mock 1'"))          # one bad row saves nothing
        self.assertEqual(upload(f"Student ID,Name,Marks,Out of\n{ann['admission_no']},x,78,100\n{ben['admission_no']},y,45.5,50\n").status_code, 302)
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.append(['Student ID', 'Name', 'Marks', 'Out of'])
        wb.active.append([ann['admission_no'], 'Ann', 91, 100])
        buf = io.BytesIO()
        wb.save(buf)
        r = a.post('/admin/records/new?_csrf=' + a.token(), {'type': 'mock_result', 'batch_id': '1', 'title': 'ZZ Mock XL', 'file': (io.BytesIO(buf.getvalue()), 'm.xlsx')}, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(one("SELECT score, max_score FROM records WHERE title = 'ZZ Mock XL'")['score'], 91)
        tpl = a.c.get('/admin/records/result-template.xlsx?batch=1')
        self.assertEqual((tpl.status_code, tpl.data[:2]), (200, b'PK'))
        from pt.routes_portal import visible_records
        with app.test_request_context():
            mine = visible_records(ann['id'], "AND r.type = 'mock_result'")
            theirs = visible_records(ben['id'], "AND r.type = 'mock_result'")
        self.assertEqual([(r['score'], r['max_score']) for r in mine if r['title'] == 'ZZ Mock 1'], [(78.0, 100.0)])
        self.assertEqual([(r['score'], r['max_score']) for r in theirs if r['title'] == 'ZZ Mock 1'], [(45.5, 50.0)])

    def test_admin_can_clear_activity_log(self):
        a = Browser()
        a.login('admin@test.example')
        self.assertEqual(a.post('/admin/activity/clear', {'older_than': 'all'}).status_code, 302)
        left = [r['summary'] for r in __import__('pt.db', fromlist=['all_']).all_('SELECT summary FROM audit_log')]
        self.assertEqual(len(left), 1)                                                     # only the record of the clearing remains
        self.assertIn('Cleared', left[0])
        staff = Browser()
        staff.login('staff@test.example')
        self.assertEqual(staff.post('/admin/activity/clear', {'older_than': 'all'}).status_code, 403)

    def test_question_bank(self):
        import io
        import zipfile
        from pt.db import all_
        a = Browser()
        a.login('admin@test.example')
        staff = Browser()
        staff.login('staff@test.example')
        self.assertEqual(staff.c.get('/admin/qbank').status_code, 200)
        self.assertEqual(staff.c.get('/admin/qbank/upload').status_code, 200)
        meta = {'batch_id': '1', 'class_level': 'Class 9', 'subject': '__custom', 'subject_custom': 'Biology', 'chapter': 'Cells', 'q_type': '2 Marks'}

        def read(who, fname, data, **over):
            return who.post('/admin/qbank/upload?_csrf=' + who.token(), {**meta, **over, 'file': (io.BytesIO(data), fname)}, content_type='multipart/form-data')

        txt = b'1. What is a cell?\n2. Name two organelles\nfound in plant cells.\n3. Define osmosis.\n'
        r = read(staff, 'q.txt', txt)
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertIn('3</span>', r.text)
        self.assertEqual(read(a, 'q.exe', txt).status_code, 422)                          # only pdf / docx / txt
        self.assertEqual(read(a, 'q.txt', txt, chapter='').status_code, 422)             # chapter is required
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>Explain mitosis.</w:t></w:r></w:p><w:p><w:r><w:t>What is a tissue?</w:t></w:r></w:p></w:body></w:document>')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('word/document.xml', xml)
        self.assertIn('Explain mitosis.', read(a, 'q.docx', buf.getvalue()).text)

        def save(who, texts):
            f = {**meta, 'subject': 'Biology', 'file_name': 'q.txt', 'count': str(len(texts))}
            for i, t in enumerate(texts):
                f[f'q_{i}'], f[f'keep_{i}'] = t, '1'
            return who.post('/admin/qbank/save', f)
        self.assertEqual(save(staff, ['What is a cell?', 'Define osmosis.']).status_code, 302)
        self.assertEqual(save(a, ['what is a CELL?', 'Name the powerhouse.']).status_code, 302)       # first one is a duplicate
        rows = all_("SELECT qid, question_text, created_by_name FROM questions WHERE chapter = 'Cells' ORDER BY qid")
        self.assertEqual([r['qid'] for r in rows], [1, 2, 3])
        self.assertEqual(staff.post('/admin/qbank/%d/delete' % one("SELECT id FROM questions WHERE qid = 2")['id'], {}).status_code, 403)   # only admin deletes
        a.post('/admin/qbank/%d/delete' % one("SELECT id FROM questions WHERE qid = 3")['id'], {})
        save(a, ['A fresh question.'])
        self.assertEqual(one("SELECT qid FROM questions WHERE question_text = 'A fresh question.'")['qid'], 4)   # qid 3 is never reused
        # removing the teacher who uploaded questions must not remove the questions
        run("DELETE FROM users WHERE email = 'staff@test.example'")
        self.assertEqual(one("SELECT COUNT(*) n FROM questions WHERE chapter = 'Cells'")['n'], 3)
        self.assertTrue(one("SELECT created_by_name FROM questions WHERE qid = 1")['created_by_name'])

    def test_exports(self):
        a = Browser()
        a.login('admin@test.example')
        r = a.c.get('/admin/data-export/users.xlsx')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[:2], b'PK')
        self.assertEqual(a.c.get('/admin/data-export/sessions.xlsx').status_code, 404)
        self.assertEqual(a.c.get('/admin/data-export/all.zip').data[:2], b'PK')


if __name__ == '__main__':
    unittest.main(verbosity=2)
