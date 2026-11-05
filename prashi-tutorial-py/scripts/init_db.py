"""Creates the database from db/schema.sql and loads sample data from db/seed.sql.
Safe by default: refuses to touch an existing database. Use "python scripts/init_db.py --reset" to start over."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pt import db  # noqa: E402

reset = '--reset' in sys.argv
f = db.DB_FILE

if f.exists() and f.stat().st_size > 0:
    if not reset:
        print(f'A database already exists at {f}. Nothing changed.\nTo wipe it and start over, run: python scripts/init_db.py --reset')
        sys.exit(0)
    for ext in ('', '-wal', '-shm', '-journal'):
        Path(str(f) + ext).unlink(missing_ok=True)

db.create_from_files()
db.ensure_ready()
print(f'Database created at {f} with sample data.\nNext: python scripts/create_admin.py')
