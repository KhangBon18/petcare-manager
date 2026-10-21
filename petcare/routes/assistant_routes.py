from flask import Blueprint, g, jsonify, request

from petcare.auth import login_required
from petcare.services import assistant_service
from petcare.services import request_throttle_service
from petcare.services.exceptions import ServiceError
from petcare.i18n import translate

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
    try:
        response = assistant_service.answer(
            g.user["id"], payload.get("message"), payload.get("history"), locale=g.locale
        )
    except ServiceError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(response)
