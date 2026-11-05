"""Fee receipts: loads one payment with everything printed on it, and writes the amount in words (Indian system)."""
import re

from .db import one

ONES = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen',
        'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']


def _below100(n):
    return ONES[n] if n < 20 else TENS[n // 10] + ('-' + ONES[n % 10] if n % 10 else '')


def _below1000(n):
    return ONES[n // 100] + ' Hundred' + (' ' + _below100(n % 100) if n % 100 else '') if n >= 100 else _below100(n)


def rupees_in_words(amount):
    """145000 -> 'One Lakh Forty-Five Thousand Rupees Only'"""
    try:
        n = int(abs(float(amount or 0)))
    except (TypeError, ValueError):
        n = 0
    if n == 0:
        return 'Zero Rupees Only'
    parts = []
    for size, name in ((10000000, 'Crore'), (100000, 'Lakh'), (1000, 'Thousand')):
        if n >= size:
            parts.append(_below1000(n // size) + ' ' + name)
            n %= size
    if n:
        parts.append(_below1000(n))
    return ' '.join(parts) + ' Rupees Only'


def load_receipt(payment_id, student_id=None):
    """Returns the receipt data, or None. Pass student_id to make sure the payment belongs to that student."""
    if not re.fullmatch(r'\d+', str(payment_id)):
        return None
    sql = """SELECT p.*, e.fee_total, e.discount, e.student_id, b.name AS batch_name, c.name AS course_name,
      u.name AS student_name, s.admission_no, s.class_level, s.parent_name, ru.name AS recorded_by_name,
      (SELECT COALESCE(SUM(p2.amount), 0) FROM payments p2 WHERE p2.enrollment_id = p.enrollment_id AND (p2.paid_on < p.paid_on OR (p2.paid_on = p.paid_on AND p2.id <= p.id))) AS paid_to_date
    FROM payments p JOIN enrollments e ON e.id = p.enrollment_id JOIN batches b ON b.id = e.batch_id JOIN courses c ON c.id = b.course_id
    JOIN users u ON u.id = e.student_id JOIN students s ON s.user_id = e.student_id LEFT JOIN users ru ON ru.id = p.recorded_by
    WHERE p.id = ?""" + (' AND e.student_id = ?' if student_id else '')
    r = one(sql, int(payment_id), *([student_id] if student_id else []))
    if not r:
        return None
    payable = r['fee_total'] - r['discount']
    return {**r, 'payable': payable, 'balance_after': payable - r['paid_to_date'], 'words': rupees_in_words(r['amount'])}
