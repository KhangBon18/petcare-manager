"""Staff/Admin workflow blueprint for incoming online Storefront orders."""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from petcare.auth import login_required
from petcare.services import storefront_service
from petcare.services.exceptions import ServiceError


bp = Blueprint("orders", __name__, url_prefix="/orders")


@bp.get("/")
@login_required
def index():
    status = request.args.get("status", "")
    search = request.args.get("q", "")
    listing = storefront_service.list_staff_orders(
        g.user["id"],
        search=search,
        status=status,
        page=request.args.get("page", "1"),
        tenant_id=g.tenant_id,
    )
    status_labels = (
        storefront_service.ORDER_STATUS_LABELS_EN
        if g.locale == "en"
        else storefront_service.ORDER_STATUS_LABELS_VI
    )
    return render_template(
        "orders/index.html",
        orders=listing["items"],
        pagination=listing["pagination"],
        search=search,
        status=status,
        status_labels=status_labels,
    )


@bp.get("/<int:order_id>")
@login_required
def detail(order_id: int):
    try:
        order = storefront_service.get_staff_order(
            g.user["id"], order_id, tenant_id=g.tenant_id
        )
    except ServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("orders.index"))
    status_labels = (
        storefront_service.ORDER_STATUS_LABELS_EN
        if g.locale == "en"
        else storefront_service.ORDER_STATUS_LABELS_VI
    )
    return render_template("orders/detail.html", order=order, status_labels=status_labels)


@bp.post("/<int:order_id>/process")
@login_required
def process(order_id: int):
    action = request.form.get("action", "")
    staff_note = request.form.get("staff_note", "")
    try:
        result = storefront_service.process_staff_order(
            g.user["id"],
            order_id,
            action,
            staff_note=staff_note,
            tenant_id=g.tenant_id,
        )
        if result["status"] in {"unchanged", "already_completed"}:
            flash("Trạng thái đơn hàng đã được cập nhật trước đó.", "info")
        elif action == "confirm":
            flash("Đã xác nhận đơn hàng và giữ cá thể thú cưng (nếu có).", "success")
        elif action == "prepare":
            flash("Đã chuyển đơn sang trạng thái đang chuẩn bị.", "success")
        elif action == "complete_payment":
            flash("Đã hoàn tất đơn hàng, ghi nhận thanh toán, tạo hóa đơn và cập nhật tồn kho.", "success")
        elif action == "reject":
            flash("Đã từ chối đơn hàng và giải phóng trạng thái giữ hàng.", "warning")
        elif action == "cancel":
            flash("Đã hủy đơn hàng và giải phóng trạng thái giữ hàng.", "info")
    except ServiceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("orders.detail", order_id=order_id))

