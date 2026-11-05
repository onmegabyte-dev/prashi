"""Prashi Tutorial - Flask app. Run locally with:  python app.py   (or: flask --app app run)"""
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory, session
from markupsafe import Markup
from werkzeug.exceptions import HTTPException
from werkzeug.security import safe_join
from werkzeug.middleware.proxy_fix import ProxyFix

from pt import content, db, web
from pt.status_pages import PAGES, status_page
from pt.fmt import locale, money
from pt.pagetext import DEFAULTS, fill, parse_items
from pt.sanitize import clean
from pt.tz import fmt_date, show_utc
from pt.uploads import PUBLIC_DIR

PROD = web.PROD
log = logging.getLogger('prashi')


# ───────────────────────── Template helpers ─────────────────────────
def initials(n):
    return ''.join(x[:1] for x in str(n or '').split(' ')[:2]).upper()


def json_ld(obj):
    return Markup(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c'))


def finalize(x):
    """How values print in templates: nothing for None, and 88 (not 88.0) for whole numbers."""
    if x is None:
        return ''
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def _wa_number(n):
    d = re.sub(r'\D', '', str(n or ''))
    return '91' + d if len(d) == 10 else d


def create_app():
    app = Flask(__name__, static_folder='public', static_url_path='', template_folder='templates')
    app.session_interface = web.DbSessionInterface()
    app.url_map.strict_slashes = False                             # /portal and /portal/ are the same page, as before
    app.config.update(
        MAX_CONTENT_LENGTH=26 * 1024 * 1024,                       # one 20 MB file plus form fields
        MAX_FORM_PARTS=5000,
        SEND_FILE_MAX_AGE_DEFAULT=7 * 86400 if PROD else 0,
        JSON_AS_ASCII=False,
    )
    app.jinja_env.finalize = finalize
    app.jinja_env.globals.update(
        money=money, fmtDate=fmt_date, showUtc=show_utc, initials=initials, locale=locale, json_ld=json_ld,
        clean=lambda h: Markup(clean(h)), parseItems=parse_items,
    )
    app.jinja_env.policies['json.dumps_kwargs'] = {'ensure_ascii': False, 'sort_keys': False}

    if os.environ.get('TRUST_PROXY') or PROD:                      # needed behind HTTPS hosting so IPs and secure cookies work
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if PROD and (len(os.environ.get('SESSION_SECRET', '')) < 32):
        raise SystemExit('Set a long SESSION_SECRET in .env before running in production.')

    db.ensure_ready()

    # ── per-request values every template can use ──
    @app.context_processor
    def inject():
        try:
            s = content.settings()
        except Exception:                                          # noqa: BLE001  (never let a settings problem break the error page)
            log.exception('settings failed')
            s = {**DEFAULTS, 'tagline': 'Learn Today. Lead Tomorrow.'}
        site = web.site_url()
        path = request.path
        wa = _wa_number(s.get('whatsapp'))
        map_url = s.get('map_embed_url') or ''
        ctx = {
            's': s, 'path': path, 'site': site, 'noindex': False, 'user': getattr(g, 'user', None), 'flash': getattr(g, 'flash', None),
            'title': s.get('site_name'), 'desc': '', 'canonical': site + path, 'ld': [], 'ogImage': site + '/img/logo-original.jpg',
            'waLink': f"https://wa.me/{wa}?text=" + web.js_quote('Hello ' + str(s.get('site_name')) + ', I would like to know more.') if s.get('whatsapp') else '',
            'map': map_url if re.match(r'https://www\.google\.com/maps/embed', map_url) else '',
            'orgLd': {
                '@context': 'https://schema.org', '@type': 'EducationalOrganization', 'name': s.get('site_name'), 'url': site,
                'logo': site + '/img/logo-original.jpg', 'email': s.get('email'), 'telephone': s.get('phone'), 'address': s.get('address'),
                'sameAs': [x for x in (s.get('social_instagram'), s.get('social_youtube'), s.get('social_facebook')) if x],
            },
            'csrfToken': getattr(g, 'csrf_token', ''), 'nav': '', 'editor': False, 'currentYear': datetime.now().year,
            'richText': lambda html: Markup(clean(fill(html, s))),
        }
        ctx.update(getattr(g, 'locals', {}))                       # set by the admin/portal areas; explicit render() values still win
        return ctx

    # ── before every request ──
    quiet = ('static', 'healthz', 'uploads')
    public_dir = Path(app.static_folder)

    def static_exists():
        try:
            return safe_join(str(public_dir), (request.view_args or {}).get('filename', '')) is not None and \
                Path(safe_join(str(public_dir), request.view_args['filename'])).is_file()
        except Exception:                                          # noqa: BLE001
            return False

    last_purge = {'t': 0.0}

    @app.before_request
    def start():
        g.locals = {}
        if PROD and not request.is_secure:
            return ('', 301, {'Location': 'https://' + request.host + request.full_path.rstrip('?')})
        mt, n = request.mimetype, request.content_length or 0
        if (mt == 'application/json' and n > 50 * 1024) or (mt == 'application/x-www-form-urlencoded' and n > 300 * 1024):
            return too_large()
        if mt == 'application/json' and n:                         # malformed JSON is the visitor's problem: a clear 400
            try:
                parsed = json.loads(request.get_data(cache=True) or b'null')
            except ValueError:
                parsed = None
            if not isinstance(parsed, (dict, list)):
                return bad_request()
        if request.endpoint in quiet and not (request.endpoint == 'static' and not static_exists()):
            return None                                            # (a missing "file" is really an unknown page, so it is handled like one)
        if time.time() - last_purge['t'] > 3600:
            last_purge['t'] = time.time()
            try:
                web.purge_expired_sessions()
            except Exception:                                      # noqa: BLE001
                pass
        r = web.csrf_check()
        if r is not None:
            return r
        web.load_user()
        p = request.path
        if p == '/admin' or p.startswith('/admin/'):
            return web.check_role('admin', 'staff')
        if p == '/portal' or p.startswith('/portal/'):
            return web.check_role('student')
        return None

    # ── after every request ──
    @app.after_request
    def finish(resp):
        if getattr(g, 'csrf_new', False):
            resp.set_cookie(web.CSRF_COOKIE, g.csrf_token, max_age=7 * 24 * 3600, httponly=True, samesite='Lax', secure=PROD, path='/')
        if request.endpoint not in quiet and 'Cache-Control' not in resp.headers:
            resp.headers['Cache-Control'] = 'no-store'
        csp = ["default-src 'self'", "base-uri 'self'", "font-src 'self' https://fonts.gstatic.com", "form-action 'self'",
               "frame-ancestors 'none'", "frame-src https://www.google.com", "img-src 'self' data:", "object-src 'none'",
               "script-src 'self'", "script-src-attr 'none'", "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"]
        if PROD:
            csp.append('upgrade-insecure-requests')
        h = resp.headers
        h['Content-Security-Policy'] = '; '.join(csp)
        h['Cross-Origin-Opener-Policy'] = 'same-origin'
        h['Cross-Origin-Resource-Policy'] = 'same-origin'
        h['Origin-Agent-Cluster'] = '?1'
        h['Referrer-Policy'] = 'same-origin'
        h['Strict-Transport-Security'] = 'max-age=15552000; includeSubDomains'
        h['X-Content-Type-Options'] = 'nosniff'
        h['X-DNS-Prefetch-Control'] = 'off'
        h['X-Download-Options'] = 'noopen'
        h['X-Frame-Options'] = 'SAMEORIGIN'
        h['X-Permitted-Cross-Domain-Policies'] = 'none'
        h['X-XSS-Protection'] = '0'
        h.pop('Server', None)
        return resp

    # ── simple endpoints ──
    @app.get('/healthz')
    def healthz():
        """For hosting platforms and uptime monitors: answers "ok" only if the database responds."""
        try:
            db.one('SELECT 1')
            return 'ok', 200, {'Content-Type': 'text/plain; charset=utf-8'}
        except Exception:                                          # noqa: BLE001
            return 'database error', 500, {'Content-Type': 'text/plain; charset=utf-8'}

    @app.get('/uploads/<path:name>')
    def uploads(name):
        return send_from_directory(PUBLIC_DIR, name, max_age=7 * 86400 if PROD else 0)

    # ── routes ──
    from pt.admin import bp as admin_bp
    from pt.routes_auth import bp as auth_bp
    from pt.routes_portal import bp as portal_bp
    from pt.routes_public import bp as public_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(portal_bp, url_prefix='/portal')
    app.register_blueprint(public_bp)

    # ── errors ──
    def error_page(code, title=None, message=None):
        return status_page(code, message)

    def too_large():
        if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json' or request.mimetype == 'application/json':
            return jsonify(ok=False, message='That request was too large.'), 413
        return 'That request was too large.', 413, {'Content-Type': 'text/plain; charset=utf-8'}

    def bad_request():
        return jsonify(ok=False, message='That request could not be understood.'), 400

    @app.errorhandler(Exception)
    def on_error(e):
        status = e.code if isinstance(e, HTTPException) else 500
        if status >= 500 or not isinstance(e, HTTPException):
            log.exception('Unhandled error: %s', e)
        as_json = request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json' or request.mimetype == 'application/json'
        if 400 <= status < 500:                                    # the visitor's problem: show a plain-language page (JSON callers get a short message)
            if as_json:
                msgs = {413: 'That request was too large.', 429: 'Too many requests. Please wait a few minutes and try again.', 404: 'Not found.', 405: 'Not found.'}
                return jsonify(ok=False, message=msgs.get(status, 'That request could not be understood.')), (404 if status == 405 else status)
            return status_page(404 if status == 405 else (status if status in PAGES else 400), status=404 if status == 405 else None)
        if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json':
            return jsonify(ok=False, message='Something went wrong. Please try again.'), 500
        try:
            return error_page(500)
        except Exception:                                          # noqa: BLE001
            return 'Something went wrong. Please try again in a moment.', 500, {'Content-Type': 'text/plain; charset=utf-8'}

    @app.get('/status/<int:code>')
    def status_preview(code):                                      # lets staff see exactly what visitors see for each code
        if code not in PAGES:
            return status_page(404)
        return status_page(code)

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT') or 3000)
    print(f'Prashi Tutorial running at http://localhost:{port}')
    app.run(host='0.0.0.0' if PROD else '127.0.0.1', port=port, debug=False, threaded=True)
