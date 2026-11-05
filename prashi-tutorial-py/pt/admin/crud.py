"""Generic add / edit / reorder / show-hide / delete for every content type in resources.py."""
import math
import re
import sqlite3
from datetime import datetime
from urllib.parse import urlencode

from flask import Blueprint, abort, g, redirect, request

from ..audit import audit
from ..db import all_, one, run, table_columns
from ..sanitize import clean, strip_tags
from ..tz import from_input, to_input
from ..uploads import UploadError, read_uploads, remove_public, save_image
from ..web import back_url, body, check_role, flash, render
from .resources import RESOURCES

bp = Blueprint('crud', __name__)
PER_PAGE = 25


@bp.before_request
def lookup():
    r = check_role('admin')
    if r is not None:
        return r
    key = (request.view_args or {}).get('res')
    cfg = RESOURCES.get(key)
    if not cfg:
        abort(404)
    g.cfg = {**cfg, 'key': key}
    g.base = '/admin/c/' + key
    g.locals.update(base=g.base, cfg=g.cfg, editor=bool(cfg.get('editor')), nav=g.base)


def slugify(s):
    return re.sub(r'^-+|-+$', '', re.sub(r'[^a-z0-9]+', '-', str(s or '').lower()))[:60] or 'item'


def opts(options):
    items = options() if callable(options) else (options or [])
    return [{'v': o, 'l': o} if isinstance(o, str) else o for o in items]


def pfloat(v):
    """Number(v) for a string; None when it is not a finite number."""
    try:
        n = float(v)
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def real_date(v, fmt='%Y-%m-%d'):
    try:
        datetime.strptime(v, fmt)
        return True
    except ValueError:
        return False


def prep_fields(cfg):
    return [{**f, 'options': opts(f.get('options'))} if f['t'] == 'select' else f for f in cfg['fields']]


def form_vals(cfg, row):
    vals = {}
    for f in cfg['fields']:
        if row:
            vals[f['k']] = to_input(row[f['k']]) if f['t'] == 'datetime' else row[f['k']]
        else:
            vals[f['k']] = 0 if f['t'] == 'checkbox' else (25 if f['k'] == 'seats_total' else 1 if f['k'] == 'instalments' else '')
    return vals


# ───── List with search, filter, sort, pages ─────
@bp.get('/<res>', strict_slashes=False)
def list_(res):
    cfg = g.cfg
    cols = [c['name'] for c in table_columns(cfg['table'])]
    search = str(request.args.get('q', '')).strip()[:100]
    where, args = [], []
    if search:
        where.append('(' + ' OR '.join(f'{c} LIKE ?' for c in cfg['search']) + ')')
        args += ['%' + search + '%'] * len(cfg['search'])
    filters = []
    for fl in cfg.get('filters', []):
        value = str(request.args.get('f_' + fl['k'], ''))
        if value:
            where.append(f"{fl['sql']} = ?")
            args.append(value)
        filters.append({'k': fl['k'], 'l': fl['l'], 'value': value, 'options': opts(fl.get('options'))})
    col = next((c for c in cfg['list'] if c['k'] == request.args.get('sort') and not c.get('nosort')), None)
    dir_ = 'desc' if request.args.get('dir') == 'desc' else 'asc'
    expr = (col.get('sql') or ('t.' + col['k'] if col['k'] in cols else col['k'])) if col else None
    order = f'{expr} {dir_}, t.id' if expr else (cfg.get('defaultOrder') or ('t.sort_order, t.id' if cfg.get('reorder') else 't.id DESC'))
    W = ' WHERE ' + ' AND '.join(where) if where else ''
    total = one(f"SELECT COUNT(*) n FROM ({cfg['select']}{W})", *args)['n']
    pages = max(1, math.ceil(total / PER_PAGE))
    try:
        page = int(request.args.get('page', ''))
    except ValueError:
        page = 1
    page = min(pages, max(1, page))
    rows = all_(f"{cfg['select']}{W} ORDER BY {order} LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}", *args)
    p = ([('q', search)] if search else []) + [('f_' + f['k'], f['value']) for f in filters if f['value']]
    qs = urlencode(p)
    sp = list(p) + ([('sort', col['k']), ('dir', dir_)] if col else [])
    return render('admin/list', {'title': cfg['title'], 'help': cfg['help'], 'rows': rows, 'total': total, 'page': page, 'pages': pages, 'q': search,
                                 'sort': col['k'] if col else '', 'dir': dir_, 'filters': filters, 'qs': qs, 'qsp': urlencode(sp)})


# ───── Add / edit form ─────
@bp.get('/<res>/new')
def new(res):
    cfg = g.cfg
    return render('admin/form', {'title': 'Add ' + cfg['single'], 'help': cfg['help'], 'fields': prep_fields(cfg), 'vals': form_vals(cfg, None),
                                 'errs': {}, 'row': None, 'action': g.base + '/new'})


def get_row(id_):
    return one(f"SELECT * FROM \"{g.cfg['table']}\" WHERE id = ?", id_)


@bp.get('/<res>/<int:id>/edit')
def edit(res, id):
    row = get_row(id)
    if not row:
        abort(404)
    cfg = g.cfg
    return render('admin/form', {'title': 'Edit ' + cfg['single'], 'help': cfg['help'], 'fields': prep_fields(cfg), 'vals': form_vals(cfg, row),
                                 'errs': {}, 'row': row, 'action': f"{g.base}/{row['id']}/edit"})


def read_form(cfg, files, b, row):
    """Reads and checks the submitted form against the field list. Returns (data, errs, new_files)."""
    data, errs, new_files = {}, {}, []
    by_field = {f.fieldname: f for f in files}
    for f in cfg['fields']:
        raw = b.get(f['k'])
        v = raw.strip() if isinstance(raw, str) else raw
        empty = v is None or v == ''
        if f['t'] == 'image':
            try:
                if f['k'] in by_field and by_field[f['k']].size:
                    name = save_image(by_field[f['k']])
                    new_files.append(name)
                    data[f['k']] = name
                elif b.get('_remove_' + f['k']):
                    data[f['k']] = None
            except UploadError as e:
                errs[f['k']] = str(e)
            continue
        if f['t'] == 'checkbox':
            data[f['k']] = 1 if v else 0
            continue
        if f.get('slug'):
            base = slugify(b.get(cfg.get('slugFrom')) if empty else v)
            s, n = base, 2
            while one(f"SELECT id FROM \"{cfg['table']}\" WHERE slug = ? AND id != ?", s, row['id'] if row else 0):
                s = f'{base}-{n}'
                n += 1
            data[f['k']] = s
            continue
        if empty:
            if f.get('req'):
                errs[f['k']] = 'This field is required.'
            data[f['k']] = None
            continue
        v = str(v)
        t = f['t']
        if t == 'number':
            num = pfloat(v)
            if num is None:
                errs[f['k']] = 'Enter a number.'
            elif not f.get('step') and num != int(num):
                errs[f['k']] = 'Enter a whole number.'
            elif f.get('min') is not None and num < f['min']:
                errs[f['k']] = f"Must be at least {f['min']}."
            elif f.get('max') is not None and num > f['max']:
                errs[f['k']] = f"Must be at most {f['max']}."
            data[f['k']] = int(num) if num is not None and num == int(num) else num
        elif t == 'date':
            if not (re.fullmatch(r'\d{4}-\d{2}-\d{2}', v) and real_date(v)):
                errs[f['k']] = 'Enter a valid date.'
            data[f['k']] = v
        elif t == 'datetime':
            if not (re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', v) and real_date(v, '%Y-%m-%dT%H:%M')):
                errs[f['k']] = 'Enter a valid date and time.'
            data[f['k']] = from_input(v)
        elif t == 'select':
            if not any(str(o['v']) == v for o in opts(f.get('options'))):
                errs[f['k']] = 'Please choose one of the options.'
            data[f['k']] = v
        elif t == 'richtext':
            if len(v) > 100000:
                errs[f['k']] = 'This is too long.'
            data[f['k']] = clean(v)
            if f.get('req') and not strip_tags(data[f['k']]):
                errs[f['k']] = 'This field is required.'
        else:
            mx = 5000 if t == 'textarea' else 300
            if len(v) > mx:
                errs[f['k']] = f'Please keep this under {mx} characters.'
            data[f['k']] = v
    if cfg['table'] == 'holidays' and data.get('start_date') and data.get('end_date') and data['end_date'] < data['start_date']:
        errs['end_date'] = 'The last day cannot be before the first day.'
    return data, errs, new_files


def _same(a, b):
    def n(x):
        if x is None:
            return ''
        if isinstance(x, float) and x.is_integer():
            return str(int(x))
        return str(x)
    return n(a) == n(b)


def save(row):
    cfg, base = g.cfg, g.base
    files, upload_err = read_uploads(request)
    b = body()
    data, errs, new_files = read_form(cfg, files, b, row)
    if upload_err:
        errs['_'] = 'That file is too large (limit 20 MB).' if upload_err == 'LIMIT_FILE_SIZE' else 'The upload failed. Please try again.'
    if errs:
        for n in new_files:
            remove_public(n)
        vals = {f['k']: (b.get(f['k']) if b.get(f['k']) is not None else '') for f in cfg['fields']}
        if row:
            vals.update({f['k']: row[f['k']] for f in cfg['fields'] if f['t'] == 'image'})
        return render('admin/form', {'title': ('Edit ' if row else 'Add ') + cfg['single'], 'help': cfg['help'], 'fields': prep_fields(cfg), 'vals': vals,
                                     'errs': errs, 'row': row, 'action': f"{base}/{row['id']}/edit" if row else base + '/new'}, 422)
    meta = table_columns(cfg['table'])
    not_null = {c['name'] for c in meta if c['notnull']}
    for k in list(data):
        if data[k] is None and k in not_null:
            del data[k]                                            # let the database default apply
    title = data.get(cfg['titleKey'])
    if title is None and row:
        title = row[cfg['titleKey']]
    try:
        if row:
            changed = [k for k in data if not _same(data[k], row.get(k))]
            sets = [f'"{k}" = ?' for k in data]
            if any(c['name'] == 'updated_at' for c in meta):
                sets.append("updated_at = datetime('now')")
            if sets:
                run(f"UPDATE \"{cfg['table']}\" SET {', '.join(sets)} WHERE id = ?", *data.values(), row['id'])
            for f in cfg['fields']:
                if f['t'] == 'image' and f['k'] in changed and row[f['k']]:
                    remove_public(row[f['k']])
            labels = ', '.join(next((f['l'] for f in cfg['fields'] if f['k'] == k), k) for k in changed)
            audit('update', cfg['table'], row['id'], f"Edited {cfg['single']} \"{title}\"{' – changed: ' + labels if changed else ''}")
            flash('ok', f'Saved “{title}”.')
        else:
            pub = cfg.get('pub')
            if pub:
                data[pub['col']] = 1 if b.get('publish') == '1' else 0
            if cfg.get('reorder'):
                data['sort_order'] = one(f"SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM \"{cfg['table']}\"")['n']
            ks = list(data)
            r = run(f"INSERT INTO \"{cfg['table']}\" ({','.join(chr(34) + k + chr(34) for k in ks)}) VALUES ({','.join('?' for _ in ks)})", *[data[k] for k in ks])
            audit('create', cfg['table'], r.lastrowid,
                  f"Added {cfg['single']} \"{title}\"{(' (published)' if data[pub['col']] else ' (saved as draft)') if pub else ''}")
            flash('ok', f"Saved “{title}” as a draft. It is hidden until you click {pub['publish']}." if pub and not data[pub['col']] else f'Added “{title}”.')
    except sqlite3.Error as e:
        for n in new_files:
            remove_public(n)
        print('save failed:', e)
        flash('err', 'Could not save. Please check the details and try again.')
        return redirect(base)
    return redirect(base)


@bp.post('/<res>/new')
def new_post(res):
    return save(None)


@bp.post('/<res>/<int:id>/edit')
def edit_post(res, id):
    row = get_row(id)
    if not row:
        abort(404)
    return save(row)


# ───── Show / hide, reorder, delete ─────
@bp.post('/<res>/<int:id>/toggle')
def toggle(res, id):
    cfg = g.cfg
    row = get_row(id)
    if not row or not cfg.get('pub'):
        abort(404)
    c = cfg['pub']['col']
    now = 0 if row[c] else 1
    run(f"UPDATE \"{cfg['table']}\" SET \"{c}\" = ? WHERE id = ?", now, row['id'])
    pub = cfg['pub']
    audit('update', cfg['table'], row['id'], f"{pub['publish'] if now else pub['unpublish']}: {cfg['single']} \"{row[cfg['titleKey']]}\"")
    flash('ok', f"“{row[cfg['titleKey']]}” is now {pub['on'].lower() if now else pub['off'].lower()}.")
    return redirect(back_url(g.base))


@bp.post('/<res>/<int:id>/move')
def move(res, id):
    cfg = g.cfg
    row = get_row(id)
    if not row or not cfg.get('reorder'):
        abort(404)
    ids = [r['id'] for r in all_(f"SELECT id FROM \"{cfg['table']}\" ORDER BY sort_order, id")]
    i = ids.index(row['id'])
    d = body().get('dir')
    j = i - 1 if d == 'up' else i + 1
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
        for n, id_ in enumerate(ids):
            run(f"UPDATE \"{cfg['table']}\" SET sort_order = ? WHERE id = ?", n + 1, id_)
        audit('reorder', cfg['table'], row['id'], f"Moved {cfg['single']} \"{row[cfg['titleKey']]}\" {d}")
    return redirect(g.base)


@bp.post('/<res>/<int:id>/delete')
def delete(res, id):
    cfg = g.cfg
    row = get_row(id)
    if not row:
        abort(404)
    title = row[cfg['titleKey']]
    if cfg.get('guard'):
        n = one(cfg['guard']['sql'], row['id'])['n']
        if n:
            flash('err', f"“{title}” cannot be deleted because it {cfg['guard']['msg'](n)}")
            return redirect(g.base)
    try:
        run(f"DELETE FROM \"{cfg['table']}\" WHERE id = ?", row['id'])
    except sqlite3.IntegrityError:
        flash('err', f"“{title}” cannot be deleted because it is still in use (for example, students are enrolled in it). Hide it instead.")
        return redirect(g.base)
    for f in cfg['fields']:
        if f['t'] == 'image' and row[f['k']]:
            remove_public(row[f['k']])
    audit('delete', cfg['table'], row['id'], f'Deleted {cfg["single"]} "{title}"')
    flash('ok', f'Deleted “{title}”.')
    return redirect(g.base)
