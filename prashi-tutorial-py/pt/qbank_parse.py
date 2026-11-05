"""Reads a question paper (PDF, Word .docx or plain .txt) and splits it into separate questions.
Pure reading/splitting: nothing here touches the database."""
import io
import re
import zipfile
import xml.etree.ElementTree as ET

MAX_QUESTIONS, MAX_LEN = 1000, 2000
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
# Question-number styles. A file normally uses one style, so we pick the style that gives the longest run of 1, 2, 3 … ;
# that keeps answer choices such as "1) 5 m/s  2) 6 m/s" inside their question when the questions are written "Q1." or "1.".
STYLES = [re.compile(r'^\s*Q(?:uestion)?\s*\.?\s*(\d{1,3})\s*[.):\-]?\s*(\S.*)$', re.I), re.compile(r'^\s*(\d{1,3})\s*\.\s*(\S.*)$'),
          re.compile(r'^\s*\(?(\d{1,3})\s*\)\s*(\S.*)$'), re.compile(r'^\s*(\d{1,3})\s*:\s*(\S.*)$')]

class ParseError(Exception):
    pass


def kind_of(name):
    n = (name or '').lower()
    return 'pdf' if n.endswith('.pdf') else 'docx' if n.endswith('.docx') else 'txt' if n.endswith('.txt') else None


def _pdf_lines(buf):
    from pypdf import PdfReader
    try:
        r = PdfReader(io.BytesIO(buf))
        if r.is_encrypted:
            raise ParseError('That PDF is password-protected. Remove the password and upload it again.')
        if len(r.pages) > 300:
            raise ParseError('That PDF has too many pages (limit 300). Split it into smaller files.')
        text = '\n'.join((p.extract_text() or '') for p in r.pages)
    except ParseError:
        raise
    except Exception:                                                  # corrupt / unsupported PDF
        raise ParseError('That PDF could not be read. Try saving it again, or upload a .docx or .txt version.')
    if not text.strip():
        raise ParseError('No text found in that PDF – it may be a scan (a photo of pages). Upload a text PDF, a .docx or a .txt file instead.')
    return [(ln, False) for ln in text.splitlines()]


def _docx_lines(buf):
    try:
        z = zipfile.ZipFile(io.BytesIO(buf))
        info = z.getinfo('word/document.xml')
        if info.file_size > 20 * 1024 * 1024:
            raise ParseError('That Word file is too large to read.')
        data = z.read('word/document.xml')
        if b'<!DOCTYPE' in data or b'<!ENTITY' in data:
            raise ParseError('That Word file could not be read.')
        root = ET.fromstring(data)
    except ParseError:
        raise
    except Exception:
        raise ParseError('That Word file could not be read. Make sure it is a .docx (not an old .doc) and try again.')
    out = []
    for p in root.iter(W + 'p'):
        parts = []
        for el in p.iter():
            if el.tag == W + 't':
                parts.append(el.text or '')
            elif el.tag in (W + 'tab', W + 'br'):
                parts.append(' ')
        num = p.find(f'{W}pPr/{W}numPr')
        top_item = num is not None and (num.find(W + 'ilvl') is None or num.find(W + 'ilvl').get(W + 'val') == '0')
        out.append((''.join(parts), top_item))
    return out


def _txt_lines(buf):
    if b'\x00' in buf[:4096]:
        raise ParseError('That does not look like a text file.')
    for enc in ('utf-8-sig', 'utf-16') if buf[:2] in (b'\xff\xfe', b'\xfe\xff') else ('utf-8-sig', 'cp1252'):
        try:
            return [(ln, False) for ln in buf.decode(enc).splitlines()]
        except UnicodeDecodeError:
            continue
    raise ParseError('That text file could not be read.')


def clean(s):
    return re.sub(r'[ \t ]+', ' ', re.sub(r'\s*\n\s*', '\n', s)).strip()


def numbered(lines, rx):
    """Splits on one numbering style; numbers must run in order (a small gap, or a restart at 1 after a section, is allowed)."""
    qs, cur, last = [], None, None
    for text, _ in lines:
        m = rx.match(text)
        n = int(m.group(1)) if m else None
        if m and (last is None or last < n <= last + 2 or (n == 1 and last >= 5)):
            if cur is not None:
                qs.append(cur)
            cur, last = [m.group(2)], n
        elif cur is not None and text.strip():
            cur.append(text.strip())
    if cur is not None:
        qs.append(cur)
    return qs


def split_questions(lines):
    """lines: [(text, is_word_list_item)]. Numbered questions ("1.", "Q2)", "Question 3:") are split on. If a file has
    no numbers: Word list items, then blank-line-separated blocks, then single lines are used."""
    best = max((numbered(lines, rx) for rx in STYLES), key=len)
    qs, cur = best, None
    if qs:
        return [clean('\n'.join(q)) for q in qs]
    if any(flag for _, flag in lines):                                 # Word's automatic numbering has no "1." in the text
        for text, flag in lines:
            if flag and text.strip():
                if cur is not None:
                    qs.append(cur)
                cur = [text.strip()]
            elif cur is not None and text.strip():
                cur.append(text.strip())
        qs = qs + ([cur] if cur else [])
        return [clean('\n'.join(q)) for q in qs]
    blocks, cur = [], []
    for text, _ in lines:
        if text.strip():
            cur.append(text.strip())
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    if len(blocks) <= 1:                                               # no blank lines either: one question per line
        blocks = [[t.strip()] for t, _ in lines if t.strip()]
    return [clean('\n'.join(b)) for b in blocks]


def read_questions(file):
    """file: an UploadedFile. Returns (kind, [question text, ...]); raises ParseError with a plain-English message."""
    kind = kind_of(file.originalname)
    if not kind:
        raise ParseError('Upload a PDF, Word (.docx) or text (.txt) file.')
    lines = {'pdf': _pdf_lines, 'docx': _docx_lines, 'txt': _txt_lines}[kind](file.buffer)
    qs = [q for q in split_questions(lines) if len(q) >= 5]
    if not qs:
        raise ParseError('No questions were found in that file. Number the questions (1. 2. 3. …) or put each one on its own line.')
    if len(qs) > MAX_QUESTIONS:
        raise ParseError(f'That file has more than {MAX_QUESTIONS} questions. Please split it into smaller files.')
    return kind, [q[:MAX_LEN] for q in qs]
