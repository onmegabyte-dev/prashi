"""Rules for a student record, shared by the Add-student form and the spreadsheet import."""
import re
from datetime import date

from .db import one

CLASSES = ['Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12', 'Dropper / Other']
_EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]{2,}')
_PHONE = re.compile(r'[+\d][\d\s-]{7,16}')


def fields():
    return [
        {'k': 'name', 'l': 'Student name', 't': 'text', 'req': 1},
        {'k': 'class_level', 'l': 'Class', 't': 'select', 'options': CLASSES, 'blank': '— choose —'},
        {'k': 'school', 'l': 'School', 't': 'text'},
        {'k': 'dob', 'l': 'Date of birth', 't': 'date'},
        {'k': 'parent_name', 'l': 'Parent / guardian name', 't': 'text'},
        {'k': 'parent_phone', 'l': 'Parent phone', 't': 'tel', 'help': 'Add at least a parent phone or a parent email so we can always reach the family.'},
        {'k': 'parent_email', 'l': 'Parent email', 't': 'email', 'help': 'Password-reset links go here if the student has no email of their own.'},
        {'k': 'email', 'l': 'Student’s own email (optional)', 't': 'email', 'help': 'Optional. The student can sign in with this or with their admission number.'},
        {'k': 'address', 'l': 'Address', 't': 'textarea', 'rows': 2},
        {'k': 'joined_on', 'l': 'Joining date', 't': 'date'},
        {'k': 'notes_internal', 'l': 'Private notes', 't': 'textarea', 'rows': 3, 'help': 'Only staff see this. Never shown to the student or parents.'},
    ]


def _real_date(v):
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def read_student(body, user_id=0):
    """Returns (values, errors) for the submitted student form."""
    v, errs = {}, {}
    for f in fields():
        raw = str(body.get(f['k']) if body.get(f['k']) is not None else '').strip()
        v[f['k']] = raw or None
        if len(raw) > (2000 if f['t'] == 'textarea' else 200):
            errs[f['k']] = 'Too long.'
    if not v['name']:
        errs['name'] = 'This field is required.'
    if v['email'] and not _EMAIL.fullmatch(v['email']):
        errs['email'] = 'Enter a valid email.'
    if v['parent_email'] and not _EMAIL.fullmatch(v['parent_email']):
        errs['parent_email'] = 'Enter a valid email.'
    if v['parent_phone'] and not (_PHONE.fullmatch(v['parent_phone']) and len(re.sub(r'\D', '', v['parent_phone'])) >= 8):
        errs['parent_phone'] = 'Enter a phone number with 8–15 digits.'
    if not v['parent_phone'] and not v['parent_email']:
        errs['parent_phone'] = 'Add a parent phone or a parent email.'
    for d in ('dob', 'joined_on'):
        if v[d] and not (re.fullmatch(r'\d{4}-\d{2}-\d{2}', v[d]) and _real_date(v[d])):
            errs[d] = 'Enter a valid date.'
    if v['class_level'] and v['class_level'] not in CLASSES:
        errs['class_level'] = 'Choose from the list.'
    if v['email'] and one('SELECT id FROM users WHERE lower(email) = lower(?) AND id != ?', v['email'], user_id or 0):
        errs['email'] = 'Another login already uses this email.'
    return v, errs


def next_admission_no():
    prefix = 'PT' + str(date.today().year)[2:]
    n = (one('SELECT COUNT(*) n FROM students WHERE admission_no LIKE ?', prefix + '%')['n'] or 0) + 1
    while True:
        no = prefix + str(n).zfill(4)
        n += 1
        if not one('SELECT 1 FROM students WHERE admission_no = ?', no):
            return no
