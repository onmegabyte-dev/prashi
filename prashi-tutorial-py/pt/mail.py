"""Email. Never raises: a mail problem must not stop a form submission being saved."""
import os
import smtplib
import ssl
import threading
from email.message import EmailMessage

from . import db  # noqa: F401  (loads .env)


def _send(to, subject, text, reply_to):
    try:
        host, port = os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT') or 587)
        msg = EmailMessage()
        msg['From'] = os.environ.get('MAIL_FROM') or os.environ.get('SMTP_USER') or 'noreply@localhost'
        msg['To'] = to
        msg['Subject'] = subject
        if reply_to:
            msg['Reply-To'] = reply_to
        msg.set_content(text)
        ctx = ssl.create_default_context()
        if port == 465:                                     # 465 = encrypted from the start; 587 upgrades with STARTTLS
            smtp = smtplib.SMTP_SSL(host, port, timeout=20, context=ctx)
        else:
            smtp = smtplib.SMTP(host, port, timeout=20)
            smtp.ehlo()
            if smtp.has_extn('starttls'):
                smtp.starttls(context=ctx)
                smtp.ehlo()
        with smtp:
            if os.environ.get('SMTP_USER'):
                smtp.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASS', ''))
            smtp.send_message(msg)
    except Exception as e:                                  # noqa: BLE001
        print('Mail failed:', e)


def send_mail(to, subject, text, reply_to=None):
    if not to:
        return False
    if not os.environ.get('SMTP_HOST'):
        print(f'[mail not configured] would send to {to}: {subject}\n{text}\n')
        return False
    threading.Thread(target=_send, args=(to, subject, text, reply_to), daemon=True).start()
    return True
