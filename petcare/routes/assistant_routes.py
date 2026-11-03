from flask import Blueprint, g, jsonify, request, url_for

from petcare.auth import login_required
from petcare.services import assistant_service
from petcare.services import request_throttle_service
from petcare.services.exceptions import ServiceError
from petcare.i18n import translate
from petcare.money import format_money

bp = Blueprint("assistant", __name__, url_prefix="/assistant")


@bp.post("/chat")
@login_required
def chat():
    allowed, retry_after = request_throttle_service.consume_with_ip_limit(
        g.user["id"], request.remote_addr, "assistant"
    )
    if not allowed:
        return (
            jsonify(error=translate("Đã gửi nhiều câu hỏi từ tài khoản hoặc mạng này. Vui lòng thử lại sau.")),
            429,
            {"Retry-After": str(retry_after)},
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error=translate("Nội dung gửi lên chưa hợp lệ.")), 400
    if not isinstance(payload.get("message"), str):
        return jsonify(
            error=translate("Nội dung gửi lên chưa hợp lệ."),
            field="message", expected="string",
        ), 400
    try:
        response = assistant_service.answer(
            g.user["id"], payload.get("message"), payload.get("history"), locale=g.locale
        )
    except ServiceError as exc:
        return jsonify(error=translate(str(exc))), 400
    for item in response.get("catalog", {}).get("items", []):
        pet = item["kind"] == "pet"
        item["url"] = url_for("pets.detail", pet_id=item["id"]) if pet else url_for("products.detail", product_id=item["id"])
        item["price_label"] = format_money(item["price"], response.get("currency_code", g.tenant["default_currency"]), "en_US" if g.locale == "en" else "vi_VN")
        item["status_label"] = translate("Đang bán" if item["status"] in {"available", "active"} else "Đã bán" if item["status"] == "sold" else "Đã ngừng")
        filename = item.pop("photo_filename", None)
        item["photo_url"] = url_for("pets.photo" if pet else "products.photo", filename=filename) if filename else None
    return jsonify(response)
