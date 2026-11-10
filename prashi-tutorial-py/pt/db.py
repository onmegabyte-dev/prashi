"""SQLite access. One connection per thread; autocommit, so explicit transactions use tx()."""
import contextlib
import os
import sqlite3
import threading
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DB_FILE = (ROOT / os.environ.get('DB_FILE', './data/prashi.db')).resolve()

_local = threading.local()


def _dict_row(cur, row):
    return {d[0]: v for d, v in zip(cur.description, row)}


def conn():
    c = getattr(_local, 'c', None)
    if c is None or getattr(_local, 'file', None) != str(DB_FILE):
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(DB_FILE), isolation_level=None, timeout=5, check_same_thread=False)
        c.row_factory = _dict_row
        c.execute('PRAGMA foreign_keys = ON')
        c.execute('PRAGMA busy_timeout = 5000')
        _local.c, _local.file = c, str(DB_FILE)
    return c


def one(sql, *args):
    return conn().execute(sql, args).fetchone()


def all_(sql, *args):
    return conn().execute(sql, args).fetchall()


def run(sql, *args):
    """Runs a write. Returns the cursor (use .lastrowid / .rowcount)."""
    return conn().execute(sql, args)


def script(sql):
    conn().executescript(sql)


@contextlib.contextmanager
def tx():
    c = conn()
    c.execute('BEGIN')
    try:
        yield
        c.execute('COMMIT')
    except BaseException:
        c.execute('ROLLBACK')
        raise


def table_columns(table):
    return all_(f'PRAGMA table_info("{table}")')


def has_table(name):
    return one("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", name) is not None


def create_from_files():
    """Creates every table from db/schema.sql and loads the sample data from db/seed.sql."""
    script((ROOT / 'db' / 'schema.sql').read_text(encoding='utf8'))
    script((ROOT / 'db' / 'seed.sql').read_text(encoding='utf8'))


def ensure_ready():
    """Safe to run on every start: creates a missing database, and adds the small extras older databases lack."""
    if not has_table('users'):
        create_from_files()
    if not any(c['name'] == 'photo' for c in table_columns('students')):
        run('ALTER TABLE students ADD COLUMN photo TEXT')
    try:
        run('PRAGMA journal_mode = DELETE')                        # a plain journal: no ever-growing "-wal" file next to the database
    except Exception:                                              # noqa: BLE001  (e.g. another program has it open: harmless)
        pass
    if has_table('chapter_access') and not any(c['name'] == 'q_type' for c in table_columns('chapter_access')):
        run('DROP TABLE chapter_access')                           # first version (whole chapters, no types): never held real data
    script((ROOT / 'db' / 'qbank.sql').read_text(encoding='utf8'))
    if not any(c['name'] == 'answer_text' for c in table_columns('questions')):
        run('ALTER TABLE questions ADD COLUMN answer_text TEXT')
    script('CREATE TABLE IF NOT EXISTS sessions (sid TEXT PRIMARY KEY, sess TEXT NOT NULL, expires INTEGER NOT NULL, uid INTEGER);'
           'CREATE INDEX IF NOT EXISTS idx_sessions_uid ON sessions(uid);')
