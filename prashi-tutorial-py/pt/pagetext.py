"""Editable wording for the public pages. Built-in defaults are used until the admin saves their own
(stored in the settings table), so nothing needs migrating."""
import re
from html import escape

from .pagetext_data import DEFAULTS, GROUPS

ALL_KEYS = [f['k'] for g in GROUPS for f in g['fields']]


def parse_items(s):
    """'Title | description' lines -> [{t, d}]"""
    out = []
    for line in str(s or '').split('\n'):
        line = line.strip()
        if not line:
            continue
        i = line.find('|')
        item = {'t': line, 'd': ''} if i < 0 else {'t': line[:i].strip(), 'd': line[i + 1:].strip()}
        if item['t']:
            out.append(item)
    return out


def esc(v):
    return escape('' if v is None else str(v), quote=True).replace('&#x27;', '&#39;')


def fill(html, s):
    """Replaces {{site_name}} etc. in rich text with escaped values from Site settings."""
    return re.sub(r'\{\{(site_name|email|phone|address)\}\}', lambda m: esc(s.get(m.group(1))), str(html or ''))
