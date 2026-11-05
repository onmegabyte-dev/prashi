"""Read-only queries used by the public pages. Hidden, unpublished and expired items never appear here."""
from flask import g, has_request_context

from .db import all_, one
from .pagetext import DEFAULTS
from .tz import now_local


def live():
    # Times are compared in the institute's local time (the same zone the admin types them in).
    n = now_local()
    return f"(publish_at IS NULL OR publish_at <= '{n}') AND (expires_at IS NULL OR expires_at > '{n}')"


def settings():
    """Saved settings win over the built-in wording (even when saved empty on purpose).
    Read once per web request."""
    if has_request_context() and hasattr(g, '_settings'):
        return dict(g._settings)
    s = {**DEFAULTS, **{r['key']: r['value'] for r in all_('SELECT key, value FROM settings')}}
    s['tagline'] = f"{s.get('hero_line1') or ''} {s.get('hero_line2') or ''}".strip()      # used in the browser-tab title
    if has_request_context():
        g._settings = s
    return dict(s)


def _split(s, sep):
    return [x.strip() for x in str(s or '').split(sep) if x.strip()]


def decorate_course(c):
    return {**c, 'subjectList': _split(c.get('subjects'), ','), 'highlightList': _split(c.get('highlights'), '\n')}


def public_course(c):
    """Fee is removed unless the admin turned "show fee" on for that course."""
    d = decorate_course(c)
    if not c.get('show_fee'):
        d['fee_amount'] = None
    return d


COURSE_SQL = 'SELECT c.*, f.name AS faculty_name FROM courses c LEFT JOIN faculty f ON f.id = c.faculty_id WHERE c.visible = 1'


def courses():
    return [public_course(c) for c in all_(f'{COURSE_SQL} ORDER BY c.sort_order, c.name')]


def course(slug):
    c = one(f'{COURSE_SQL} AND c.slug = ?', slug)
    return public_course(c) if c else None


BATCH_SQL = """SELECT b.*, c.name AS course_name, c.slug AS course_slug,
  b.seats_total - (SELECT COUNT(*) FROM enrollments e WHERE e.batch_id = b.id AND e.status = 'active') AS seats_left
  FROM batches b JOIN courses c ON c.id = b.course_id WHERE b.visible = 1 AND c.visible = 1"""


def upcoming_batches(limit=4):
    return all_(f"{BATCH_SQL} AND b.status != 'closed' ORDER BY b.start_date LIMIT ?", limit)


def course_batches(course_id):
    return all_(f"{BATCH_SQL} AND b.course_id = ? AND b.status != 'closed' ORDER BY b.start_date", course_id)


def faculty(limit=100):
    return all_('SELECT * FROM faculty WHERE visible = 1 ORDER BY sort_order, name LIMIT ?', limit)


def testimonials():
    return all_('SELECT * FROM testimonials WHERE approved = 1 ORDER BY sort_order, id')


def results(kind):
    return all_('SELECT * FROM results WHERE approved = 1 AND kind = ? ORDER BY sort_order, id', kind)


def faqs(course_id=None):
    extra = 'OR course_id = ?' if course_id else ''
    return all_(f'SELECT * FROM faqs WHERE visible = 1 AND {live()} AND (course_id IS NULL {extra}) ORDER BY sort_order, id',
                *([course_id] if course_id else []))


def notices():
    return all_(f"SELECT * FROM notices WHERE visible = 1 AND audience = 'public' AND {live()} ORDER BY pinned DESC, created_at DESC LIMIT 5")


def articles():
    return all_(f"""SELECT id, slug, title, category, summary, cover_image, publish_at, created_at FROM articles
   WHERE published = 1 AND (publish_at IS NULL OR publish_at <= '{now_local()}') ORDER BY COALESCE(publish_at, created_at) DESC""")


def article(slug):
    return one(f"SELECT * FROM articles WHERE slug = ? AND published = 1 AND (publish_at IS NULL OR publish_at <= '{now_local()}')", slug)


def holidays():
    return all_(f"SELECT * FROM holidays WHERE end_date >= '{now_local()[:10]}' ORDER BY start_date LIMIT 5")


# Admin previews: same shape as the public data, but hidden/unpublished items are allowed.
def course_any(id_):
    c = one('SELECT c.*, f.name AS faculty_name FROM courses c LEFT JOIN faculty f ON f.id = c.faculty_id WHERE c.id = ?', id_)
    return public_course(c) if c else None


def article_any(id_):
    return one('SELECT * FROM articles WHERE id = ?', id_)
