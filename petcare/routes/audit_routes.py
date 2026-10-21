from flask import Blueprint, g, render_template, request

from petcare.auth import admin_required
from petcare.services import audit_service


bp = Blueprint("audit", __name__, url_prefix="/activity")


@bp.get("/")
@admin_required
def index():
    listing = audit_service.list_events(g.user["id"], request.args.get("page", "1"))
    return render_template(
        "audit/index.html",
        events=listing["items"],
        pagination=listing["pagination"],
    )
