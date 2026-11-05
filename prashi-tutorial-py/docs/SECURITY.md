# Security notes

What protects the site, what the review found, and what is still a limitation. Written in plain language; developers can find the code locations in brackets.

## What is in place

| Area | Control |
|---|---|
| **Passwords** | Stored only as **argon2id** hashes, never readable. Minimum 10 characters. Very long inputs are refused so nobody can overload the server with hashing. Admin-created accounts get a random temporary password that must be changed at first sign-in. *(pt/pw.py)* |
| **Sign-in** | Same generic message for wrong password and unknown user (and the same response time). Account locks 15 minutes after 5 wrong passwords. Sign-in attempts are rate-limited per visitor address (10 failures / 15 min). Every sign-in, failure, logout and reset is logged. |
| **Sessions** | Server-side sessions in an **HttpOnly, SameSite=Lax, Secure (live)** cookie. A fresh session id is issued at sign-in. Signed out after 8 idle hours. Logout destroys the session on the server. Changing or resetting a password, or switching an account off, signs that person out **everywhere immediately**. |
| **Access control** | Checked **on the server for every request** (`require_role`), never by hiding links. Admin: everything. Staff: enquiries, students, records, attendance, doubts only. Students: only the portal, and only their own data. A signed-out visitor is sent to the sign-in page; a wrong-role user sees “Access denied”. An automatic test walks **every** admin and portal route as a visitor, student and staff member and checks each is refused. |
| **Student privacy** | Every portal query is tied to the signed-in student’s own id; no URL or form field can pick another student. Students see only records the admin released, addressed to them or to a batch they are in. Files are downloadable only through a checked route (not by URL), served as attachments. Students who leave a batch lose its material. |
| **Forged requests (CSRF)** | Every form submission must carry a secret token that matches a cookie. Another website cannot read it, so it cannot submit forms for a signed-in admin. |
| **Injection** | All database queries use bound parameters; the few dynamic parts (column names for sorting) come from fixed whitelists. All page output is HTML-escaped. Rich text from the editor is cleaned when saved **and** again when shown (no scripts, no event handlers, no `javascript:` links). Single-line form answers cannot contain line breaks (stops email-header tricks). |
| **Browser protections** | Strict Content-Security-Policy (scripts only from the site itself, no framing, no plugins), `nosniff`, referrer policy, HSTS when live, `X-Powered-By` removed. Admin, portal and sign-in pages are never cached and are marked `noindex`. |
| **HTTPS only (live)** | In production, plain-HTTP requests are redirected to HTTPS, cookies are marked Secure, and the site **refuses to start** without a long `SESSION_SECRET`. |
| **Uploads** | Pictures: JPG/PNG/GIF/WebP only, checked by file contents (a renamed program or SVG is refused), 5 MB limit, stored under random names so a file name can never choose its location. Documents: fixed list of types, 20 MB, stored outside the public folder. |
| **Public forms** | Server-side validation against the Form Builder fields, required privacy-consent tick (time recorded), hidden “honeypot” field for bots, rate limit (8 per 10 minutes per visitor), unknown fields discarded, visitor IP stored only as a one-way hash. |
| **Data exposure** | Phone numbers and fees are never on public pages (course fees only if the admin ticks “Show fee on website”). Exports never include password hashes or reset tokens, and are logged. Spreadsheet/CSV exports neutralise “formula injection”. |
| **Page text** | Text typed into the editable page wording is HTML-escaped when shown; rich text (privacy/terms) is sanitised on save and on display, and `{{site_name}}`-style values are escaped. |
| **Spreadsheet import** | CSV only, 1 MB / 200 rows, text-checked. The preview creates nothing; the confirm step **re-reads and re-checks the whole file on the server** (a tampered preview cannot sneak rows in). Same validation as the Add-student form, duplicate detection, and temporary passwords are shown once and never stored readable. |
| **Student photos** | Stored in the private folder (not under the public uploads), checked by file contents, 5 MB limit, shown only to that student and to staff through checked routes; deleted when replaced, removed, or when the student is deleted. |
| **Receipts** | A receipt is shown only to staff, or to the student who owns that payment (checked on the server; other IDs answer “not found”). |
| **Audit trail** | Who changed what and when (create, edit, delete, publish, payments, resets, exports, sign-ins) in **Settings → Activity log**. Passwords and tokens are never written to it. |
| **Backups** | `python scripts/backup.py` makes a consistent copy of the database and all files. |

## What the review found (and fixed during the build)
1. Add/Edit forms were missing their security token (“session ended” on save) – fixed; an automated browser-style test now checks **every** form on every admin page carries it.
2. Staff could open admin-only preview pages – fixed and covered by the route-by-route test.
3. A student forced to change a temporary password was bounced back to the same page forever – fixed.
4. Sign-in rate limiting never triggered because failed sign-ins returned “200 OK” – failures now return 401 and limiting is tested in live mode.
5. Deleting a course silently deleted its batches – now refused with a plain-English reason.
6. Oversized or malformed requests produced “500 server error” instead of a clean 4xx – fixed.
7. Outdated mail and upload libraries (in the original Node version) – the Python version uses the standard library for mail and Flask/Werkzeug for uploads.
8. “Go back” redirects after list-page buttons trusted the browser’s Referer – now restricted to this same website.
9. WhatsApp numbers entered without a country code produced a link that does not work – `91` is now added automatically to 10-digit numbers.
10. Line breaks inside single-line answers could have reached email headers – now flattened, and the subject is sanitised.

## Tests
`python tests/test_site.py` runs a quick self-check on a throw-away database. Before release, the Python version was also run against the full original suite (about **700 automatic checks**: public site, admin, student privacy, security attacks and live-mode behaviour) with the same results. The original suite covers: public site, admin, real-browser form submission, student privacy, security attacks (SQL/script injection, path traversal, header injection, session replay, CSRF, forged cookies, hostile uploads), and live/production mode (HTTPS redirect, Secure cookies, startup refusal, rate limits).

*What the tests cannot do:* they do not drive a visual browser, so the look of pages, the rich-text editor toolbar and phone layouts still need a human to click through before launch.

11. A new test once opened the real database by mistake; SQLite refused the change so nothing was lost, and the test harness now **refuses to run** if the real database was loaded first.
12. Re-importing students who had only a parent *email* could have created duplicates – duplicate detection now covers email as well as phone.

## Known limitations – please read
* **No two-factor sign-in** for admins. Use long unique passwords, keep a second admin, and sign out on shared computers.
* **Passwords are only checked for length**, not against lists of leaked passwords.
* **Data is not encrypted at rest.** The database and uploaded files are ordinary files. Protect them with a server that has disk encryption, correct file permissions (the install guide uses a dedicated user and `chmod 600` for `.env`), and **encrypted off-site backups**. Field-level encryption was not built.
* **One server only.** Rate-limit counters and sessions live on that one machine. That is fine for a single institute; running several copies behind a load balancer would need shared storage.
* **Accepted dependency note.** *Quill* (the rich-text editor, shipped as one file in `public/vendor/quill/`) had a reported “XSS via HTML export”. Our editor output is **re-sanitised on the server** before it is stored and again before it is shown, and is never rendered back into the admin page unsanitised. Check for new Quill and Python package versions every few months (`pip list --outdated`).
* **Google Fonts** are loaded from Google, so visitors’ browsers contact Google. If that matters for your privacy policy, the fonts can be hosted on your own server instead.
* **Upload forms carry the token in the web address** (browsers cannot put it in the body of a file upload before the server reads it). The token is useless without the matching cookie, but it can appear in server logs – do not publish raw logs.
* **Email-based reset** sends the link to the student’s email, or to the parent email on file if the student has none. If neither exists the admin must reset the password.
* **Legal compliance is your responsibility.** The Privacy Policy and Terms are drafts. India’s DPDP Act 2023 (and any rules that apply to you) may require consent wording, a grievance contact, retention limits and a way to honour deletion requests. Retention is **manual** – nothing is deleted automatically.
* The admin can see all personal data by design; every export is logged.
