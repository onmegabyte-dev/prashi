"""Creates (or resets the password of) an admin login. The password is hashed with argon2id."""
import getpass
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pt import db, pw  # noqa: E402

db.ensure_ready()
name = input('Admin name: ').strip()
email = input('Admin email (used to log in): ').strip().lower()
password = getpass.getpass('Password (min 10 characters, hidden while you type): ')

if not name or not re.fullmatch(r'\S+@\S+\.\S+', email):
    sys.exit('Please enter a name and a valid email.')
if len(password) < 10:
    sys.exit('Password must be at least 10 characters.')
hashed = pw.hash_password(password)
old = db.one('SELECT id, role FROM users WHERE email = ?', email)
if old and old['role'] != 'admin':
    sys.exit(f"That email belongs to a {old['role']} login, not an admin. Use a different email, or change that login from the admin panel.")
if old:
    db.run("UPDATE users SET password_hash=?, name=?, role='admin', active=1, must_change_password=0, failed_logins=0, locked_until=NULL WHERE id=?", hashed, name, old['id'])
else:
    db.run("INSERT INTO users (role,name,email,password_hash,must_change_password) VALUES ('admin',?,?,?,0)", name, email, hashed)
print('Admin password updated.' if old else 'Admin created.')
