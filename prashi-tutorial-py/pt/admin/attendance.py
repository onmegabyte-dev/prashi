"""Attendance: mark who came to class, batch by batch."""
import re

from flask import Blueprint, redirect, request

from ..audit import audit
from ..db import all_, run
from ..tz import today_local, valid_day
from ..web import body, days_ago, flash, render

bp = Blueprint('attendance', __name__)
STATUS = [['present', 'Present'], ['absent', 'Absent'], ['late', 'Late'], ['excused', 'Excused']]


@bp.get('/', strict_slashes=False)
def index():
    batches = all_("SELECT b.id, c.name || ' – ' || b.name AS label FROM batches b JOIN courses c ON c.id = b.course_id WHERE b.status != 'closed' OR EXISTS (SELECT 1 FROM enrollments e WHERE e.batch_id = b.id AND e.status = 'active') ORDER BY c.name, b.name")
    batch_id = int(request.args['batch']) if re.fullmatch(r'\d+', request.args.get('batch', '')) else None
    day = request.args.get('day') if valid_day(request.args.get('day')) else today_local()
    roster = []
    if batch_id:
        since = days_ago(30)
        roster = all_("""SELECT u.id, u.name, s.admission_no, a.status, a.remark,
      (SELECT COUNT(*) FROM attendance x WHERE x.student_id = u.id AND x.batch_id = ? AND x.day >= ?) AS marked,
      (SELECT COUNT(*) FROM attendance x WHERE x.student_id = u.id AND x.batch_id = ? AND x.day >= ? AND x.status IN ('present','late')) AS here
      FROM enrollments e JOIN users u ON u.id = e.student_id JOIN students s ON s.user_id = u.id
      LEFT JOIN attendance a ON a.student_id = u.id AND a.batch_id = e.batch_id AND a.day = ?
      WHERE e.batch_id = ? AND e.status = 'active' AND u.active = 1 ORDER BY u.name""", batch_id, since, batch_id, since, day, batch_id)
    return render('admin/attendance', {
        'title': 'Attendance', 'nav': '/admin/attendance', 'batches': batches, 'batchId': batch_id, 'day': day, 'roster': roster, 'STATUS': STATUS,
        'help': '<p>Mark who came to class.</p><ol style="margin-left:20px"><li>Choose the <b>batch</b> and the <b>date</b>.</li><li>Everyone starts as <b>Present</b> – change only the exceptions.</li><li>Click <b>Save attendance</b>. You can come back and correct a day any time.</li></ol><p>Students see their own attendance in their portal; the “Last 30 days” column here is a quick view.</p>'})


@bp.post('/', strict_slashes=False)
def save():
    b = body()
    batch_id = int(b['batch']) if re.fullmatch(r'\d+', b.get('batch') or '') else None
    day = b.get('day')
    if not batch_id or not valid_day(day):
        flash('err', 'Choose a batch and a valid date.')
        return redirect('/admin/attendance')
    ids = [r['student_id'] for r in all_("SELECT e.student_id FROM enrollments e WHERE e.batch_id = ? AND e.status = 'active'", batch_id)]
    counts = {'present': 0, 'absent': 0, 'late': 0, 'excused': 0}
    for sid in ids:
        st = b.get(f's_{sid}') if any(s[0] == b.get(f's_{sid}') for s in STATUS) else 'present'
        run("""INSERT INTO attendance (student_id, batch_id, day, status, remark) VALUES (?,?,?,?,?)
        ON CONFLICT(student_id, batch_id, day) DO UPDATE SET status = excluded.status, remark = excluded.remark""",
            sid, batch_id, day, st, str(b.get(f'r_{sid}') or '').strip()[:200] or None)
        counts[st] += 1
    audit('update', 'attendance', batch_id, f"Marked attendance for {day}: {counts['present']} present, {counts['absent']} absent, {counts['late']} late, {counts['excused']} excused")
    flash('ok', f'Attendance saved for {len(ids)} students.')
    return redirect(f'/admin/attendance?batch={batch_id}&day={day}')
