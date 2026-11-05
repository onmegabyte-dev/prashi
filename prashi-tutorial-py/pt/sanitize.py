"""Rich text from the admin editor. Applied when saving AND when showing (defence in depth)."""
import re

import nh3

# sanitize-html's default tag list, plus the extras the editor needs.
_TAGS = {
    'address', 'article', 'aside', 'footer', 'header', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hgroup', 'main', 'nav', 'section',
    'blockquote', 'dd', 'div', 'dl', 'dt', 'figcaption', 'figure', 'hr', 'li', 'ol', 'p', 'pre', 'ul',
    'a', 'abbr', 'b', 'bdi', 'bdo', 'br', 'cite', 'code', 'data', 'dfn', 'em', 'i', 'kbd', 'mark', 'q', 'rb', 'rp', 'rt', 'rtc',
    'ruby', 's', 'samp', 'small', 'span', 'strike', 'strong', 'sub', 'sup', 'time', 'u', 'var', 'wbr',
    'caption', 'col', 'colgroup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr',
    'img',
}
_ATTRS = {'a': {'href', 'title', 'target'}, 'img': {'src', 'alt', 'width', 'height'}}
_SCHEME = re.compile(r'^\s*([a-z][a-z0-9+.\-]*):', re.I)


def _filter(tag, attr, value):
    # Pictures may only point to http(s) addresses (or this site); never mailto: / tel:.
    if tag == 'img' and attr == 'src':
        m = _SCHEME.match(value)
        if m and m.group(1).lower() not in ('http', 'https'):
            return None
    return value


def clean(html):
    return nh3.clean(html or '', tags=_TAGS, attributes=_ATTRS, url_schemes={'http', 'https', 'mailto', 'tel'},
                     link_rel='noopener noreferrer', attribute_filter=_filter)


def text(html):
    return nh3.clean(html or '', tags=set(), attributes={})


def strip_tags(html):
    """Plain text of some HTML (for "is this empty?" checks)."""
    return re.sub(r'<[^>]*>', '', html or '').strip()
