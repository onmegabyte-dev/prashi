"""All admin-entered times are in the institute's local time zone (default India)."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ_NAME = os.environ.get('TIME_ZONE', 'Asia/Kolkata')
TZ = ZoneInfo(TZ_NAME)


def now_local():
    """'YYYY-MM-DD HH:MM:SS' in local time - the same format stored in publish_at / expires_at."""
    return datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')


def today_local():
    return now_local()[:10]


def from_input(v):
    """<input type="datetime-local"> gives 'YYYY-MM-DDTHH:MM'; store with a space and seconds."""
    return (v.replace('T', ' ') + (':00' if len(v) == 16 else '')) if v else None


def to_input(v):
    return str(v).replace(' ', 'T')[:16] if v else ''


def iso_now(offset_seconds=0):
    """Like JavaScript's new Date().toISOString(): 2026-10-19T08:00:00.000Z"""
    d = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + offset_seconds, timezone.utc)
    return d.strftime('%Y-%m-%dT%H:%M:%S.') + f'{d.microsecond // 1000:03d}Z'


def utc_stamp(offset_seconds=0):
    """'YYYY-MM-DD HH:MM:SS' in UTC (the format SQLite's datetime('now') writes)."""
    return iso_now(offset_seconds)[:19].replace('T', ' ')


def show_utc(v):
    """created_at columns are stored in UTC by SQLite; show them in local time, like '19 Oct 2026, 1:26 pm'."""
    if not v:
        return ''
    try:
        d = datetime.fromisoformat(str(v).replace(' ', 'T').rstrip('Z')).replace(tzinfo=timezone.utc).astimezone(TZ)
    except ValueError:
        return ''
    h = d.hour % 12 or 12
    return f"{d.day} {d.strftime('%b')} {d.year}, {h}:{d.minute:02d} {'am' if d.hour < 12 else 'pm'}"


def fmt_date(v):
    """'2026-10-19' -> '19 Oct 2026'."""
    if not v:
        return ''
    try:
        d = datetime.strptime(str(v)[:10], '%Y-%m-%d')
    except ValueError:
        return ''
    return f"{d.day} {d.strftime('%b')} {d.year}"


def valid_day(v):
    """True for a real calendar date written YYYY-MM-DD."""
    import re
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(v or '')):
        return False
    try:
        datetime.strptime(v, '%Y-%m-%d')
        return True
    except ValueError:
        return False
