"""Sends one test email so you can confirm your email settings work.   python scripts/test_email.py you@example.com"""
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pt import db  # noqa: E402,F401  (loads .env)

if len(sys.argv) < 2:
    sys.exit('Usage: python scripts/test_email.py your.name@example.com')
to = sys.argv[1]
if not os.environ.get('SMTP_HOST'):
    sys.exit('SMTP_HOST is empty in your .env file – email is not set up yet. See README, "Set up email".')
try:
    host, port = os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT') or 587)
    msg = EmailMessage()
    msg['From'] = os.environ.get('MAIL_FROM') or os.environ.get('SMTP_USER')
    msg['To'] = to
    msg['Subject'] = 'Prashi Tutorial – test email'
    msg.set_content('If you can read this, email is working. Enquiry alerts and password-reset emails will be delivered.')
    ctx = ssl.create_default_context()
    smtp = smtplib.SMTP_SSL(host, port, timeout=20, context=ctx) if port == 465 else smtplib.SMTP(host, port, timeout=20)
    with smtp:
        if port != 465:
            smtp.ehlo()
            if smtp.has_extn('starttls'):
                smtp.starttls(context=ctx)
                smtp.ehlo()
        if os.environ.get('SMTP_USER'):
            smtp.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASS', ''))
        smtp.send_message(msg)
    print('Sent! Check the inbox (and the spam folder) of ' + to)
except Exception as e:                                              # noqa: BLE001
    sys.exit(f'FAILED: {e}\nCheck SMTP_HOST, SMTP_PORT, SMTP_USER and SMTP_PASS in .env. For Gmail you need an "App password", not your normal password.')
