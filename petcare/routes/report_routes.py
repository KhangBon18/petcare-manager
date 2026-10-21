from flask import Blueprint, flash, g, render_template, request

from petcare.auth import login_required
from petcare.services import report_service
from petcare.services.exceptions import ServiceError

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.get("/")
@login_required
def index():
    try:
        report = report_service.report(
            g.user["id"], request.args.get("start"), request.args.get("end")
        )
    except (ServiceError, ValueError) as exc:
        flash(str(exc), "error")
        report = report_service.report(g.user["id"])
    return render_template("reports/index.html", report=report)
