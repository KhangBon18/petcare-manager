from flask import Blueprint, g, redirect, render_template, url_for

from petcare.auth import login_required
from petcare.services import report_service

bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    if g.user:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@bp.get("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        metrics=report_service.dashboard(g.user["id"]),
    )
