"""Small OpenAI-compatible HTTP client using only the Python standard library."""

from __future__ import annotations

import base64
import ipaddress
import json
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from flask import current_app


class AIProviderError(RuntimeError):
    """Raised when a configured model endpoint cannot complete a request."""

    def __init__(self, message: str, *, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


MAX_REQUEST_BYTES = 8 * 1024 * 1024
RETRYABLE_HTTP_STATUSES = {408, 500, 502, 503, 504}


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

    url = _completion_url()
    _enforce_test_provider_guard(url)
    if image_bytes is not None and len(image_bytes) > MAX_REQUEST_BYTES:
        raise AIProviderError("Ảnh gửi tới mô hình AI vượt giới hạn yêu cầu.")

    request_messages = messages
    if image_bytes is not None:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        last = dict(messages[-1])
        last["content"] = [
            {"type": "text", "text": str(last.get("content", ""))},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
        ]
        request_messages = [*messages[:-1], last]

    try:
        request_body = {
            "model": current_app.config["AI_MODEL"],
            "messages": request_messages,
            "temperature": 0.2,
        }
        reasoning_effort = str(current_app.config.get("AI_REASONING_EFFORT", "") or "").strip().lower()
        if reasoning_effort:
            if reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
                raise AIProviderError("AI_REASONING_EFFORT configuration is invalid.")
            request_body["reasoning_effort"] = reasoning_effort
            request_body["max_completion_tokens"] = 700
        else:
            request_body["max_tokens"] = 700
        body = json.dumps(request_body).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AIProviderError("Yêu cầu AI không đúng định dạng.") from exc
    if len(body) > MAX_REQUEST_BYTES:
        raise AIProviderError("Yêu cầu AI vượt giới hạn dung lượng cho phép.")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = current_app.config.get("AI_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=body, headers=headers, method="POST")

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
    except HTTPError as exc:
        raise AIProviderError(
            "Không kết nối được mô hình AI đã cấu hình.",
            retryable=exc.code in RETRYABLE_HTTP_STATUSES,
            status_code=exc.code,
        ) from exc
    except URLError as exc:
        retryable = not isinstance(exc.reason, ssl.SSLError)
        raise AIProviderError(
            "Không kết nối được mô hình AI đã cấu hình.", retryable=retryable
        ) from exc
    except (TimeoutError, socket.timeout, OSError) as exc:
        raise AIProviderError("Không kết nối được mô hình AI đã cấu hình.", retryable=True) from exc
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AIProviderError("Mô hình AI trả về JSON không hợp lệ.") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError("Mô hình AI trả về dữ liệu không đúng định dạng.") from exc
    if isinstance(content, list):
        content = "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise AIProviderError("Mô hình AI chưa trả lời nội dung.")
    return content.strip()[:4000]


def complete_vision(messages: list[dict], image_bytes: bytes) -> str:
    """Vision-only bounded retry; never retries malformed output or HTTP 4xx."""
    configured_retries = int(current_app.config.get("AI_VISION_MAX_RETRIES", 1))
    retries = min(max(configured_retries, 0), 1)
    for attempt in range(retries + 1):
        try:
            return complete(messages, image_bytes=image_bytes)
        except AIProviderError as exc:
            if not exc.retryable or attempt >= retries:
                raise
            time.sleep(0.1 * (attempt + 1))
    raise AIProviderError("Không kết nối được mô hình ảnh đã cấu hình.")


def _enforce_test_provider_guard(url: str) -> None:
    """Block all external provider egress in tests; allow explicit literal loopback only."""
    if current_app.config.get("APP_ENV") != "test":
        return
    parsed = urlparse(url)
    try:
        loopback = ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        loopback = False
    if not (loopback and current_app.config.get("AI_TEST_ALLOW_LOOPBACK_PROVIDER")):
        raise AIProviderError("AI provider requests are disabled in tests except to an explicitly enabled loopback mock.")
