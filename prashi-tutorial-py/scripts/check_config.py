"""Go-live checker:  python scripts/check_config.py
Lists anything still set to a sample value or left insecure. Exit code 1 if something must be fixed."""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pt import content, db  # noqa: E402

bad = warn = 0


def ok(m): print('  ✔ ' + m)


def fix(m):
    global bad
    bad += 1
    print('  ✘ MUST FIX: ' + m)


def maybe(m):
    global warn
    warn += 1
    print('  ⚠ ' + m)


db.ensure_ready()
env = os.environ
S = {r['key']: r['value'] for r in db.all_('SELECT key, value FROM settings')}
prod = env.get('NODE_ENV') == 'production' or env.get('APP_ENV') == 'production'

print('\nServer')
ok('Python ' + sys.version.split()[0]) if sys.version_info >= (3, 10) else fix('Python 3.10 or newer is required')
ok('APP_ENV=production') if prod else maybe('APP_ENV is not "production" (set it in .env when going live)')
ok('SESSION_SECRET is long and set') if len(env.get('SESSION_SECRET', '')) >= 32 and 'change-me' not in env.get('SESSION_SECRET', '') else fix('SESSION_SECRET is missing, short or still "change-me"')
ok('SITE_URL uses https://') if re.match(r'https://', env.get('SITE_URL', '')) else fix('SITE_URL must be your real https:// address (used in sitemap and reset-password emails)')
ok('Email (SMTP) is configured') if env.get('SMTP_HOST') else fix('SMTP_* is empty – enquiry alerts and password-reset emails will NOT be sent')
ok('.env file present') if (db.ROOT / '.env').exists() else fix('.env file missing')

print('\nAccounts')
admins = db.one("SELECT COUNT(*) n FROM users WHERE role = 'admin' AND active = 1")['n']
ok(f'{admins} active admin login(s)') if admins else fix('No admin login yet – run: python scripts/create_admin.py')
if admins == 1:
    maybe('Only one admin. Create a second admin so you cannot be locked out.')

print('\nWebsite details (still sample values?)')
ok('Public email set') if not re.search(r'example|\.test', S.get('email') or '') else fix(f"Public email is a placeholder ({S.get('email')})")
ok('Enquiry inbox email set') if not re.search(r'example|\.test', S.get('admin_inbox_email') or '') else fix(f"\"Email for new enquiries\" is a placeholder ({S.get('admin_inbox_email')}) – real enquiries would go nowhere")
ok('Phone and WhatsApp set') if not re.search(r'90000 ?00000|9000000000', (S.get('phone') or '') + (S.get('whatsapp') or '')) else fix('Phone / WhatsApp number is still the sample number')
ok('Address set') if 'Your branch address' not in (S.get('address') or '') else fix('Address is still the sample text')
ok('Map embed set') if S.get('map_embed_url') else maybe('No Google Map set (optional)')
ok('Social links set') if (S.get('social_instagram') or S.get('social_youtube') or S.get('social_facebook')) else maybe('No social links set (optional)')
maybe(f"{db.one('SELECT COUNT(*) n FROM courses')['n']} course(s) in the database – make sure they are YOUR courses, fees and batch dates, not the samples")
eff = content.settings()
ok('Page text has been reviewed and saved') if S.get('pages_reviewed') == '1' else fix('Page text not reviewed yet: open Admin → Settings → Page text, read every section (home, about, admissions…), correct anything untrue, and click “Save page text”')
fix('Privacy Policy still has the “Draft for review” notice – edit it under Admin → Settings → Page text → Privacy Policy') if 'Draft for review' in eff['privacy_html'] else ok('Privacy Policy edited')
fix('Terms & Conditions are still the placeholder – write them under Admin → Settings → Page text → Terms') if '<b>Placeholder.</b>' in eff['terms_html'] else ok('Terms & Conditions edited')
flagged = []
for f in list((db.ROOT / 'templates').rglob('*.html')):
    if re.search(r'public|partials', str(f.relative_to(db.ROOT / 'templates'))):
        for i, line in enumerate(f.read_text(encoding='utf8').split('\n')):
            if re.search(r'placeholder content|placeholder text|<b>placeholder|Admissions open · 2026', line, re.I):
                flagged.append(f'{f.relative_to(db.ROOT)}:{i + 1}')
fix('Sample wording is still visible to visitors (footer “Placeholder content”, About/Terms notes, hero “Admissions open · 2026–27”): ' + ', '.join(flagged)) if flagged else ok('No “placeholder” wording left in public pages')
logo = db.ROOT / 'public' / 'img' / 'logo-original.jpg'
maybe('The logo file is small (about 150px). Replace public/img/logo-original.jpg with a larger one.') if logo.exists() and logo.stat().st_size < 20000 else ok('Logo file is a reasonable size')

print(f"\n{f'{bad} thing(s) must be fixed before going live.' if bad else 'No blocking problems.'}{f' {warn} reminder(s) above.' if warn else ''}\n")
sys.exit(1 if bad else 0)
