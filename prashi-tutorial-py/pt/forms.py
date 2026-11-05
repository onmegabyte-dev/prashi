"""Server-side validation for forms built in the admin Form Builder.
The field list comes from the database, so adding "Previous school" in the admin needs no code change."""
import re

from .db import all_

FORM_NAMES = ['admission', 'enquiry', 'counselling', 'contact']

EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]{2,}')
PHONE = re.compile(r'[+\d][\d\s-]{7,16}')


def course_options():
    return [{'value': c['slug'], 'label': c['name']}
            for c in all_('SELECT slug, name FROM courses WHERE visible = 1 ORDER BY sort_order, name')]


def get_fields(form):
    """Returns the active fields for a form, with select options resolved."""
    out = []
    for f in all_('SELECT * FROM form_fields WHERE form = ? AND active = 1 ORDER BY sort_order, id', form):
        options = None
        if f['type'] == 'select':
            if f['name'] == 'course' and not f['options']:
                options = course_options()
            else:
                options = [{'value': v, 'label': v} for v in (s.strip() for s in str(f['options'] or '').split('\n')) if v]
        out.append({**f, 'options': options})
    return out


def validate(form, body):
    """Returns (values, errors). Unknown fields sent by a client are ignored."""
    values, errors = {}, {}
    for f in get_fields(form):
        v = body.get(f['name'])
        if f['type'] == 'checkbox':
            v = 'Yes' if v in (True, 'on', 'true', '1') else ''
        else:
            v = v.strip() if isinstance(v, str) else ''
        if f['type'] != 'textarea':
            v = re.sub(r'[\r\n\t]+', ' ', v)            # single-line answers can never smuggle in line breaks (email header tricks)
        mx = 3000 if f['type'] == 'textarea' else 300
        digits = re.sub(r'\D', '', v)
        msg = ''
        if not v:
            if f['required']:
                msg = 'This field is required.'
        elif len(v) > mx:
            msg = f'Please keep this under {mx} characters.'
        elif f['type'] == 'email' and not EMAIL.fullmatch(v):
            msg = 'Enter a valid email like name@example.com.'
        elif f['type'] == 'tel' and not (PHONE.fullmatch(v) and 8 <= len(digits) <= 15):
            msg = 'Enter a phone number with 8–15 digits.'
        elif f['type'] == 'number' and not re.fullmatch(r'-?\d+(\.\d+)?', v):
            msg = 'Enter a number.'
        elif f['type'] == 'date' and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
            msg = 'Enter a valid date.'
        elif f['type'] == 'select' and not any(o['value'] == v for o in f['options']):
            msg = 'Please choose one of the options.'
        if msg:
            errors[f['name']] = msg
        elif v:
            values[f['name']] = v
    return values, errors
