"""One-command backup: a consistent copy of the database plus all uploaded files, into data/backups/<date>.
Run:  python scripts/backup.py        (schedule it daily - see README)
Keeps the 14 most recent backups."""
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pt import db  # noqa: E402

stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')
root = db.ROOT / 'data' / 'backups'
dest = root / stamp
dest.mkdir(parents=True, exist_ok=True)
target = str(dest / 'prashi.db').replace("'", "''")
db.script(f"VACUUM INTO '{target}'")                                # safe even while the site is running
for parts in (('uploads', 'public'), ('storage', 'private')):
    src = db.ROOT.joinpath(*parts)
    if src.exists():
        shutil.copytree(src, dest / '-'.join(parts), dirs_exist_ok=True)
old = sorted(p.name for p in root.iterdir() if re.fullmatch(r'\d{4}-\d{2}-\d{2}_\d{4}', p.name))[:-14]
for n in old:
    shutil.rmtree(root / n, ignore_errors=True)
print(f"Backup saved to {dest}" + (f" (removed {len(old)} old backup{'s' if len(old) > 1 else ''})" if old else ''))
print('Copy this folder somewhere safe (another computer or cloud drive). A backup on the same server is not enough.')
