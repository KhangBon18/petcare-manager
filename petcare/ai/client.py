"""Small OpenAI-compatible & Google Gemini HTTP client using only the Python standard library."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
import base64
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from flask import current_app, has_app_context

from petcare.config import Config

_SAFE_UPSTREAM_CODE_RE = re.compile(r"^[A-Za-z0-9_.:-]{2,64}$")
_DIAG_SCRUB_RE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{12,}|Bearer\s+\S+|https?://\S+|"
    r"(?:api[_-]?key|secret|password|token)\s*[:=]\s*\S+|"
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|\b(?:\+?84|0)\d{8,11}\b)",
    re.IGNORECASE,
)


def _sanitize_diagnostic_detail(raw_text: str | None, max_len: int = 160) -> str | None:
    if not raw_text or not isinstance(raw_text, str):
        return None
    scrubbed = _DIAG_SCRUB_RE.sub("[REDACTED]", raw_text)
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "AI_API_KEY"):
        secret_val = os.getenv(env_name, "").strip()
        if len(secret_val) >= 8 and secret_val in scrubbed:
            scrubbed = scrubbed.replace(secret_val, "[REDACTED]")
    collapsed = re.sub(r"\s+", " ", scrubbed).strip()
    return collapsed[:max_len] if collapsed else None


class AIProviderError(RuntimeError):
    """Raised when a configured model endpoint cannot complete a request (carries secret-free diagnostics)."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        error_category: str = "provider_error",
        upstream_error_code: str | None = None,
        sanitized_detail: str | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.error_category = error_category
        self.upstream_error_code = upstream_error_code
        self.sanitized_detail = _sanitize_diagnostic_detail(sanitized_detail)

    def to_diagnostic_dict(self) -> dict[str, Any]:
        return {
            "error_category": self.error_category,
            "http_status": self.status_code,
            "upstream_error_code": self.upstream_error_code,
            "retryable": self.retryable,
            "sanitized_detail": self.sanitized_detail,
        }


class AIRateLimitError(AIProviderError):
    """Raised when local Free-Tier throttling or upstream HTTP 429 blocks a request.

    Intentionally `retryable=False` so callers degrade immediately to grounded Offline Python
    rather than hammering a quota-exhausted Free Tier bucket or switching to any paid model.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        source: str = "upstream_429",
        upstream_error_code: str | None = "RESOURCE_EXHAUSTED",
        sanitized_detail: str | None = None,
    ):
        super().__init__(
            message,
            retryable=False,
            status_code=429,
            error_category="http_429_rate_limited" if source == "upstream_429" else f"rate_limit:{source}",
            upstream_error_code=upstream_error_code,
            sanitized_detail=sanitized_detail,
        )
        self.retry_after_seconds = retry_after_seconds
        self.source = source


def _classify_http_status(status_code: int) -> str:
    if status_code == 400:
        return "http_400_bad_request"
    if status_code == 401:
        return "http_401_unauthorized"
    if status_code == 403:
        return "http_403_forbidden"
    if status_code == 404:
        return "http_404_not_found"
    if status_code == 408:
        return "http_408_timeout"
    if status_code == 422:
        return "http_422_unprocessable"
    if status_code == 429:
        return "http_429_rate_limited"
    if 500 <= status_code <= 599:
        return "http_5xx_upstream"
    return f"http_{status_code}"


def _extract_sanitized_http_error(exc: HTTPError) -> tuple[str, str | None, str | None]:
    """Extract secret-scrubbed category, upstream status enum, and short error hint from an HTTPError."""
    category = _classify_http_status(int(exc.code))
    upstream_code: str | None = None
    detail: str | None = None
    try:
        raw_bytes = exc.read(4096) if hasattr(exc, "read") else b""
        if raw_bytes:
            parsed = json.loads(raw_bytes.decode("utf-8", errors="replace"))
            # Gemini's `/v1beta/openai/` shim often returns a JSON array `[{"error": {...}}]`
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                parsed = parsed[0]
            if isinstance(parsed, dict):
                err_obj = parsed.get("error") if isinstance(parsed.get("error"), dict) else parsed
                for key in ("status", "type", "code"):
                    val = err_obj.get(key)
                    if val is not None:
                        cand = str(val).strip()
                        if _SAFE_UPSTREAM_CODE_RE.fullmatch(cand):
                            upstream_code = cand
                            break
                msg_val = err_obj.get("message")
                if isinstance(msg_val, str) and msg_val.strip():
                    detail = _sanitize_diagnostic_detail(msg_val)
    except Exception:  # nosec B110
        pass
    if detail is None and getattr(exc, "reason", None):
        detail = _sanitize_diagnostic_detail(str(exc.reason))
    return category, upstream_code, detail


MAX_REQUEST_BYTES = 8 * 1024 * 1024
RETRYABLE_HTTP_STATUSES = {408, 500, 502, 503, 504}
GEMINI_OPENAI_BASE_URL = Config.GEMINI_OPENAI_BASE_URL
DEFAULT_GEMINI_MODEL = Config.DEFAULT_GEMINI_MODEL

ALLOWED_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh", "max"})
ALLOWED_GEMINI_3_REASONING_EFFORTS = frozenset({"minimal", "low", "medium", "high"})
ALLOWED_GEMINI_25_REASONING_EFFORTS = frozenset({"none", "minimal", "low", "medium", "high"})

_REASONING_SERIES_MODEL_RE = re.compile(
    r"(?:^|/)(?:gpt-6(?:-[a-z0-9._-]+)?|gpt-5(?:[.-][a-z0-9._-]+)?|o1(?:-[a-z0-9._-]+)?|o3(?:-[a-z0-9._-]+)?|o4(?:-[a-z0-9._-]+)?)$",
    re.IGNORECASE,
)
_GEMINI_MODEL_RE = re.compile(r"^(?:models/|google/)?gemini-[a-z0-9._-]+$", re.IGNORECASE)
_GEMINI_3_PLUS_MODEL_RE = re.compile(r"^(?:models/|google/)?gemini-(?:[3-9]|\d{2,})(?:[.-]|$)", re.IGNORECASE)


def is_reasoning_series_model(model_name: str | None) -> bool:
    """Return True for OpenAI reasoning-first models (e.g., `gpt-6-luna`) requiring `max_completion_tokens`."""
    return bool(_REASONING_SERIES_MODEL_RE.match(str(model_name or "").strip()))


def is_gemini_model(model_name: str | None) -> bool:
    """Return True for Google Gemini model identifiers (e.g., `gemini-3.5-flash-lite`)."""
    return bool(_GEMINI_MODEL_RE.match(str(model_name or "").strip()))


def detect_provider_family(
    provider_raw: str | None,
    base_url: str | None,
    model_name: str | None,
) -> str:
    """Classify the active LLM provider into `'gemini'`, `'openai'`, or `'openai_compatible'`."""
    prov = str(provider_raw or "").strip().lower()
    if prov in {"gemini", "google", "google_gemini"}:
        return "gemini"
    if prov == "openai":
        return "openai"
    if prov == "openai_compatible":
        return "openai_compatible"

    cleaned_url = str(base_url or "").strip()
    if cleaned_url:
        try:
            host = (urlparse(cleaned_url).hostname or "").strip().lower()
        except ValueError:
            host = ""
        if host.endswith("generativelanguage.googleapis.com") or host.endswith("aiplatform.googleapis.com"):
            return "gemini"
        if host == "api.openai.com":
            return "openai"

    cleaned_model = str(model_name or "").strip()
    if is_gemini_model(cleaned_model):
        return "gemini"
    if is_reasoning_series_model(cleaned_model) or cleaned_model.lower().startswith("gpt-"):
        return "openai"
    return "openai_compatible"


def resolve_provider_connection_settings(cfg: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Resolve provider family, effective endpoint, model name, and secret source without exposing secret values."""
    if cfg is None:
        if has_app_context():
            cfg = current_app.config
        else:
            cfg = {
                "AI_PROVIDER": Config.AI_PROVIDER,
                "AI_API_BASE_URL": Config.AI_API_BASE_URL,
                "AI_API_KEY": Config.AI_API_KEY,
                "GEMINI_API_KEY": Config.GEMINI_API_KEY,
                "AI_MODEL": Config.AI_MODEL,
            }

    raw_provider = str(cfg.get("AI_PROVIDER") or "").strip().lower()
    raw_base_url = str(cfg.get("AI_API_BASE_URL") or "").strip()
    raw_model = str(cfg.get("AI_MODEL") or "").strip()
    gemini_key = str(cfg.get("GEMINI_API_KEY") or "").strip()
    ai_key = str(cfg.get("AI_API_KEY") or "").strip()

    explicit_gemini = raw_provider in {"gemini", "google", "google_gemini"}
    base_url = raw_base_url or (GEMINI_OPENAI_BASE_URL if explicit_gemini else "")
    model_name = raw_model or (DEFAULT_GEMINI_MODEL if explicit_gemini else "")
    provider_family = detect_provider_family(raw_provider, base_url, model_name)

    if provider_family == "gemini":
        if gemini_key:
            api_key = gemini_key
            api_key_source = "GEMINI_API_KEY"
        elif ai_key:
            api_key = ai_key
            api_key_source = "AI_API_KEY"
        else:
            api_key = ""
            api_key_source = "none"
    else:
        if ai_key:
            api_key = ai_key
            api_key_source = "AI_API_KEY"
        else:
            api_key = ""
            api_key_source = "none"

    return {
        "provider_raw": raw_provider,
        "provider_family": provider_family,
        "base_url": base_url,
        "model_name": model_name,
        "api_key": api_key,
        "api_key_present": bool(api_key),
        "api_key_source": api_key_source,
    }


def normalize_messages_for_provider(
    messages: list[dict[str, Any]],
    provider_family: str,
) -> list[dict[str, Any]]:
    """Coalesce consecutive plain-text `user` turns for Gemini's strict turn-alternation validator.

    Gemini's `/v1beta/openai/chat/completions` translator rejects adjacent `role == 'user'` messages
    with `HTTP 400 INVALID_ARGUMENT`. Merging adjacent plain-text user messages preserves full context
    while keeping `system`, `assistant`, `tool`, and multimodal content blocks intact.
    """
    if provider_family != "gemini" or not messages:
        return messages
    normalized: list[dict[str, Any]] = []
    for msg in messages:
        if (
            normalized
            and msg.get("role") == "user"
            and normalized[-1].get("role") == "user"
            and isinstance(msg.get("content"), str)
            and isinstance(normalized[-1].get("content"), str)
        ):
            merged_prev = dict(normalized[-1])
            merged_prev["content"] = f"{merged_prev['content']}\n\n{msg['content']}"
            normalized[-1] = merged_prev
        else:
            normalized.append(msg)
    return normalized


def build_gemini_final_synthesis_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a post-tool conversation into a protocol-valid, tool-free Gemini synthesis payload.

    Google Gemini's `/v1beta/openai/chat/completions` endpoint can still emit `finish_reason='tool_calls'`
    (including unconstrained function names) when `tools` remain present alongside `tool_choice='none'`,
    yet rejects `role == 'tool'` / `assistant.tool_calls` history with `HTTP 400` if `tools` is simply omitted.
    Converting verified Python tool outputs into `VERIFIED_PYTHON_TOOL_RESULTS_JSON` inside a clean
    `system` + plain conversation history + `user` payload allows omitting `tools` completely so Gemini
    is guaranteed to generate a grounded natural-language answer with zero tool invocations.
    """
    if not messages:
        return []
    has_tool_exchange = any(
        msg.get("role") == "tool" or bool(msg.get("tool_calls"))
        for msg in messages
        if isinstance(msg, dict)
    )
    if not has_tool_exchange:
        return normalize_messages_for_provider(messages, "gemini")

    system_parts: list[str] = []
    plain_turns: list[dict[str, str]] = []
    call_meta_by_id: dict[str, dict[str, Any]] = {}
    ordered_call_meta: list[dict[str, Any]] = []
    verified_tool_results: list[dict[str, Any]] = []
    tool_obs_idx = 0

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role == "system":
            if isinstance(msg.get("content"), str) and msg["content"].strip():
                system_parts.append(msg["content"].strip())
            continue

        if role == "assistant" and isinstance(msg.get("tool_calls"), list) and msg["tool_calls"]:
            for tc in msg["tool_calls"]:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                raw_args = fn.get("arguments", "{}")
                parsed_args: Any = raw_args
                if isinstance(raw_args, str):
                    try:
                        parsed_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        parsed_args = raw_args
                meta = {
                    "id": str(tc.get("id", "")),
                    "tool": str(fn.get("name") or ""),
                    "arguments": parsed_args,
                }
                if meta["id"] and meta["id"] not in call_meta_by_id:
                    call_meta_by_id[meta["id"]] = meta
                ordered_call_meta.append(meta)
            continue

        if role == "tool":
            raw_obs = msg.get("content", "")
            parsed_obs: Any = raw_obs
            if isinstance(raw_obs, str):
                try:
                    parsed_obs = json.loads(raw_obs)
                except json.JSONDecodeError:
                    parsed_obs = raw_obs
            tc_id = str(msg.get("tool_call_id", ""))
            matched = call_meta_by_id.get(tc_id) if tc_id else None
            if matched is None and tool_obs_idx < len(ordered_call_meta):
                matched = ordered_call_meta[tool_obs_idx]
            tool_obs_idx += 1
            verified_tool_results.append({
                "tool": str(msg.get("name") or (matched["tool"] if matched else "tool")),
                "arguments": matched["arguments"] if matched else {},
                "verified_output": parsed_obs,
            })
            continue

        if role in {"user", "assistant"} and isinstance(msg.get("content"), str) and msg["content"].strip():
            plain_turns.append({"role": role, "content": msg["content"].strip()})

    base_system = "\n\n".join(system_parts)
    is_english = "You are PetCare AI" in base_system and "Bạn là PetCare AI" not in base_system
    if is_english:
        base_system = re.sub(
            r"1\.\s*Always invoke allowlisted tools[^\n]*",
            "1. Use ONLY the verified Python/MySQL results in VERIFIED_PYTHON_TOOL_RESULTS_JSON; NEVER invent SKU codes, prices, stock counts, nutrient percentages, or breed stereotypes.",
            base_system,
        )
        synthesis_directive = (
            "\n\nFINAL SYNTHESIS MODE (TOOLS COMPLETED — DO NOT CALL TOOLS):\n"
            "- Python has already executed the authorized read-only tools; compose the final helpful English answer directly from VERIFIED_PYTHON_TOOL_RESULTS_JSON.\n"
            "- Quote exact item names, exact SKU codes in parentheses (e.g., FOOD-001), and exact per-item prices from the 'price' field; do NOT compute custom cart totals or price differences, and do NOT output JSON or function-call syntax."
        )
    else:
        base_system = re.sub(
            r"1\.\s*Luôn gọi các công cụ[^\n]*",
            "1. CHỈ sử dụng kết quả Python/MySQL đã xác thực trong VERIFIED_PYTHON_TOOL_RESULTS_JSON; TUYỆT ĐỐI KHÔNG tự bịa mã SKU, giá bán, tồn kho, tỷ lệ dinh dưỡng hay tính cách theo giống.",
            base_system,
        )
        synthesis_directive = (
            "\n\nCHẾ ĐỘ TỔNG HỢP CUỐI CÙNG (CÔNG CỤ ĐÃ CHẠY XONG — KHÔNG GỌI THÊM CÔNG CỤ):\n"
            "- Công cụ Python đã truy vấn dữ liệu MySQL thành công; hãy trả lời tư vấn tiếng Việt tự nhiên, rõ ràng, súc tích dựa HOÀN TOÀN vào VERIFIED_PYTHON_TOOL_RESULTS_JSON.\n"
            "- Khi nêu sản phẩm hoặc thú cưng, ghi đúng tên, mã SKU trong ngoặc (ví dụ FOOD-001) và đúng giá niêm yết của từng mục từ trường 'price' (ví dụ 100.000 VND, 210.000 VND); KHÔNG tự cộng tổng tiền nhiều món hay tính chênh lệch giá, và KHÔNG xuất JSON hay cú pháp gọi hàm."
        )

    last_user_idx = -1
    for idx in range(len(plain_turns) - 1, -1, -1):
        if plain_turns[idx]["role"] == "user":
            last_user_idx = idx
            break

    if last_user_idx >= 0:
        prior_turns = plain_turns[:last_user_idx]
        current_question = plain_turns[last_user_idx]["content"]
    else:
        prior_turns = plain_turns
        current_question = ""

    final_user_content = (
        "VERIFIED_PYTHON_TOOL_RESULTS_JSON:\n"
        + json.dumps(verified_tool_results, ensure_ascii=False, default=str)
        + "\n\nUSER_QUESTION:\n"
        + current_question
    )

    assembled: list[dict[str, Any]] = []
    full_system = (base_system + synthesis_directive).strip()
    if full_system:
        assembled.append({"role": "system", "content": full_system})
    assembled.extend(prior_turns)
    assembled.append({"role": "user", "content": final_user_content})
    return normalize_messages_for_provider(assembled, "gemini")


def resolve_chat_completions_params(
    model_name: str,
    reasoning_effort_raw: str | None,
    *,
    has_tools: bool,
    max_output_tokens: int,
    default_temperature: float,
    provider_family: str | None = None,
) -> dict[str, Any]:
    """Build Chat Completions token, reasoning_effort, and sampling fields per provider contract."""
    fam = provider_family or detect_provider_family("", "", model_name)
    effort = str(reasoning_effort_raw or "").strip().lower()

    if fam == "gemini":
        is_gemini_3_plus = bool(_GEMINI_3_PLUS_MODEL_RE.match(str(model_name or "").strip()))
        if effort:
            if is_gemini_3_plus and effort == "none":
                raise AIProviderError(
                    "Mô hình Gemini 3/3.5 (như gemini-3.5-flash-lite) không hỗ trợ AI_REASONING_EFFORT='none'; "
                    "hãy để trống hoặc dùng 'minimal'/'low'.",
                    error_category="invalid_configuration",
                )
            allowed_gemini = (
                ALLOWED_GEMINI_3_REASONING_EFFORTS
                if is_gemini_3_plus
                else ALLOWED_GEMINI_25_REASONING_EFFORTS
            )
            if effort not in allowed_gemini:
                raise AIProviderError(
                    f"AI_REASONING_EFFORT='{effort}' không được hỗ trợ cho Google Gemini "
                    f"(chỉ chấp nhận: {', '.join(sorted(allowed_gemini))}).",
                    error_category="invalid_configuration",
                )
        params: dict[str, Any] = {
            "temperature": default_temperature,
            "max_tokens": max_output_tokens,
        }
        if effort:
            params["reasoning_effort"] = effort
        return params

    if effort and effort not in ALLOWED_REASONING_EFFORTS:
        raise AIProviderError("AI_REASONING_EFFORT configuration is invalid.", error_category="invalid_configuration")

    reasoning_model = is_reasoning_series_model(model_name)
    if reasoning_model:
        if has_tools:
            if effort and effort != "none":
                raise AIProviderError(
                    "Function calling trên /v1/chat/completions cho mô hình suy luận (như gpt-6-luna) "
                    "bắt buộc AI_REASONING_EFFORT='none' (mức suy luận cao hơn yêu cầu Responses API /v1/responses).",
                    error_category="invalid_configuration",
                )
            effective_effort = "none"
        else:
            effective_effort = effort or "none"

        params = {
            "reasoning_effort": effective_effort,
            "max_completion_tokens": max_output_tokens,
        }
        if effective_effort == "none":
            params["temperature"] = default_temperature
        return params

    if effort:
        params = {
            "reasoning_effort": effort,
            "max_completion_tokens": max_output_tokens,
        }
        if effort == "none":
            params["temperature"] = default_temperature
        return params

    return {
        "temperature": default_temperature,
        "max_tokens": max_output_tokens,
    }


def extract_usage_metadata(usage_raw: Any, *, fallback_prompt_tokens: int = 0, fallback_completion_tokens: int = 0) -> dict[str, Any]:
    """Normalize OpenAI & Gemini token usage metadata without losing cached or thinking token counts."""
    u = usage_raw if isinstance(usage_raw, dict) else {}
    rep_prompt = int(u.get("prompt_tokens") or 0)
    rep_comp = int(u.get("completion_tokens") or 0)
    has_real = rep_prompt > 0 or rep_comp > 0
    p_tok = rep_prompt if has_real else max(0, int(fallback_prompt_tokens))
    c_tok = rep_comp if has_real else max(0, int(fallback_completion_tokens))
    t_tok = int(u.get("total_tokens") or 0) or (p_tok + c_tok)
    p_details = u.get("prompt_tokens_details") if isinstance(u.get("prompt_tokens_details"), dict) else {}
    c_details = u.get("completion_tokens_details") if isinstance(u.get("completion_tokens_details"), dict) else {}
    cached_tok = max(0, min(int(p_details.get("cached_tokens") or u.get("cached_content_token_count") or 0), p_tok))
    reas_tok = max(0, int(c_details.get("reasoning_tokens") or u.get("thoughts_token_count") or 0))
    return {
        "usage_source": "provider_reported" if has_real else "estimated",
        "prompt_tokens": p_tok,
        "cached_prompt_tokens": cached_tok,
        "completion_tokens": c_tok,
        "reasoning_tokens": reas_tok,
        "total_tokens": t_tok,
    }


class FreeTierRateLimiter:
    """Thread-safe sliding-window rate limiter for Google AI Studio Free Tier (~15 RPM / 250k TPM / 500 RPD)."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._minute_events: dict[str, deque[tuple[float, int]]] = {}
        self._day_events: dict[str, deque[float]] = {}
        self._last_request_ts: dict[str, float] = {}
        self._cooldown_until: dict[str, float] = {}

    def reset(self) -> None:
        with self._lock:
            self._minute_events.clear()
            self._day_events.clear()
            self._last_request_ts.clear()
            self._cooldown_until.clear()

    def snapshot(self, bucket: str = "gemini") -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            min_q = self._minute_events.get(bucket, deque())
            day_q = self._day_events.get(bucket, deque())
            active_min = [(ts, tok) for ts, tok in min_q if now - ts < 60.0]
            active_day = [ts for ts in day_q if now - ts < 86400.0]
            cooldown_rem = max(0.0, self._cooldown_until.get(bucket, 0.0) - now)
            return {
                "bucket": bucket,
                "requests_in_last_minute": len(active_min),
                "input_tokens_in_last_minute": sum(tok for _, tok in active_min),
                "requests_in_last_day": len(active_day),
                "cooldown_remaining_seconds": round(cooldown_rem, 3),
            }

    def record_upstream_429(self, bucket: str, retry_after_seconds: float | None = None) -> float:
        cooldown = min(max(float(retry_after_seconds or 5.0), 1.0), 60.0)
        now = self._clock()
        with self._lock:
            self._cooldown_until[bucket] = max(self._cooldown_until.get(bucket, 0.0), now + cooldown)
        return cooldown

    def _prune_locked(self, bucket: str, now: float) -> tuple[deque[tuple[float, int]], deque[float]]:
        min_q = self._minute_events.setdefault(bucket, deque())
        while min_q and now - min_q[0][0] >= 60.0:
            min_q.popleft()
        day_q = self._day_events.setdefault(bucket, deque())
        while day_q and now - day_q[0] >= 86400.0:
            day_q.popleft()
        return min_q, day_q

    def acquire(
        self,
        bucket: str,
        *,
        estimated_input_tokens: int,
        rpm_limit: int,
        tpm_limit: int,
        rpd_limit: int,
        min_interval_seconds: float = 0.0,
        max_wait_seconds: float = 2.5,
    ) -> float:
        est_tokens = max(1, int(estimated_input_tokens))
        total_slept = 0.0

        while True:
            wait_needed = 0.0
            limit_reason: str | None = None
            with self._lock:
                now = self._clock()
                min_q, day_q = self._prune_locked(bucket, now)

                cooldown_until = self._cooldown_until.get(bucket, 0.0)
                if now < cooldown_until:
                    wait_needed = cooldown_until - now
                    limit_reason = "upstream_429_cooldown"
                elif len(day_q) >= rpd_limit:
                    raise AIRateLimitError(
                        f"Đã chạm ngưỡng an toàn ngày của gói miễn phí ({rpd_limit} RPD); "
                        "chuyển sang chế độ Python nội bộ.",
                        retry_after_seconds=60.0,
                        source="local_rpd_guard",
                    )
                elif est_tokens > tpm_limit:
                    raise AIRateLimitError(
                        f"Ước tính token đầu vào ({est_tokens}) vượt ngưỡng an toàn phút ({tpm_limit} TPM).",
                        retry_after_seconds=60.0,
                        source="local_tpm_guard",
                    )
                else:
                    last_ts = self._last_request_ts.get(bucket)
                    if last_ts is not None and min_interval_seconds > 0 and (now - last_ts) < min_interval_seconds:
                        wait_needed = min_interval_seconds - (now - last_ts)
                        limit_reason = "min_interval_pacing"
                    elif len(min_q) >= rpm_limit:
                        wait_needed = max(0.05, 60.0 - (now - min_q[0][0]))
                        limit_reason = "local_rpm_guard"
                    elif sum(tok for _, tok in min_q) + est_tokens > tpm_limit:
                        wait_needed = max(0.05, 60.0 - (now - min_q[0][0]))
                        limit_reason = "local_tpm_guard"
                    else:
                        min_q.append((now, est_tokens))
                        day_q.append(now)
                        self._last_request_ts[bucket] = now
                        return round(total_slept, 4)

            if wait_needed <= 0 or (total_slept + wait_needed) > max(0.0, max_wait_seconds):
                raise AIRateLimitError(
                    f"Đã chạm ngưỡng điều tiết gói miễn phí ({limit_reason or 'rate_limit'}); "
                    "chuyển sang chế độ Python nội bộ an toàn.",
                    retry_after_seconds=round(wait_needed, 2),
                    source=limit_reason or "local_rate_guard",
                )

            self._sleeper(wait_needed)
            total_slept += wait_needed


GLOBAL_PROVIDER_RATE_LIMITER = FreeTierRateLimiter()


def _estimate_payload_input_tokens(body_bytes: bytes) -> int:
    return max(1, len(body_bytes) // 4)


def _parse_retry_after_seconds(headers: Any) -> float | None:
    if headers is None:
        return None
    raw = None
    try:
        raw = headers.get("Retry-After") or headers.get("retry-after")
    except AttributeError:
        raw = None
    if raw is None:
        return None
    try:
        val = float(str(raw).strip())
        if val > 0:
            return min(val, 120.0)
    except ValueError:
        pass
    return None


def _maybe_enforce_free_tier_rate_limit(
    provider_family: str,
    body_bytes: bytes,
    *,
    timeout_budget_seconds: float,
) -> None:
    cfg = current_app.config
    app_env = str(cfg.get("APP_ENV", "development")).strip().lower()
    enforce_in_test = bool(cfg.get("AI_ENFORCE_TEST_RATE_LIMIT", False))
    throttle_enabled = bool(
        cfg.get("AI_FREE_TIER_THROTTLE_ENABLED", provider_family == "gemini")
    )
    if not throttle_enabled:
        return
    if app_env == "test" and not enforce_in_test:
        return

    rpm = max(1, int(cfg.get("AI_RATE_LIMIT_RPM", Config.AI_RATE_LIMIT_RPM)))
    tpm = max(1000, int(cfg.get("AI_RATE_LIMIT_TPM", Config.AI_RATE_LIMIT_TPM)))
    rpd = max(1, int(cfg.get("AI_RATE_LIMIT_RPD", Config.AI_RATE_LIMIT_RPD)))
    min_interval_ms = max(0, int(cfg.get("AI_MIN_REQUEST_INTERVAL_MS", Config.AI_MIN_REQUEST_INTERVAL_MS)))
    max_wait = max(0.0, min(2.5, timeout_budget_seconds * 0.35))

    GLOBAL_PROVIDER_RATE_LIMITER.acquire(
        provider_family,
        estimated_input_tokens=_estimate_payload_input_tokens(body_bytes),
        rpm_limit=rpm,
        tpm_limit=tpm,
        rpd_limit=rpd,
        min_interval_seconds=min_interval_ms / 1000.0,
        max_wait_seconds=max_wait,
    )


def is_configured() -> bool:
    conn = resolve_provider_connection_settings()
    return bool(conn["base_url"] and conn["model_name"])


def validate_endpoint_url(
    base_url: str,
    *,
    app_env: str = "development",
    allow_http_endpoint: bool = False,
    allow_test_loopback: bool = False,
) -> str:
    """Validate an OpenAI-compatible or Gemini OpenAI base URL and enforce SSRF / TLS boundaries."""
    cleaned = str(base_url or "").strip().rstrip("/")
    try:
        parsed = urlparse(cleaned)
        _ = parsed.port
    except ValueError as exc:
        raise AIProviderError("Địa chỉ AI endpoint không hợp lệ.", error_category="invalid_endpoint_url") from exc
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise AIProviderError(
            "Địa chỉ AI endpoint cần dùng http hoặc https (không chứa khóa hoặc query trên URL).",
            error_category="invalid_endpoint_url",
        )

    host = parsed.hostname.strip().lower()
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_unspecified:
            raise AIProviderError(
                "Địa chỉ AI endpoint thuộc dải IP nội bộ/metadata bị chặn (SSRF guard).",
                error_category="ssrf_blocked",
            )
        if ip_obj.is_loopback:
            allowed_loopback = (app_env == "test" and allow_test_loopback) or (
                app_env != "production" and allow_http_endpoint
            )
            if not allowed_loopback and app_env == "production":
                raise AIProviderError(
                    "Production không cho phép AI endpoint trỏ tới loopback nội bộ.",
                    error_category="ssrf_blocked",
                )
        elif ip_obj.is_private and not allow_http_endpoint:
            raise AIProviderError(
                "Địa chỉ AI endpoint IP riêng tư bị chặn trừ khi bật ngoại lệ mạng nội bộ tin cậy.",
                error_category="ssrf_blocked",
            )
    elif host in {"metadata.google.internal", "metadata", "169.254.169.254"}:
        raise AIProviderError(
            "Địa chỉ AI endpoint thuộc dịch vụ metadata đám mây bị chặn (SSRF guard).",
            error_category="ssrf_blocked",
        )

    if (
        (app_env == "production" or host.endswith("generativelanguage.googleapis.com"))
        and parsed.scheme != "https"
        and not allow_http_endpoint
    ):
        raise AIProviderError(
            "Endpoint AI ngoài yêu cầu giao thức HTTPS an toàn.",
            error_category="insecure_transport_blocked",
        )
    if cleaned.endswith("/chat/completions"):
        return cleaned
    if cleaned.endswith(("/v1", "/v1beta/openai", "/v1/openai")):
        return f"{cleaned}/chat/completions"
    return f"{cleaned}/v1/chat/completions"


def _completion_url(base_url: str | None = None) -> str:
    effective_base = (
        base_url
        if base_url is not None
        else resolve_provider_connection_settings()["base_url"]
    )
    return validate_endpoint_url(
        effective_base,
        app_env=str(current_app.config.get("APP_ENV", "development")).strip().lower(),
        allow_http_endpoint=bool(current_app.config.get("AI_ALLOW_HTTP_ENDPOINT")),
        allow_test_loopback=bool(current_app.config.get("AI_TEST_ALLOW_LOOPBACK_PROVIDER")),
    )


def _build_verified_ssl_context() -> ssl.SSLContext:
    """Create an SSLContext with strict certificate + hostname verification enabled (`CERT_REQUIRED`)."""
    ctx = ssl.create_default_context()
    if not os.getenv("SSL_CERT_FILE") and not os.getenv("SSL_CERT_DIR"):
        default_paths = ssl.get_default_verify_paths()
        cafile_exists = bool(default_paths.cafile and os.path.isfile(default_paths.cafile))
        if not cafile_exists:
            try:
                import certifi  # type: ignore[import-not-found]

                ctx.load_verify_locations(cafile=certifi.where())
            except Exception:  # nosec B110
                pass
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def _build_secure_http_opener() -> Any:
    class NoRedirectHandler(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, new_url):
            return None

    return build_opener(NoRedirectHandler(), HTTPSHandler(context=_build_verified_ssl_context()))


def complete_with_metadata(
    messages: list[dict],
    image_bytes: bytes | None = None,
    *,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    """Call a configured model endpoint and return `{content, usage, finish_reason}`."""
    if current_app.config.get("AI_PILOT_KILL_SWITCH"):
        raise AIProviderError("Công tắc ngắt khẩn cấp AI_PILOT_KILL_SWITCH đang bật.", error_category="kill_switch")
    conn = resolve_provider_connection_settings()
    if not (conn["base_url"] and conn["model_name"]):
        raise AIProviderError("Chưa cấu hình mô hình AI.", error_category="unconfigured_provider")

    url = _completion_url(conn["base_url"])
    _enforce_test_provider_guard(url)
    if image_bytes is not None and len(image_bytes) > MAX_REQUEST_BYTES:
        raise AIProviderError("Ảnh gửi tới mô hình AI vượt giới hạn yêu cầu.", error_category="payload_too_large")

    provider_family = str(conn["provider_family"])
    request_messages = normalize_messages_for_provider(messages, provider_family)
    if image_bytes is not None:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        last = dict(request_messages[-1])
        last["content"] = [
            {"type": "text", "text": str(last.get("content", ""))},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
        ]
        request_messages = [*request_messages[:-1], last]

    default_max_out = 1024 if provider_family == "gemini" else 700
    bounded_max_out = max(128, min(int(max_output_tokens or default_max_out), 2048))

    try:
        model_name = str(conn["model_name"])
        request_body = {
            "model": model_name,
            "messages": request_messages,
            **resolve_chat_completions_params(
                model_name,
                current_app.config.get("AI_REASONING_EFFORT", ""),
                has_tools=False,
                max_output_tokens=bounded_max_out,
                default_temperature=0.2,
                provider_family=provider_family,
            ),
        }
        body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AIProviderError("Yêu cầu AI không đúng định dạng.", error_category="invalid_request_payload") from exc
    if len(body) > MAX_REQUEST_BYTES:
        raise AIProviderError("Yêu cầu AI vượt giới hạn dung lượng cho phép.", error_category="payload_too_large")

    timeout_val = float(current_app.config.get("AI_TIMEOUT_SECONDS", 15))
    _maybe_enforce_free_tier_rate_limit(
        provider_family,
        body,
        timeout_budget_seconds=timeout_val,
    )

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = str(conn["api_key"] or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=body, headers=headers, method="POST")

    max_response_bytes = 512_000
    t0 = time.perf_counter()
    try:
        opener = _build_secure_http_opener()
        with opener.open(request, timeout=float(timeout_val)) as response:  # nosec B310
            raw_payload = response.read(max_response_bytes + 1)
            if len(raw_payload) > max_response_bytes:
                raise AIProviderError("Mô hình AI trả về dữ liệu vượt giới hạn cho phép.", error_category="response_too_large")
    except HTTPError as exc:
        err_cat, upstream_code, detail = _extract_sanitized_http_error(exc)
        if exc.code == 429:
            retry_after = _parse_retry_after_seconds(getattr(exc, "headers", None))
            GLOBAL_PROVIDER_RATE_LIMITER.record_upstream_429(provider_family, retry_after)
            raise AIRateLimitError(
                "Đã chạm giới hạn tần suất gói miễn phí (HTTP 429); chuyển sang chế độ Python nội bộ an toàn.",
                retry_after_seconds=retry_after,
                source="upstream_429",
                upstream_error_code=upstream_code or "RESOURCE_EXHAUSTED",
                sanitized_detail=detail,
            ) from exc
        raise AIProviderError(
            "Không kết nối được mô hình AI đã cấu hình.",
            retryable=exc.code in RETRYABLE_HTTP_STATUSES,
            status_code=exc.code,
            error_category=err_cat,
            upstream_error_code=upstream_code,
            sanitized_detail=detail,
        ) from exc
    except URLError as exc:
        is_ssl = isinstance(exc.reason, ssl.SSLError)
        raise AIProviderError(
            "Không kết nối được mô hình AI đã cấu hình.",
            retryable=not is_ssl,
            error_category="tls_error" if is_ssl else "network_error",
            sanitized_detail=str(exc.reason) if exc.reason else None,
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise AIProviderError(
            "Không kết nối được mô hình AI đã cấu hình.",
            retryable=True,
            error_category="timeout",
            sanitized_detail="Request timed out",
        ) from exc
    except OSError as exc:
        raise AIProviderError(
            "Không kết nối được mô hình AI đã cấu hình.",
            retryable=True,
            error_category="network_error",
            sanitized_detail=type(exc).__name__,
        ) from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AIProviderError("Mô hình AI trả về JSON không hợp lệ.", error_category="malformed_response_json") from exc

    try:
        choice0 = payload["choices"][0]
        content = choice0["message"]["content"]
        finish_reason = choice0.get("finish_reason")
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError("Mô hình AI trả về dữ liệu không đúng định dạng.", error_category="malformed_response_schema") from exc
    if isinstance(content, list):
        content = "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        err_cat = "response_truncated_length" if finish_reason == "length" else "empty_model_output"
        raise AIProviderError(
            "Mô hình AI chưa trả lời nội dung.",
            error_category=err_cat,
            sanitized_detail=f"finish_reason={finish_reason}" if finish_reason else None,
        )

    cleaned_content = content.strip()[:4000]
    usage_norm = extract_usage_metadata(
        payload.get("usage"),
        fallback_prompt_tokens=_estimate_payload_input_tokens(body),
        fallback_completion_tokens=max(8, len(cleaned_content) // 4),
    )
    usage_norm["provider_latency_ms"] = elapsed_ms
    return {
        "content": cleaned_content,
        "finish_reason": finish_reason,
        "usage": usage_norm,
    }


def complete(messages: list[dict], image_bytes: bytes | None = None) -> str:
    """Call a configured OpenAI-compatible or Google Gemini model endpoint."""
    return str(complete_with_metadata(messages, image_bytes=image_bytes)["content"])


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
    raise AIProviderError("Không kết nối được mô hình ảnh đã cấu hình.", error_category="vision_unavailable")


def complete_chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    *,
    timeout_seconds: float | None = None,
    max_retries: int = 1,
    max_output_tokens: int | None = None,
    tool_choice: str = "auto",
) -> dict:
    """Call an approved OpenAI-compatible or Google Gemini chat completions endpoint with function tools."""
    if current_app.config.get("AI_PILOT_KILL_SWITCH"):
        raise AIProviderError("Công tắc ngắt khẩn cấp AI_PILOT_KILL_SWITCH đang bật.", error_category="kill_switch")
    if not (
        current_app.config.get("AI_PROVIDER_APPROVED")
        and current_app.config.get("AI_TOOL_CALLING_ENABLED")
    ):
        raise AIProviderError(
            "Chế độ gọi công cụ LLM ngoài chưa được phê duyệt và kích hoạt.",
            error_category="unapproved_provider",
        )
    conn = resolve_provider_connection_settings()
    if not (conn["base_url"] and conn["model_name"]):
        raise AIProviderError("Chưa cấu hình mô hình AI.", error_category="unconfigured_provider")

    url = _completion_url(conn["base_url"])
    _enforce_test_provider_guard(url)

    provider_family = str(conn["provider_family"])
    default_out = 1200 if provider_family == "gemini" else 700
    configured_max_out = int(
        max_output_tokens
        if max_output_tokens is not None
        else current_app.config.get("AI_MAX_OUTPUT_TOKENS", default_out)
    )
    if provider_family == "gemini" and max_output_tokens is None:
        # Gemini 3/3.5 thinking shares max_tokens with visible output/tool_calls; prevent 700-token truncation
        configured_max_out = max(configured_max_out, 1200)
    bounded_max_out = max(128, min(configured_max_out, 2048))

    use_gemini_tool_free_synthesis = provider_family == "gemini" and tool_choice == "none"
    if use_gemini_tool_free_synthesis:
        request_messages = build_gemini_final_synthesis_messages(messages)
        effective_tools: list[dict] = []
    else:
        request_messages = normalize_messages_for_provider(messages, provider_family)
        effective_tools = tools

    try:
        model_name = str(conn["model_name"])
        request_body: dict = {
            "model": model_name,
            "messages": request_messages,
            **resolve_chat_completions_params(
                model_name,
                current_app.config.get("AI_REASONING_EFFORT", ""),
                has_tools=bool(effective_tools),
                max_output_tokens=bounded_max_out,
                default_temperature=0.1,
                provider_family=provider_family,
            ),
        }
        if effective_tools:
            request_body["tools"] = effective_tools
            request_body["tool_choice"] = tool_choice if tool_choice in {"auto", "none", "required"} else "auto"
        body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AIProviderError(
            "Yêu cầu AI tool-calling không đúng định dạng.",
            error_category="invalid_request_payload",
        ) from exc

    if len(body) > 256 * 1024:
        raise AIProviderError(
            "Yêu cầu AI tool-calling vượt giới hạn 256 KB.",
            error_category="payload_too_large",
        )

    configured_timeout = float(
        timeout_seconds
        if timeout_seconds is not None
        else current_app.config.get("AI_TIMEOUT_SECONDS", 15)
    )
    max_http_timeout = max(
        1.0,
        min(float(current_app.config.get("AI_MAX_HTTP_TIMEOUT_SECONDS") or Config.AI_MAX_HTTP_TIMEOUT_SECONDS), 60.0),
    )
    bounded_timeout = max(0.5, min(configured_timeout, max_http_timeout))

    _maybe_enforce_free_tier_rate_limit(
        provider_family,
        body,
        timeout_budget_seconds=bounded_timeout,
    )

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = str(conn["api_key"] or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    bounded_retries = min(max(int(max_retries), 0), 1)
    max_response_bytes = 512_000

    for attempt in range(bounded_retries + 1):
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            opener = _build_secure_http_opener()
            with opener.open(request, timeout=bounded_timeout) as response:  # nosec B310
                raw_payload = response.read(max_response_bytes + 1)
                if len(raw_payload) > max_response_bytes:
                    raise AIProviderError(
                        "Mô hình AI trả về dữ liệu vượt giới hạn cho phép.",
                        error_category="response_too_large",
                    )
            break
        except HTTPError as exc:
            err_cat, upstream_code, detail = _extract_sanitized_http_error(exc)
            if exc.code == 429:
                retry_after = _parse_retry_after_seconds(getattr(exc, "headers", None))
                GLOBAL_PROVIDER_RATE_LIMITER.record_upstream_429(provider_family, retry_after)
                raise AIRateLimitError(
                    "Đã chạm giới hạn tần suất gói miễn phí (HTTP 429); chuyển sang chế độ Python nội bộ an toàn.",
                    retry_after_seconds=retry_after,
                    source="upstream_429",
                    upstream_error_code=upstream_code or "RESOURCE_EXHAUSTED",
                    sanitized_detail=detail,
                ) from exc
            err = AIProviderError(
                "Không kết nối được mô hình AI đã cấu hình.",
                retryable=exc.code in RETRYABLE_HTTP_STATUSES,
                status_code=exc.code,
                error_category=err_cat,
                upstream_error_code=upstream_code,
                sanitized_detail=detail,
            )
            if not err.retryable or attempt >= bounded_retries:
                raise err from exc
            time.sleep(0.1 * (attempt + 1))
        except URLError as exc:
            is_ssl = isinstance(exc.reason, ssl.SSLError)
            err = AIProviderError(
                "Không kết nối được mô hình AI đã cấu hình.",
                retryable=not is_ssl,
                error_category="tls_error" if is_ssl else "network_error",
                sanitized_detail=str(exc.reason) if exc.reason else None,
            )
            if not err.retryable or attempt >= bounded_retries:
                raise err from exc
            time.sleep(0.1 * (attempt + 1))
        except (TimeoutError, socket.timeout) as exc:
            err = AIProviderError(
                "Không kết nối được mô hình AI đã cấu hình.",
                retryable=True,
                error_category="timeout",
                sanitized_detail="Request timed out",
            )
            if attempt >= bounded_retries:
                raise err from exc
            time.sleep(0.1 * (attempt + 1))
        except OSError as exc:
            err = AIProviderError(
                "Không kết nối được mô hình AI đã cấu hình.",
                retryable=True,
                error_category="network_error",
                sanitized_detail=type(exc).__name__,
            )
            if attempt >= bounded_retries:
                raise err from exc
            time.sleep(0.1 * (attempt + 1))

    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AIProviderError("Mô hình AI trả về JSON không hợp lệ.", error_category="malformed_response_json") from exc
    if not isinstance(payload, dict):
        raise AIProviderError(
            "Mô hình AI trả về dữ liệu không đúng định dạng.",
            error_category="malformed_response_schema",
        )
    return payload


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
        raise AIProviderError(
            "AI provider requests are disabled in tests except to an explicitly enabled loopback mock.",
            error_category="test_egress_blocked",
        )
