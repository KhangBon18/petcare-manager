from io import BytesIO
from flask import Blueprint, flash, g, jsonify, render_template, request, send_file

from petcare.auth import login_required
from petcare.i18n import translate
from petcare.services import report_service, report_export_service
from petcare.services.exceptions import ServiceError
from petcare.services.ui_text import ui_text

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.get("/")
@login_required
def index():
    try:
        report = report_service.report(
            g.user["id"],
            request.args.get("start"),
            request.args.get("end"),
            request.args.get("period"),
            tenant_id=g.tenant_id,
        )
    except (ServiceError, ValueError, OverflowError) as exc:
        return render_template("reports/error.html", message=translate(str(exc))), 400
    token = report_export_service.snapshot(report, g.user["id"], g.tenant["id"])
    return render_template("reports/index.html", report=report, report_snapshot=token)


@bp.post("/export.xlsx")
@login_required
def export_xlsx():
    payload = request.get_json(silent=True) if request.is_json else request.form
    if not isinstance(payload, dict) and not hasattr(payload, "get"):
        return (
            jsonify(
                error=ui_text(
                    "Nội dung báo cáo không hợp lệ.", "Invalid report payload."
                )
            ),
            400,
        )
    if not payload or not isinstance(payload.get("snapshot"), str):
        return (
            jsonify(
                error=ui_text(
                    "Thiếu bản chốt số liệu báo cáo.", "The report snapshot is missing."
                )
            ),
            400,
        )
    try:
        report = report_export_service.read_snapshot(
            payload["snapshot"], g.user["id"], g.tenant["id"]
        )
        content = report_export_service.workbook_bytes(report, g.locale)
    except ServiceError as exc:
        return jsonify(error=translate(str(exc))), 400
    return send_file(
        BytesIO(content),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"PetCare-{report['start_date']}-{report['end_date']}.xlsx",
        max_age=0,
    )
