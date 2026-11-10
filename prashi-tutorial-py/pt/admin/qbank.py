"""Question bank. Admin and teachers (staff) upload a PDF / Word / text file of questions for a batch, class, subject, chapter and
question type; the questions are read out and stored one per row. (Quiz mode will be built on top of this later.)
Questions belong to the school, not to a person: deleting a login or a batch never deletes questions."""
import re
from urllib.parse import urlencode

from flask import Blueprint, Response, abort, g, redirect, request

from ..audit import audit
from ..db import all_, one, run, tx
from ..qbank_samples import SAMPLES, sample_text
from ..qbank_parse import MAX_LEN, MAX_QUESTIONS, ParseError, kind_of, read_questions
from ..uploads import read_uploads
from ..web import admin_only, body, flash, render

bp = Blueprint('qbank', __name__)
CLASSES = [f'Class {n}' for n in range(1, 13)]
SUBJECTS = ['Physics', 'Chemistry', 'Mathematics']
QTYPES = [f'{n} Mark' + ('' if n == 1 else 's') for n in range(1, 6)]
CUSTOM = '__custom'


def key(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip().lower()


def tidy(s, n):
    return re.sub(r'\s+', ' ', str(s or '')).strip()[:n]


ANS_RX = re.compile(r'\n\s*(?:ans(?:wer)?)\s*[.:\-)]\s*', re.I)


def split_answer(t):
    """'What is a cell?\\nAns: The unit of life' -> (question, answer). No 'Ans:' line -> (text, None)."""
    m = ANS_RX.search(t)
    if not m or not t[:m.start()].strip() or not t[m.end():].strip():
        return t, None
    return t[:m.start()].strip(), t[m.end():].strip()


def batches():
    return all_("SELECT b.id AS v, c.name || ' – ' || b.name AS l FROM batches b JOIN courses c ON c.id = b.course_id ORDER BY c.name, b.name")


def pick(b, field, fixed, label, maxlen=40, resolved=False):
    """A drop-down with a 'Custom' choice: returns (value, error). `resolved`: the value was already chosen on the previous step."""
    v = str(b.get(field) or '')
    if resolved:
        v = tidy(v, maxlen)
        return (v, '') if v else ('', f'Choose the {label}.')
    if v == CUSTOM:
        v = tidy(b.get(field + '_custom'), maxlen)
        return (v, '') if v else ('', f'Type the {label}.')
    if v in fixed:
        return v, ''
    return '', f'Choose the {label}.'


def read_meta(b, resolved=False):
    errs, m = {}, {}
    bid = int(b['batch_id']) if re.fullmatch(r'\d+', str(b.get('batch_id') or '')) else None
    row = bid and one("SELECT b.id, c.name || ' – ' || b.name AS label FROM batches b JOIN courses c ON c.id = b.course_id WHERE b.id = ?", bid)
    if not row:
        errs['batch_id'] = 'Choose a batch.'
    else:
        m['batch_id'], m['batch_name'] = row['id'], row['label']
    for field, fixed, label in (('class_level', CLASSES, 'class'), ('subject', SUBJECTS, 'subject'), ('q_type', QTYPES, 'question type')):
        m[field], e = pick(b, field, fixed, label, resolved=resolved)
        if e:
            errs[field] = e
    m['chapter'] = tidy(b.get('chapter'), 120)
    if not m['chapter']:
        errs['chapter'] = 'Type the chapter name.'
    return errs, m


def form_page(vals, errs, status=200):
    return render('admin/qbank-upload', {
        'samples': [(n, v[0]) for n, v in SAMPLES.items()],
        'title': 'Upload questions', 'nav': '/admin/qbank', 'vals': vals, 'errs': errs, 'batches': batches(), 'CLASSES': CLASSES, 'SUBJECTS': SUBJECTS, 'QTYPES': QTYPES, 'CUSTOM': CUSTOM,
        'chapters': all_('SELECT DISTINCT chapter AS v FROM questions ORDER BY 1 LIMIT 500'),
        'help': '<p>Add many questions at once from one file.</p><ol style="margin-left:20px"><li>Choose the <b>batch, class, subject, chapter</b> and <b>question type</b> – every question in the file is filed under these.</li>'
                '<li>Upload a <b>PDF, Word (.docx) or text (.txt)</b> file. Number the questions (<b>Q1.</b> <b>Q2.</b> or <b>1.</b> <b>2.</b>). To give an answer, start a new line with <b>Answer:</b> – everything after it, up to the next question number, is the answer.</li>'
                '<li>You will see the questions it found. Fix or untick any, then save.</li></ol><p>Use one question type per file (for example one file of 2-mark questions). Duplicates already in the bank are skipped.</p>'}, status)


@bp.get('/sample/<int:n>.txt')
def sample(n):
    if n not in SAMPLES:
        abort(404)
    return Response(sample_text(n), mimetype='text/plain; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="sample-{n}-mark-questions.txt"'})


# ───── Browse: Class > Subject > Chapter > Question types (folders) ─────
def class_key(c):
    m = re.fullmatch(r'class\s+(\d+)', c.lower())
    return (0, int(m.group(1)), '') if m else (1, 0, c.lower())


def type_key(t):
    m = re.match(r'\s*(\d+)', t)
    return (int(m.group(1)) if m else 99, t.lower())


@bp.get('/', strict_slashes=False)
def list_():
    a = request.args
    f = {k: str(a.get(k, '')).strip()[:120] for k in ('class_level', 'subject', 'chapter')}
    if not f['class_level']:
        f['subject'] = f['chapter'] = ''
    if not f['subject']:
        f['chapter'] = ''
    ctx = {'title': 'Question bank', 'nav': '/admin/qbank', 'f': f, 'folders': [], 'types': [], 'uploads': [], 'batches': batches(), 'audience': '', 'published': set(), 'pub_rows': []}
    if not f['class_level']:
        ctx['folders'] = sorted(all_('SELECT class_level AS name, COUNT(DISTINCT subject) sub, COUNT(*) n FROM questions GROUP BY class_level'), key=lambda r: class_key(r['name']))
        ctx['uploads'] = all_('SELECT * FROM qb_uploads ORDER BY id DESC LIMIT 8')
        ctx['level'] = 'class'
    elif not f['subject']:
        ctx['folders'] = all_('SELECT subject AS name, COUNT(DISTINCT chapter) sub, COUNT(*) n FROM questions WHERE class_level = ? GROUP BY subject ORDER BY subject', f['class_level'])
        ctx['level'] = 'subject'
    elif not f['chapter']:
        ctx['folders'] = all_('SELECT chapter AS name, COUNT(DISTINCT q_type) sub, COUNT(*) n FROM questions WHERE class_level = ? AND subject = ? GROUP BY chapter ORDER BY chapter', f['class_level'], f['subject'])
        ctx['level'] = 'chapter'
    else:
        grp = (f['class_level'], f['subject'], f['chapter'])
        qs = all_('SELECT * FROM questions WHERE class_level = ? AND subject = ? AND chapter = ? ORDER BY qid', *grp)
        types = {}
        for q in qs:
            types.setdefault(q['q_type'], []).append(q)
        aud = str(a.get('audience', ''))
        aud = int(aud) if re.fullmatch(r'\d+', aud) and one('SELECT 1 FROM batches WHERE id = ?', int(aud)) else None
        ctx.update(level='types', types=sorted(types.items(), key=lambda kv: type_key(kv[0])), audience=aud if aud else '',
                   published={r['q_type'].lower() for r in all_('SELECT q_type FROM chapter_access WHERE class_level = ? AND subject = ? AND chapter = ? AND COALESCE(batch_id, 0) = ?', *grp, aud or 0)},
                   pub_rows=all_("""SELECT COALESCE(c.name || ' – ' || b.name, 'Whole ' || a.class_level) AS who, GROUP_CONCAT(a.q_type, ', ') AS kinds FROM chapter_access a
                                    LEFT JOIN batches b ON b.id = a.batch_id LEFT JOIN courses c ON c.id = b.course_id
                                    WHERE a.class_level = ? AND a.subject = ? AND a.chapter = ? GROUP BY a.batch_id ORDER BY a.batch_id""", *grp))
        ctx['title'] = f['chapter']
    ctx['help'] = ('<p>Questions are filed in folders: <b>Class → Subject → Chapter → Question type</b>. Open a chapter to read the questions and answers, fix an answer, and '
                   '<b>choose which question types to publish</b> to students (the whole class, or one batch).</p>'
                   '<p>Questions stay in the bank even if the teacher who uploaded them, or the batch, is later removed.</p>')
    return render('admin/qbank', ctx)


@bp.post('/publish')
def publish():
    b = body()
    grp = tuple(str(b.get(k) or '').strip() for k in ('class_level', 'subject', 'chapter'))
    back = '/admin/qbank?' + urlencode(dict(zip(('class_level', 'subject', 'chapter'), grp)))
    have = {r['q_type'] for r in all_('SELECT DISTINCT q_type FROM questions WHERE class_level = ? AND subject = ? AND chapter = ?', *grp)}
    if not have:
        flash('err', 'That chapter was not found.')
        return redirect('/admin/qbank')
    bid = None
    if str(b.get('batch_id') or ''):
        bid = int(b['batch_id']) if re.fullmatch(r'\d+', str(b['batch_id'])) and one('SELECT 1 FROM batches WHERE id = ?', int(b['batch_id'])) else 0
        if not bid:
            flash('err', 'Choose a valid batch.')
            return redirect(back)
    want = {t for t in b.getlist('types') if t in have}
    with tx():
        for t in have:
            if t in want:
                run('INSERT OR IGNORE INTO chapter_access (class_level, subject, chapter, q_type, batch_id, enabled_by, enabled_by_name) VALUES (?,?,?,?,?,?,?)',
                    *grp, t, bid, g.user['id'], g.user['name'])
            else:
                run('DELETE FROM chapter_access WHERE class_level = ? AND subject = ? AND chapter = ? AND q_type = ? AND COALESCE(batch_id, 0) = ?', *grp, t, bid or 0)
    audit('update', 'chapter access', 0, f"Published {', '.join(sorted(want)) or 'nothing'} of {' · '.join(grp)} to " + (f'batch {bid}' if bid else 'the whole class'))
    flash('ok', ('Published to students: ' + ', '.join(sorted(want, key=type_key)) + '.') if want else 'Nothing is published to those students now.')
    return redirect(back + ('&audience=%d' % bid if bid else ''))


# ───── Upload: step 1 (choose + read the file), step 2 (check), step 3 (save) ─────
@bp.get('/upload')
def upload():
    return form_page({}, {})


@bp.post('/upload')
def upload_post():
    b = body()
    files, err = read_uploads(request, accept='file')
    errs, meta = read_meta(b)
    f = files[0] if files else None
    qs, kind = [], None
    if err:
        errs['file'] = 'That file is too large (limit 20 MB).' if err == 'LIMIT_FILE_SIZE' else 'The upload failed. Please try again.'
    elif not f or not f.size:
        errs['file'] = 'Choose a PDF, Word or text file.'
    elif not kind_of(f.originalname):
        errs['file'] = 'Only PDF, Word (.docx) and text (.txt) files can be read.'
    else:
        try:
            kind, qs = read_questions(f)
        except ParseError as e:
            errs['file'] = str(e)
    if errs:
        return form_page(b, errs, 422)
    dup = {key(r['question_text']) for r in all_('SELECT question_text FROM questions WHERE class_level = ? AND subject = ? AND chapter = ? AND q_type = ?',
                                                 meta['class_level'], meta['subject'], meta['chapter'], meta['q_type'])}
    items = [{'text': q, 'dup': key(q) in dup} for q in qs]
    return render('admin/qbank-preview', {'title': 'Check the questions', 'nav': '/admin/qbank', 'm': meta, 'items': items, 'kind': kind, 'file_name': f.originalname[:120],
                                          'dups': sum(i['dup'] for i in items), 'MAX_LEN': MAX_LEN})


@bp.post('/save')
def save():
    b = body()
    errs, meta = read_meta(b, resolved=True)
    n = int(b['count']) if re.fullmatch(r'\d{1,4}', str(b.get('count') or '')) else 0
    if errs or not 0 < n <= MAX_QUESTIONS:
        flash('err', 'That upload could not be saved. Please start again.')
        return redirect('/admin/qbank/upload')
    texts = []
    for i in range(n):
        t = re.sub(r'[ \t]+', ' ', str(b.get(f'q_{i}') or '')).strip()[:MAX_LEN]
        if b.get(f'keep_{i}') and len(t) >= 5:
            texts.append(t)
    if not texts:
        flash('err', 'No questions were ticked, so nothing was saved.')
        return redirect('/admin/qbank/upload')
    u = g.user
    grp = (meta['class_level'], meta['subject'], meta['chapter'], meta['q_type'])
    added = skipped = 0
    with tx():
        up = run('INSERT INTO qb_uploads (batch_id, batch_name, class_level, subject, chapter, q_type, file_name, file_kind, uploaded_by, uploaded_by_name, uploaded_by_role) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                 meta['batch_id'], meta['batch_name'], *grp, tidy(b.get('file_name'), 120), kind_of(b.get('file_name')), u['id'], u['name'], u['role']).lastrowid
        run('INSERT OR IGNORE INTO qb_counters (class_level, subject, chapter, q_type, last_qid) VALUES (?,?,?,?,0)', *grp)
        for t in texts:
            t, ans = split_answer(t)
            if one('SELECT 1 FROM questions WHERE class_level = ? AND subject = ? AND chapter = ? AND q_type = ? AND text_key = ?', *grp, key(t)):
                skipped += 1
                continue
            run('UPDATE qb_counters SET last_qid = last_qid + 1 WHERE class_level = ? AND subject = ? AND chapter = ? AND q_type = ?', *grp)
            qid = one('SELECT last_qid FROM qb_counters WHERE class_level = ? AND subject = ? AND chapter = ? AND q_type = ?', *grp)['last_qid']
            run('INSERT INTO questions (class_level, subject, chapter, q_type, qid, question_text, answer_text, text_key, batch_id, batch_name, upload_id, created_by, created_by_name) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                *grp, qid, t, ans, key(t), meta['batch_id'], meta['batch_name'], up, u['id'], u['name'])
            added += 1
        run('UPDATE qb_uploads SET question_count = ?, skipped_count = ? WHERE id = ?', added, skipped, up)
    audit('create', 'question bank', up, f"Added {added} question(s) to {meta['class_level']} · {meta['subject']} · {meta['chapter']} · {meta['q_type']}" + (f' ({skipped} duplicates skipped)' if skipped else ''))
    flash('ok', f"{added} question{'' if added == 1 else 's'} saved." + (f' {skipped} already in the bank {"was" if skipped == 1 else "were"} skipped.' if skipped else ''))
    return redirect('/admin/qbank?' + urlencode({'class_level': meta['class_level'], 'subject': meta['subject'], 'chapter': meta['chapter'], 'q_type': meta['q_type']}))


# ───── Delete (admin only: teachers can add questions but not remove them) ─────
@bp.post('/<int:id>/delete')
@admin_only
def delete(id):
    q = one('SELECT * FROM questions WHERE id = ?', id)
    if not q:
        abort(404)
    run('DELETE FROM questions WHERE id = ?', id)
    audit('delete', 'question bank', id, f"Deleted question {q['class_level']} · {q['subject']} · {q['chapter']} · {q['q_type']} · Q{q['qid']}")
    flash('ok', 'Question deleted.')
    from ..web import back_url
    return redirect(back_url('/admin/qbank'))


# ───── Answers ─────
@bp.post('/<int:id>/answer')
def answer(id):
    q = one('SELECT * FROM questions WHERE id = ?', id)
    if not q:
        abort(404)
    a = str(body().get('answer') or '').strip()[:MAX_LEN] or None
    run('UPDATE questions SET answer_text = ? WHERE id = ?', a, id)
    audit('update', 'question bank', id, f"{'Set' if a else 'Cleared'} the answer of {q['class_level']} · {q['subject']} · {q['chapter']} · {q['q_type']} · Q{q['qid']}")
    flash('ok', 'Answer saved.' if a else 'Answer removed.')
    from ..web import back_url
    return redirect(back_url('/admin/qbank'))
