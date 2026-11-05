"""'Page text': the wording on the home, about and admissions pages, footer, receipts, privacy and terms."""
import re

from flask import Blueprint, redirect, request

from .. import content
from ..audit import audit
from ..db import run
from ..pagetext import ALL_KEYS, GROUPS
from ..sanitize import clean
from ..web import body, check_role, flash, render

bp = Blueprint('pages', __name__)


@bp.before_request
def only_admin():
    return check_role('admin')


FIELDS = [{**f, 'group': g_['id']} for g_ in GROUPS for f in g_['fields']]
HELP = '<p>Change the wording on your public pages – no coding needed. Each box shows what visitors see now.</p><ul><li>Open a section, edit, and click <b>Save page text</b> at the bottom. The website updates immediately.</li><li><b>Lists</b> (like “Why families choose us”) are written one item per line as <b>Title | Description</b>. Empty the box to hide that section.</li><li><b>Reset this section</b> brings back the original sample wording.</li><li>The home page heading (“Learn Today. Lead Tomorrow.”) and the sentence under it are in <b>Home page</b>.</li><li><b>Please read every box once and save</b> – some of the sample wording contains claims (class sizes, safety, reports) that must be true for your institute.</li></ul>'


def page(vals, errs, open_, status=200):
    return render('admin/pages', {'title': 'Page text', 'nav': '/admin/pages', 'editor': True, 'groups': GROUPS, 'vals': vals, 'errs': errs, 'open': open_, 'help': HELP}, status)


@bp.get('/', strict_slashes=False)
def index():
    s = content.settings()
    return page({k: s.get(k) for k in ALL_KEYS}, {}, str(request.args.get('g', 'home')))


@bp.post('/', strict_slashes=False)
def save():
    b = body()
    errs, cleaned, current = {}, {}, content.settings()
    for f in FIELDS:
        k = f['k']
        if b.get(k) is None:                                       # a field missing from the submission is left unchanged, never blanked
            cleaned[k] = current.get(k) if current.get(k) is not None else ''
            continue
        v = str(b.get(k)).replace('\r\n', '\n').strip()
        if f['t'] == 'text':
            v = re.sub(r'\n+', ' ', v)
        if f['t'] == 'richtext':
            v = clean(v)
        if f.get('req') and not v:
            errs[k] = 'This cannot be empty.'
            continue
        if len(v) > f['max']:
            errs[k] = f"Please keep this under {f['max']} characters (it is {len(v)})."
            continue
        if f.get('list') and v:
            ls = [x.strip() for x in v.split('\n') if x.strip()]
            bad = next((i for i, l in enumerate(ls) if not re.fullmatch(r'[^|]+\|.+', l)), -1)
            if len(ls) > 12:
                errs[k] = 'Please use at most 12 lines.'
            elif bad >= 0:
                errs[k] = f'Line {bad + 1} needs a title, then “ | ”, then a description. Example: Small batches | 25 students at most.'
            elif any(len(l.split('|')[0].strip()) > 80 for l in ls):
                errs[k] = 'Titles should be under 80 characters.'
            v = '\n'.join(ls)
        cleaned[k] = v
    if errs:
        first_bad = next(f for f in FIELDS if f['k'] in errs)
        return page({k: (b.get(k) if b.get(k) is not None else '') for k in ALL_KEYS}, errs, first_bad['group'], 422)
    cur, changed = content.settings(), []
    for f in FIELDS:
        if (cur.get(f['k']) if cur.get(f['k']) is not None else '') != cleaned[f['k']]:
            run('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', f['k'], cleaned[f['k']])
            changed.append(f['l'])
    run('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', 'pages_reviewed', '1')
    audit('update', 'page_text', None, 'Edited page text: ' + ', '.join(changed) if changed else 'Reviewed page text (no changes)')
    n = len(changed)
    flash('ok', f"Saved. {n} item{'' if n == 1 else 's'} changed – the website is updated." if changed else 'Nothing changed, and the page text is marked as reviewed.')
    return redirect('/admin/pages')


@bp.post('/reset')
def reset():
    g_ = next((x for x in GROUPS if x['id'] == body().get('group')), None)
    if not g_:
        flash('err', 'Unknown section.')
        return redirect('/admin/pages')
    for f in g_['fields']:
        run('DELETE FROM settings WHERE key = ?', f['k'])
    audit('update', 'page_text', g_['id'], f"Reset “{g_['label']}” to the original wording")
    flash('ok', f"“{g_['label']}” is back to the original wording.")
    return redirect('/admin/pages?g=' + g_['id'])
