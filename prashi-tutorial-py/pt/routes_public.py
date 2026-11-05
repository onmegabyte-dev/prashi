"""The public website: pages, the form-submission endpoint, robots.txt and the sitemap."""
import hashlib
import os

from flask import Blueprint, g, jsonify, request

from . import content
from .db import run
from .forms import FORM_NAMES, get_fields, validate
from .mail import send_mail
from .sanitize import text as strip_html
from .tz import iso_now
from .web import Limiter, body, client_ip, render, site_url

bp = Blueprint('public', __name__)


def faq_ld(lst):
    if not lst:
        return []
    return [{'@context': 'https://schema.org', '@type': 'FAQPage',
             'mainEntity': [{'@type': 'Question', 'name': f['question'],
                             'acceptedAnswer': {'@type': 'Answer', 'text': strip_html(f['answer_html'])}} for f in lst]}]


def S():
    return content.settings()


@bp.get('/')
def home():
    s, faqs = S(), content.faqs()
    return render('public/home', {
        'title': f"{s['site_name']} – {s['tagline']}", 'desc': s['hero_text'],
        'courses': content.courses()[:3], 'faculty': content.faculty(3), 'testimonials': content.testimonials(),
        'batches': content.upcoming_batches(4), 'faqs': faqs, 'notices': content.notices(), 'ld': faq_ld(faqs)})


@bp.get('/about')
def about():
    s = S()
    return render('public/about', {'title': f"About – {s['site_name']}", 'desc': f"About {s['site_name']}: our mission, journey and campus."})


@bp.get('/courses')
def courses():
    return render('public/courses', {'title': f"Courses – {S()['site_name']}",
                                     'desc': 'Search coaching courses by class, exam, subject, type and duration.', 'courses': content.courses()})


@bp.get('/courses/<slug>')
def course(slug):
    c = content.course(slug)
    if not c:
        from flask import abort
        abort(404)
    faqs, s = content.faqs(c['id']), S()
    ld = {'@context': 'https://schema.org', '@type': 'Course', 'name': c['name'],
          'description': '. '.join(c['highlightList']) or c['name'],
          'provider': {'@type': 'EducationalOrganization', 'name': s['site_name'], 'url': site_url()}}
    if c['fee_amount']:
        ld['offers'] = {'@type': 'Offer', 'price': c['fee_amount'], 'priceCurrency': 'INR'}
    return render('public/course', {
        'title': f"{c['name']} – {s['site_name']}",
        'desc': f"{c['name']} ({c['class_level'] or ''}, {c['duration'] or ''}). {'. '.join(c['highlightList'])}.",
        'c': c, 'batches': content.course_batches(c['id']), 'faqs': faqs, 'ld': [ld, *faq_ld(faqs)]})


@bp.get('/faculty')
def faculty():
    return render('public/faculty', {'title': f"Faculty – {S()['site_name']}", 'desc': 'Meet our teachers, their qualifications and focus areas.',
                                     'faculty': content.faculty()})


@bp.get('/results')
def results():
    return render('public/results', {
        'title': f"Results – {S()['site_name']}", 'desc': 'Rank holders, success rates and student stories.',
        'ranks': content.results('rank'), 'years': content.results('year_stat'), 'improvement': content.results('improvement'),
        'testimonials': content.testimonials()})


@bp.get('/resources')
def resources():
    return render('public/resources', {'title': f"Resources – {S()['site_name']}", 'desc': 'Free guides, exam plans and news.',
                                       'articles': content.articles()})


@bp.get('/resources/<slug>')
def article(slug):
    a = content.article(slug)
    if not a:
        from flask import abort
        abort(404)
    return render('public/article', {
        'title': f"{a['title']} – {S()['site_name']}", 'desc': a['summary'] or a['title'], 'a': a,
        'ld': [{'@context': 'https://schema.org', '@type': 'Article', 'headline': a['title'],
                'datePublished': a['publish_at'] or a['created_at'],
                'publisher': {'@type': 'EducationalOrganization', 'name': S()['site_name']}}]})


@bp.get('/admissions')
def admissions():
    return render('public/admissions', {
        'title': f"Admissions – {S()['site_name']}", 'desc': 'Register, book free counselling and see admission steps and dates.',
        'admission': get_fields('admission'), 'counselling': get_fields('counselling'), 'pick': str(request.args.get('c', ''))})


@bp.get('/contact')
def contact():
    return render('public/contact', {'title': f"Contact – {S()['site_name']}", 'desc': 'Visit, call or message us.',
                                     'contact': get_fields('contact'), 'holidays': content.holidays()})


@bp.get('/privacy')
def privacy():
    return render('public/privacy', {'title': f"Privacy Policy – {S()['site_name']}", 'desc': 'How we collect and protect your information.'})


@bp.get('/terms')
def terms():
    return render('public/terms', {'title': f"Terms – {S()['site_name']}", 'desc': 'Terms and conditions.'})


# ── Form submissions (JSON). Validated against the Form Builder fields on the server. ──
form_limiter = Limiter(10 * 60, int(os.environ.get('FORM_RATE_LIMIT') or 8))

TITLES = {'admission': 'New admission registration', 'enquiry': 'New enquiry', 'counselling': 'New counselling request', 'contact': 'New website message'}
DONE = {
    'admission': 'Registration received. A counsellor will call you within one working day.',
    'counselling': 'Request received. We will call you back today.',
    'enquiry': 'Enquiry received. We will get back to you within one working day.',
    'contact': 'Message sent. We reply within one working day.',
}


@bp.post('/forms/<form>')
def submit_form(form):
    if not form_limiter.hit(client_ip()):
        return jsonify(ok=False, message='Too many submissions. Please wait a few minutes and try again.'), 429
    if form not in FORM_NAMES:
        return jsonify(ok=False, message='Unknown form.'), 404
    b = body()
    if b.get('website'):                                           # honeypot: bots fill this in; pretend success
        return jsonify(ok=True, message=DONE[form])
    values, errors = validate(form, b)
    if b.get('consent') not in (True, 'on', 'true'):
        errors['_consent'] = 'Please tick the box to agree to our Privacy Policy.'
    if errors:
        return jsonify(ok=False, message='Please fix the highlighted fields.', errors=errors), 422
    import json
    ip_hash = hashlib.sha256((client_ip() + os.environ.get('SESSION_SECRET', '')).encode()).hexdigest()[:32]
    run('INSERT INTO submissions (form, data_json, consent_at, ip_hash) VALUES (?,?,?,?)', form, json.dumps(values, ensure_ascii=False), iso_now(), ip_hash)
    labels = {f['name']: f['label'] for f in get_fields(form)}
    s = S()
    subject = f"{TITLES[form]} – {values.get('student_name') or values.get('name') or ''}"
    import re
    subject = re.sub(r'[\r\n]+', ' ', subject)[:150].strip()
    send_mail(s.get('admin_inbox_email'), subject,
              '\n'.join(f'{labels.get(k, k)}: {v}' for k, v in values.items()) + '\n\nOpen the admin inbox to follow up.',
              reply_to=values.get('email'))
    return jsonify(ok=True, message=DONE[form])


# ── SEO files ──
@bp.get('/robots.txt')
def robots():
    return (f'User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /portal\nDisallow: /forms\nSitemap: {site_url()}/sitemap.xml\n',
            200, {'Content-Type': 'text/plain; charset=utf-8'})


@bp.get('/sitemap.xml')
def sitemap():
    urls = ['/', '/about', '/courses', '/faculty', '/results', '/resources', '/admissions', '/contact', '/privacy',
            *['/courses/' + c['slug'] for c in content.courses()], *['/resources/' + a['slug'] for a in content.articles()]]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + ''.join(f'<url><loc>{site_url()}{u}</loc></url>' for u in urls) + '</urlset>')
    return xml, 200, {'Content-Type': 'application/xml; charset=utf-8'}
