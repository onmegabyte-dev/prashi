# Prashi Tutorial – website, admin panel and student portal (Python / Flask version)

One program that runs your public website, the admin panel (for you and your staff) and the student portal.
All content lives in a database, so you never edit code to change courses, fees, faculty, notices and so on.
This is the Python version of the original Node.js site. **Every feature is the same**, the pages look the same, and the
database format is the same (so data can be copied across – see Part 6).

* **Public website** – Home, About, Courses, Course details, Faculty, Results, Resources, Admissions, Contact
* **Admin panel** – `/admin` (admin and staff logins)
* **Student portal** – `/portal` (logins created by the admin)
* **Sign in** – `/login` (one page for everyone)

Guides: [Admin Guide](docs/ADMIN-GUIDE.md) · [Go-live checklist](docs/GO-LIVE-CHECKLIST.md) · [Security notes](docs/SECURITY.md)

> **Why this cannot run on Netlify.** Netlify only serves ready-made pages and very short functions. This site needs a login
> system, a database, uploaded files and email, and all of those need a server that stays on and has a disk that keeps its
> files. Netlify has none of that, so student records, fees and photos could not be stored there. Use a Python host instead –
> Part 4 shows a **free** one (PythonAnywhere).

---

## Part 1 – Run it on your own computer

You only need to do this once. You need **Python 3.12 or newer** (<https://www.python.org/downloads/>). Check with `python3 --version`.

```
cd path/to/prashi-tutorial-py
python3 -m venv ~/.venvs/prashi                 # a private box for the libraries (kept OUTSIDE this folder, so the folder stays small)
~/.venvs/prashi/bin/pip install -r requirements.txt
cp .env.example .env
```
(Windows: `py -m venv %USERPROFILE%\venvs\prashi`, then `%USERPROFILE%\venvs\prashi\Scripts\pip install -r requirements.txt`, `copy .env.example .env`.)

Make a secret and put it in `.env` after `SESSION_SECRET=`:
```
~/.venvs/prashi/bin/python -c "import secrets; print(secrets.token_hex(32))"
```

Create the database (with sample data) and your admin login, then start the site:
```
~/.venvs/prashi/bin/python scripts/init_db.py
~/.venvs/prashi/bin/python scripts/create_admin.py
~/.venvs/prashi/bin/python app.py
```
Open <http://localhost:3000>. Sign in at <http://localhost:3000/login>. Stop the site with `Ctrl+C`.

(If you activate the private box first – `source ~/.venvs/prashi/bin/activate` – you can type just `python` instead of the long path.)

The database is created automatically on the first start even if you skip `init_db.py`, but you still need `create_admin.py` to make your login.

## Part 2 – Set up email

Email is used for enquiry alerts and “forgot password” links. Fill in `.env`:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your-16-letter-app-password
MAIL_FROM="Prashi Tutorial <you@gmail.com>"
```
For Gmail, turn on 2-step verification and create an **App password** (Google Account → Security → App passwords). Your normal password will not work.
Test it: `python scripts/test_email.py you@example.com`.

Without email the site still works: every enquiry is saved in **Admin → Enquiries & admissions**; you just are not notified by email.

## Part 3 – Make it yours
Sign in as admin and follow the [Admin Guide](docs/ADMIN-GUIDE.md): Site settings, Page text, Courses, Faculty, Form builder, Students, Fees…
Replace the logo by saving a larger picture over `public/img/logo-original.jpg`.
Run `python scripts/check_config.py` any time – it lists what is still a sample value.

## Part 4 – Put it on the internet for free (PythonAnywhere)

PythonAnywhere (<https://www.pythonanywhere.com>) has a free plan that keeps your files and database on disk and gives you
`https://YOURNAME.pythonanywhere.com` with HTTPS. I have not deployed to it from here, so treat the steps as a guide and check their help pages if a screen looks different.

**Free-plan limits to know about**
* One web app, about 512 MB of disk. A custom domain (like prashitutorial.com) needs a paid plan.
* You must press a **“Run until 3 months from today”** button on the Web tab about every 3 months, or the site is switched off (they email you first).
* The free plan can only contact a short list of websites. Check PythonAnywhere’s “allowlist” help page to see whether your email provider is on it; if it is not, email alerts will not send, but everything else works.
* Rate-limit counters live inside one running copy of the site – fine for one institute.

**Steps**
1. Sign up for a free **Beginner** account. Your username becomes part of the address.
2. **Files** tab → upload `prashi-tutorial-py.zip` (zip the folder first; leave out `data/` unless you are moving old data – see Part 6) → open a **Bash console** and unzip: `unzip prashi-tutorial-py.zip`.
3. In the Bash console, make the private libraries box and install:
   ```
   mkvirtualenv prashi --python=python3.12       # use the newest Python 3.12+ the account offers
   cd ~/prashi-tutorial-py
   pip install -r requirements.txt
   ```
4. Create the settings file: `cp .env.example .env`, then edit `.env` in the Files tab and set
   ```
   APP_ENV=production
   SITE_URL=https://YOURNAME.pythonanywhere.com
   SESSION_SECRET=<the long secret from Part 1>
   ```
   plus the email lines from Part 2.
5. Still in the console: `python scripts/init_db.py` then `python scripts/create_admin.py`.
6. **Web** tab → **Add a new web app** → *Manual configuration* → the same Python version. Then set:
   * **Virtualenv:** `/home/YOURNAME/.virtualenvs/prashi`
   * **WSGI configuration file** (click the link, delete everything, paste):
     ```python
     import sys
     path = '/home/YOURNAME/prashi-tutorial-py'
     if path not in sys.path:
         sys.path.insert(0, path)
     from wsgi import application
     ```
7. Press the green **Reload** button and open `https://YOURNAME.pythonanywhere.com`.
8. Run `python scripts/check_config.py` in the console and fix every “MUST FIX” before telling anyone the site is live.
9. **Backups:** Tasks tab → add a daily task: `/home/YOURNAME/.virtualenvs/prashi/bin/python /home/YOURNAME/prashi-tutorial-py/scripts/backup.py`. Download the newest folder from `data/backups/` now and then (Files tab) – a backup on the same server is not enough.

## Part 5 – Other places to host
Any host that runs Python 3.12+ as a normal long-running program **and keeps files on disk** works: a small VPS (DigitalOcean, Hetzner, an Indian VPS provider), Oracle Cloud “Always Free”, AWS Lightsail/EC2, Render or Railway **with a persistent disk**.
On a Linux server: install Python, create the private box, `pip install -r requirements.txt gunicorn`, set `APP_ENV=production` in `.env`, and run
`gunicorn --workers 1 --threads 4 --bind 127.0.0.1:8000 wsgi:application` behind nginx with a free HTTPS certificate (Certbot). Keep **one** worker (rate limits and sessions assume one process).
It will not work on Netlify, Vercel, GitHub Pages, or hosts whose disk is wiped on every restart (e.g. Heroku).

## Part 6 – Looking after it

### Moving your data from the old Node.js version
Stop both sites. Copy these three things from the old folder into this one (same names):
`data/prashi.db` (also copy `prashi.db-wal` and `prashi.db-shm` if they exist next to it), `uploads/public/` and `storage/private/`.
Logins keep working – the password format is identical.

### Backups – please do this
`python scripts/backup.py` saves the database and all uploaded files into `data/backups/<date>/` and keeps the newest 14.
Each backup includes a full copy of your uploads, so on a small disk keep an eye on the size of `data/backups/`, and move older ones off the server.
Admin → *Download your data* also gives an Excel/ZIP copy of every table.

### Why the folder stays small
There is no `node_modules` (that was ~90 MB), the libraries live outside the folder, and the database uses a plain journal (no growing `-wal` file).
What grows is only your real data: `data/`, `uploads/`, `storage/` and `data/backups/`.

### Updating the libraries
`pip install --upgrade -r requirements.txt` every few months, then run the tests.

### Running the automatic tests
`python tests/test_site.py` – a quick self-check using a throw-away database (your real data is not touched).

## Troubleshooting
* **“Set a long SESSION_SECRET”** – you set `APP_ENV=production` but `SESSION_SECRET` in `.env` is empty or shorter than 32 characters.
* **Cannot sign in** – run `python scripts/create_admin.py` again with the same email to set a new password (it also clears a lock).
* **Pages show but styles are missing** – you opened the files directly; start the site with `python app.py` and use the `http://localhost:3000` address.
* **Email not arriving** – run `python scripts/test_email.py you@example.com` and read the message; check spam; for Gmail use an App password.

## Folder map (for developers)
```
app.py            starts the site (security headers, sessions, error pages)
wsgi.py           entry point for hosting
pt/               the code: routes_*.py (pages), admin/ (admin panel), db.py, web.py (sessions, CSRF), pw.py, sanitize.py ...
templates/        the HTML pages (Jinja2)
public/           CSS, JavaScript, logo, the editor library (served at the site root)
db/               schema.sql (tables) and seed.sql (sample data)
scripts/          init_db.py, create_admin.py, backup.py, check_config.py, test_email.py
tests/            test_site.py
data/ uploads/ storage/   your database, public pictures, private files (never uploaded to a code host – see .gitignore)
```
