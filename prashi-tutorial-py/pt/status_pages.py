"""Friendly pages for HTTP status codes, written for students and parents (no technical words).
status_page(404) renders the page and returns (html, 404)."""
from flask import g, request

from . import web

# code: (heading, what happened, [what you can do], tone)
PAGES = {
    201: ('Done – it has been saved', 'Your request was received and saved. You do not need to do anything else.',
          ['You can safely close this page.', 'If you expected an email or a call, our team will contact you soon.'], 'ok'),
    400: ('We could not understand that', 'Something in the form or the link was not right, so we could not go ahead.',
          ['Go back and check that every box is filled in correctly.', 'If you opened an old or copied link, open the page again from the menu.',
           'Still stuck? Call or message the office and we will help.'], 'warn'),
    401: ('Please sign in first', 'You need to sign in before you can open this page.',
          ['Press “Sign in” and enter your email (or username) and password.', 'Forgot your password? Use “Forgot password” on the sign-in page.'], 'warn'),
    403: ('You cannot open this page', 'This page is not meant for your account. Your login is fine – this part is only for someone else, such as the teachers or the office.',
          ['Go back to your own page using the button below.', 'If you think you should have access, ask the office.'], 'warn'),
    404: ('We could not find that page', 'The link may be old, or the address may have a small typing mistake.',
          ['Check the address for spelling mistakes.', 'Use the menu at the top, or go to the home page.'], 'warn'),
    413: ('That file is too big', 'The file you tried to send is larger than we allow, so nothing was saved.',
          ['Try a smaller file (up to 20 MB; pictures up to 5 MB).', 'For a photo, use a lower-quality or resized picture.'], 'warn'),
    429: ('Too many tries – please wait', 'You did that too many times in a short time, so we paused it to keep everyone’s account safe. Your information is safe.',
          ['Wait about 15 minutes, then try again.', 'Please do not keep pressing the button – that makes the wait longer.'], 'warn'),
    500: ('Something went wrong on our side', 'This is not your mistake. Nothing you did caused it.',
          ['Wait a minute and try again.', 'If it keeps happening, tell the office what you were doing.'], 'warn'),
}
ALIASES = {405: 404, 422: 400, 408: 400}


def actions(code):
    u = getattr(g, 'user', None)
    home = ('Go to home page', '/')
    mine = [('Go to my ' + ('portal' if u['role'] == 'student' else 'admin panel'), web.home_for(u['role']))] if u else []
    if code == 401:
        nxt = '?next=' + web.js_quote(request.path) if request.method == 'GET' and request.path not in ('/login', '/') else ''
        return [('Sign in', '/login' + nxt), ('Forgot password', '/forgot'), home]
    if code == 403:
        return (mine or [('Sign in', '/login')]) + [home]
    if code == 429:
        return [('Try again', request.path if request.method == 'GET' else '/'), home]
    if code in (400, 413):
        return [('Go back', 'javascript:history.back()'), home]
    if code == 404:
        return [home, ('See our courses', '/courses'), ('Contact us', '/contact')]
    if code == 201:
        return (mine or []) + [home]
    return [('Try again', request.path if request.method == 'GET' else '/'), home]


def status_page(code, message=None, status=None):
    """Render the page for `code`. `message` replaces the "what happened" sentence; `status` overrides the HTTP status sent."""
    key = ALIASES.get(code, code)
    title, text, tips, tone = PAGES.get(key, PAGES[500])
    return web.render('public/error', {
        'noindex': True, 'flash': None, 'code': key, 'title': title, 'message': message or text, 'tips': tips, 'tone': tone, 'actions': actions(key),
        'desc': '', 'ld': [], 'waLink': '', 'map': '', 'site': '', 'canonical': '', 'ogImage': '', 'orgLd': None}, status or key)
