"""Everything under /admin. app.py has already required a signed-in admin or staff user;
admin-only sections add their own check below."""
from flask import Blueprint, g, request

bp = Blueprint('admin', __name__)


@bp.before_request
def area():
    g.locals.update(noindex=True, nav=request.path)


from . import (attendance, crud, data_export, formbuilder, inbox, misc, pages, qbank, records, settings,  # noqa: E402,F401
               student_import, students)

bp.register_blueprint(crud.bp, url_prefix='/c')
bp.register_blueprint(formbuilder.bp, url_prefix='/forms')
bp.register_blueprint(settings.bp, url_prefix='/settings')
bp.register_blueprint(pages.bp, url_prefix='/pages')
bp.register_blueprint(inbox.bp, url_prefix='/inbox')
bp.register_blueprint(student_import.bp, url_prefix='/students/import')       # "import" is never read as a student id
bp.register_blueprint(students.bp, url_prefix='/students')
bp.register_blueprint(records.bp, url_prefix='/records')
bp.register_blueprint(qbank.bp, url_prefix='/qbank')
bp.register_blueprint(attendance.bp, url_prefix='/attendance')
bp.register_blueprint(data_export.bp, url_prefix='/data-export')
bp.register_blueprint(misc.bp, url_prefix='')
