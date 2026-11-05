"""Form builder: the admin edits the fields on the admission / enquiry / counselling / contact forms."""
import re

from flask import Blueprint, abort, redirect, request

from ..audit import audit
from ..db import all_, one, run
from ..forms import get_fields
from ..web import body, check_role, flash, render

bp = Blueprint('formbuilder', __name__)


@bp.before_request
def only_admin():
    return check_role('admin')


FORMS = {'admission': 'Admission form', 'enquiry': 'Enquiry form', 'counselling': 'Counselling request', 'contact': 'Contact form'}
TYPES = [['text', 'Short text'], ['textarea', 'Long text'], ['tel', 'Phone number'], ['email', 'Email'], ['number', 'Number'], ['date', 'Date'], ['select', 'Drop-down list'], ['checkbox', 'Tick box']]
RESERVED = ['website', 'consent', '_csrf', 'constructor', 'prototype', '__proto__']


def slug(s):
    return re.sub(r'^_+|_+$', '', re.sub(r'[^a-z0-9]+', '_', str(s).lower()))[:40] or 'field'


def form_of(v):
    return v if v in FORMS else 'admission'


def page(form, extra=None, status=200):
    fields = all_('SELECT * FROM form_fields WHERE form = ? ORDER BY sort_order, id', form)
    ctx = {'title': 'Form builder', 'nav': '/admin/forms', 'FORMS': FORMS, 'TYPES': TYPES, 'form': form, 'fields': fields, 'preview': get_fields(form), 'values': {}, 'errs': [],
           'help': '<p>Change what people are asked on the website forms – no coding needed.</p><ul><li><b>Add a field</b> (for example “Previous school”) at the bottom of the page.</li><li><b>▲ ▼</b> change the order; <b>Required</b> means the form cannot be sent without it.</li><li><b>Hide</b> stops asking a question without deleting old answers.</li><li>Core fields (like name and phone) are locked so enquiries always have a way to reach the family. You can still rename them.</li><li>The <b>Preview</b> below shows exactly what visitors will see.</li></ul>'}
    ctx.update(extra or {})
    return render('admin/forms', ctx, status)


@bp.get('/', strict_slashes=False)
def index():
    return page(form_of(request.args.get('form')))


def read_field(b, existing):
    errs, label = [], str(b.get('label') or '').strip()
    typ = existing['type'] if existing and existing['locked'] else str(b.get('type') or '')
    if not label or len(label) > 100:
        errs.append('Give the field a label (up to 100 characters).')
    if not any(t[0] == typ for t in TYPES):
        errs.append('Choose a field type.')
    options = '\n'.join(x.strip() for x in str(b.get('options') or '').split('\n') if x.strip())
    if typ == 'select' and not options and not (existing and existing['name'] == 'course'):
        errs.append('A drop-down needs at least one choice (one per line).')
    if len(options) > 2000:
        errs.append('Too many choices.')
    return {'errs': errs, 'label': label, 'type': typ, 'options': (options or None) if typ == 'select' else None,
            'required': 1 if b.get('required') else 0, 'help': str(b.get('help_text') or '').strip()[:200] or None}


@bp.post('/add')
def add():
    b = body()
    form = form_of(b.get('form'))
    f = read_field(b, None)
    if f['errs']:
        return page(form, {'errs': f['errs'], 'values': b})
    name, n = slug(f['label']), 2
    if name in RESERVED:
        name += '_field'
    base = name
    while one('SELECT 1 FROM form_fields WHERE form = ? AND name = ?', form, name):
        name = f'{base}_{n}'
        n += 1
    order = one('SELECT COALESCE(MAX(sort_order),0)+1 AS n FROM form_fields WHERE form = ?', form)['n']
    run('INSERT INTO form_fields (form, name, label, type, options, required, help_text, sort_order) VALUES (?,?,?,?,?,?,?,?)', form, name, f['label'], f['type'], f['options'], f['required'], f['help'], order)
    audit('create', 'form_field', f'{form}.{name}', f"Added “{f['label']}” to the {FORMS[form]}{' (required)' if f['required'] else ''}")
    flash('ok', f"Added “{f['label']}” to the {FORMS[form].lower()}.")
    return redirect('/admin/forms?form=' + form)


def field(id_):
    r = one('SELECT * FROM form_fields WHERE id = ?', id_)
    if not r:
        abort(404)
    return r


@bp.get('/field/<int:id>')
def field_edit(id):
    fl = field(id)
    return render('admin/form-field', {'title': 'Edit field', 'nav': '/admin/forms', 'FORMS': FORMS, 'TYPES': TYPES, 'fl': fl, 'errs': [],
                                       'help': '<p>Change how this question appears. Locked fields keep their type and always stay required.</p>'})


@bp.post('/field/<int:id>')
def field_save(id):
    fl = field(id)
    b = body()
    f = read_field(b, fl)
    if f['errs']:
        return render('admin/form-field', {'title': 'Edit field', 'nav': '/admin/forms', 'FORMS': FORMS, 'TYPES': TYPES, 'fl': {**fl, **b}, 'errs': f['errs'], 'help': ''}, 422)
    run('UPDATE form_fields SET label = ?, type = ?, options = ?, required = ?, help_text = ? WHERE id = ?', f['label'], f['type'], f['options'], fl['required'] if fl['locked'] else f['required'], f['help'], fl['id'])
    audit('update', 'form_field', f"{fl['form']}.{fl['name']}", f"Edited “{f['label']}” on the {FORMS[fl['form']]}")
    flash('ok', 'Field updated.')
    return redirect('/admin/forms?form=' + fl['form'])


@bp.post('/field/<int:id>/move')
def field_move(id):
    fl = field(id)
    ids = [r['id'] for r in all_('SELECT id FROM form_fields WHERE form = ? ORDER BY sort_order, id', fl['form'])]
    i = ids.index(fl['id'])
    d = body().get('dir')
    j = i - 1 if d == 'up' else i + 1
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
        for n, id_ in enumerate(ids):
            run('UPDATE form_fields SET sort_order = ? WHERE id = ?', n + 1, id_)
        audit('reorder', 'form_field', f"{fl['form']}.{fl['name']}", f"Moved “{fl['label']}” {d} on the {FORMS[fl['form']]}")
    return redirect('/admin/forms?form=' + fl['form'])


@bp.post('/field/<int:id>/required')
def field_required(id):
    fl = field(id)
    if fl['locked']:
        flash('err', 'This core field must always stay required.')
        return redirect('/admin/forms?form=' + fl['form'])
    now = 0 if fl['required'] else 1
    run('UPDATE form_fields SET required = ? WHERE id = ?', now, fl['id'])
    audit('update', 'form_field', f"{fl['form']}.{fl['name']}", f"“{fl['label']}” is now {'required' if now else 'optional'} on the {FORMS[fl['form']]}")
    return redirect('/admin/forms?form=' + fl['form'])


@bp.post('/field/<int:id>/active')
def field_active(id):
    fl = field(id)
    if fl['locked']:
        flash('err', 'Core fields cannot be hidden.')
        return redirect('/admin/forms?form=' + fl['form'])
    now = 0 if fl['active'] else 1
    run('UPDATE form_fields SET active = ? WHERE id = ?', now, fl['id'])
    audit('update', 'form_field', f"{fl['form']}.{fl['name']}", f"{'Showing' if now else 'Hiding'} “{fl['label']}” on the {FORMS[fl['form']]}")
    return redirect('/admin/forms?form=' + fl['form'])


@bp.post('/field/<int:id>/delete')
def field_delete(id):
    fl = field(id)
    if fl['locked']:
        flash('err', 'Core fields cannot be deleted.')
        return redirect('/admin/forms?form=' + fl['form'])
    run('DELETE FROM form_fields WHERE id = ?', fl['id'])
    audit('delete', 'form_field', f"{fl['form']}.{fl['name']}", f"Deleted “{fl['label']}” from the {FORMS[fl['form']]}")
    flash('ok', f"Deleted “{fl['label']}”. Answers people already gave are kept in the inbox.")
    return redirect('/admin/forms?form=' + fl['form'])
