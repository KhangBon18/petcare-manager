"""Small OpenAI-compatible HTTP client using only the Python standard library."""

from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from flask import current_app


class AIProviderError(RuntimeError):
    """Raised when a configured model endpoint cannot complete a request."""


def is_configured() -> bool:
    return bool(current_app.config.get("AI_API_BASE_URL") and current_app.config.get("AI_MODEL"))


def _completion_url() -> str:
    base_url = current_app.config["AI_API_BASE_URL"].strip().rstrip("/")
    try:
        parsed = urlparse(base_url)
        _ = parsed.port
    except ValueError as exc:
        raise AIProviderError("Địa chỉ AI endpoint không hợp lệ.") from exc
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise AIProviderError("Địa chỉ AI endpoint cần dùng http hoặc https.")
    if (
        current_app.config.get("APP_ENV") == "production"
        and parsed.scheme != "https"
        and not current_app.config.get("AI_ALLOW_HTTP_ENDPOINT")
    ):
        raise AIProviderError(
            "Production chỉ gửi dữ liệu AI qua HTTPS; chỉ bật ngoại lệ cho endpoint mạng nội bộ tin cậy."
        )
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"


def complete(messages: list[dict], image_bytes: bytes | None = None) -> str:
    """Call a configured OpenAI-compatible model endpoint.

    The caller decides which information is included in messages. Images are
    sent only when the separate AI_VISION_ENABLED setting is enabled.
    """
    if not is_configured():
        raise AIProviderError("Chưa cấu hình mô hình AI.")

    request_messages = messages
    if image_bytes is not None:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        last = dict(messages[-1])
        last["content"] = [
            {"type": "text", "text": str(last.get("content", ""))},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
        ]
        request_messages = [*messages[:-1], last]

    body = json.dumps({
        "model": current_app.config["AI_MODEL"],
        "messages": request_messages,
        "temperature": 0.2,
        "max_tokens": 700,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = current_app.config.get("AI_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(_completion_url(), data=body, headers=headers, method="POST")

    class NoRedirectHandler(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, new_url):
            return None

    max_response_bytes = 512_000
    try:
        opener = build_opener(NoRedirectHandler())
        with opener.open(request, timeout=int(current_app.config.get("AI_TIMEOUT_SECONDS", 15))) as response:
            raw_payload = response.read(max_response_bytes + 1)
            if len(raw_payload) > max_response_bytes:
                raise AIProviderError("Mô hình AI trả về dữ liệu vượt giới hạn cho phép.")
            payload = json.loads(raw_payload.decode("utf-8"))
    except AIProviderError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise AIProviderError("Không kết nối được mô hình AI đã cấu hình.") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError("Mô hình AI trả về dữ liệu không đúng định dạng.") from exc
    if isinstance(content, list):
        content = "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise AIProviderError("Mô hình AI chưa trả lời nội dung.")
    return content.strip()[:4000]
