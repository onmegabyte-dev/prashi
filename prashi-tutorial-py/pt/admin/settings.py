"""Site settings: contact details, map, social links and the home-page numbers."""
import re

from flask import Blueprint, redirect

from ..audit import audit
from ..db import all_, run
from ..web import body, check_role, flash, render

bp = Blueprint('settings', __name__)


@bp.before_request
def only_admin():
    return check_role('admin')


# Every setting the admin may change, grouped for the screen. type: text | textarea | email | digits | url | map | number
GROUPS = [
    ['Your institute', [
        ['site_name', 'Institute name', 'text', 'Shown in the header, footer, browser tab and emails.', 1],
        ['banner_text', 'Announcement bar', 'text', 'A thin coloured bar at the very top of every page. Leave blank to hide it. Example: “Admissions open for 2026–27”.'],
    ]],
    ['Contact details', [
        ['phone', 'Phone number', 'text', 'Shown on the Contact page and footer.'],
        ['whatsapp', 'WhatsApp number', 'digits', 'Digits only with country code, no + or spaces. Example: 919876543210. Powers the green WhatsApp button. Leave blank to hide it.'],
        ['email', 'Public email', 'email', 'Shown on the Contact page and footer.'],
        ['admin_inbox_email', 'Email for new enquiries', 'email', 'Every new admission, enquiry, counselling request and message is emailed here. Not shown to visitors.'],
        ['address', 'Address', 'textarea', 'Your branch address.'],
        ['office_hours', 'Office hours', 'text', 'Example: Mon–Sat 9 am–7 pm · Sun 10 am–2 pm'],
    ]],
    ['Map', [
        ['map_embed_url', 'Google Maps embed link', 'map', 'Optional. In Google Maps: Share → Embed a map → copy HTML. Paste it here (the whole thing is fine). Leave blank to hide the map.'],
    ]],
    ['Social links', [
        ['social_instagram', 'Instagram', 'url', 'Full link starting with https://. Leave blank to hide.'],
        ['social_youtube', 'YouTube', 'url', 'Full link starting with https://. Leave blank to hide.'],
        ['social_facebook', 'Facebook', 'url', 'Full link starting with https://. Leave blank to hide.'],
    ]],
    ['Home page numbers', [
        ['stats_students', 'Students taught', 'number', 'Counts up on the home page. Use real, honest figures.'],
        ['stats_success', 'Success rate (%)', 'number', 'A number from 0 to 100.'],
        ['stats_faculty', 'Number of faculty', 'number'],
        ['stats_years', 'Years of experience', 'number'],
    ]],
]
FIELDS = [d for g_ in GROUPS for d in g_[1]]
HELP = '<p>Your contact details and the small bits of text that appear all over the website. Change them here and every page updates immediately – no coding needed.</p><ul><li>Anything you leave blank (like the map or social links) is simply hidden.</li><li>Holiday closures are managed under <b>Website content → Holidays</b>.</li></ul>'


def check(d, raw):
    key, label, typ = d[0], d[1], d[2]
    req = d[4] if len(d) > 4 else 0
    v = str(raw if raw is not None else '').strip()
    if not v:
        return {'err': f'{label} is required.'} if req else {'v': ''}
    if len(v) > (500 if typ == 'textarea' else 300) and typ != 'map':
        return {'err': f'{label} is too long.'}
    if typ == 'email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]{2,}', v):
        return {'err': f'{label}: enter a valid email.'}
    if typ == 'digits':
        v = re.sub(r'[\s+-]', '', v)
        if not re.fullmatch(r'\d{8,15}', v):
            return {'err': f'{label}: digits only (8–15 numbers), with the country code.'}
        if len(v) == 10:
            v = '91' + v                                           # plain Indian mobile number -> add the country code
    if typ == 'url' and not re.fullmatch(r'https://[^\s"\'<>]+', v):
        return {'err': f'{label}: must start with https://'}
    if typ == 'number' and not (re.fullmatch(r'\d+', v) and int(v) <= 100000000):
        return {'err': f'{label}: enter a whole number.'}
    if key == 'stats_success' and int(v) > 100:
        return {'err': 'Success rate cannot be more than 100.'}
    if typ == 'map':
        m = re.search(r'''src=["']([^"']+)["']''', v)
        if m:
            v = m.group(1)
        v = v.replace('&amp;', '&')
        if not re.fullmatch(r'https://www\.google\.com/maps/embed[^\s"\'<>]*', v):
            return {'err': 'That does not look like a Google Maps “Embed a map” link. It should start with https://www.google.com/maps/embed'}
    return {'v': v}


@bp.get('/', strict_slashes=False)
def index():
    vals = {r['key']: r['value'] for r in all_('SELECT key, value FROM settings')}
    return render('admin/settings', {'title': 'Site settings', 'nav': '/admin/settings', 'groups': GROUPS, 'vals': vals, 'errs': [], 'help': HELP})


@bp.post('/', strict_slashes=False)
def save():
    b = body()
    errs, cleaned = [], {}
    for d in FIELDS:
        r = check(d, b.get(d[0]))
        if r.get('err'):
            errs.append(r['err'])
        else:
            cleaned[d[0]] = r['v']
    if errs:
        return render('admin/settings', {'title': 'Site settings', 'nav': '/admin/settings', 'groups': GROUPS, 'vals': b, 'errs': errs, 'help': ''}, 422)
    old = {r['key']: r['value'] for r in all_('SELECT key, value FROM settings')}
    changed = []
    for k, v in cleaned.items():
        if (old.get(k) if old.get(k) is not None else '') != v:
            run('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', k, v)
            changed.append(next(f[1] for f in FIELDS if f[0] == k))
    if changed:
        audit('update', 'settings', None, 'Changed site settings: ' + ', '.join(changed))
    flash('ok', 'Settings saved. The website is updated.' if changed else 'Nothing changed.')
    return redirect('/admin/settings')
