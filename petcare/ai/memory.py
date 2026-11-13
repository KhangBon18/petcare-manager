"""Session-scoped, tenant-isolated conversational memory with TTL and PII redaction."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import re
import secrets
from threading import Lock
import time

from flask import current_app, has_app_context

from petcare.ai.contracts import AssistantScope, PreferenceSlots


_CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)\d[\d\s.-]{7,12}\d(?!\d)")
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_SECRET_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{12,}|api[_-]?key\s*[:=]\s*\S+|password\s*[:=]\s*\S+|bearer\s+[A-Za-z0-9._-]+)",
    re.IGNORECASE,
)

DEFAULT_TTL_SECONDS = 1800
DEFAULT_MAX_SESSIONS = 512
MAX_TURN_SUMMARIES = 8


def sanitize_conversation_id(raw_id: object) -> str:
    """Validate client conversation ID or mint a cryptographically random token."""
    if isinstance(raw_id, str):
        candidate = raw_id.strip()
        if _CONVERSATION_ID_RE.fullmatch(candidate):
            return candidate
    return f"conv_{secrets.token_urlsafe(12)}"


def redact_sensitive_text(text: str, max_chars: int = 240) -> str:
    """Strip emails, phone numbers, card numbers, and bearer/API secrets before retention."""
    cleaned = _SECRET_RE.sub("[REDACTED_SECRET]", text)
    cleaned = _EMAIL_RE.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _CARD_RE.sub("[REDACTED_CARD]", cleaned)
    cleaned = _PHONE_RE.sub("[REDACTED_PHONE]", cleaned)
    return cleaned[: max(1, int(max_chars))]


@dataclass(slots=True)
class SessionState:
    """Mutable state isolated to a single (tenant_id, user_id, scope, conversation_id)."""

    tenant_id: int
    user_id: int
    scope: AssistantScope
    conversation_id: str
    slots: PreferenceSlots = field(default_factory=PreferenceSlots)
    last_recommended_product_ids: list[int] = field(default_factory=list)
    last_recommended_pet_ids: list[int] = field(default_factory=list)
    recent_turns: list[dict[str, str]] = field(default_factory=list)
    turn_count: int = 0
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)

    def record_turn(self, role: str, summary_text: str) -> None:
        if role not in {"user", "assistant"}:
            return
        redacted = redact_sensitive_text(summary_text.strip())
        if not redacted:
            return
        self.recent_turns.append({"role": role, "summary": redacted})
        if len(self.recent_turns) > MAX_TURN_SUMMARIES:
            del self.recent_turns[:-MAX_TURN_SUMMARIES]
        if role == "user":
            self.turn_count += 1
        self.updated_at = time.monotonic()


class ConversationMemoryStore:
    """Bounded in-memory session store keyed strictly by tenant, actor, scope, and conversation."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: OrderedDict[tuple[int, int, str, str], SessionState] = OrderedDict()

    @staticmethod
    def _limits() -> tuple[int, int]:
        if has_app_context():
            ttl = int(current_app.config.get("ASSISTANT_CONVERSATION_TTL_SECONDS", DEFAULT_TTL_SECONDS))
            max_sessions = int(current_app.config.get("ASSISTANT_MAX_SESSIONS", DEFAULT_MAX_SESSIONS))
            return max(60, ttl), max(32, max_sessions)
        return DEFAULT_TTL_SECONDS, DEFAULT_MAX_SESSIONS

    def _prune_unlocked(self, now: float, ttl_seconds: int, max_sessions: int) -> None:
        expired_keys = [
            key
            for key, state in self._sessions.items()
            if now - state.updated_at > ttl_seconds
        ]
        for key in expired_keys:
            self._sessions.pop(key, None)
        while len(self._sessions) > max_sessions:
            self._sessions.popitem(last=False)

    def get_or_create(
        self,
        *,
        tenant_id: int,
        user_id: int,
        scope: AssistantScope,
        conversation_id: str,
    ) -> SessionState:
        ttl_seconds, max_sessions = self._limits()
        now = time.monotonic()
        key = (int(tenant_id), int(user_id), scope.value, conversation_id)
        with self._lock:
            self._prune_unlocked(now, ttl_seconds, max_sessions)
            existing = self._sessions.get(key)
            if existing is not None:
                existing.updated_at = now
                self._sessions.move_to_end(key)
                return existing
            created = SessionState(
                tenant_id=int(tenant_id),
                user_id=int(user_id),
                scope=scope,
                conversation_id=conversation_id,
                created_at=now,
                updated_at=now,
            )
            self._sessions[key] = created
            self._prune_unlocked(now, ttl_seconds, max_sessions)
            return created

    def peek(
        self,
        *,
        tenant_id: int,
        user_id: int,
        scope: AssistantScope,
        conversation_id: str,
    ) -> SessionState | None:
        ttl_seconds, max_sessions = self._limits()
        now = time.monotonic()
        key = (int(tenant_id), int(user_id), scope.value, conversation_id)
        with self._lock:
            self._prune_unlocked(now, ttl_seconds, max_sessions)
            state = self._sessions.get(key)
            return state

    def reset(
        self,
        *,
        tenant_id: int,
        user_id: int,
        scope: AssistantScope,
        conversation_id: str | None = None,
    ) -> int:
        """Clear one conversation or all conversations belonging to (tenant_id, user_id, scope)."""
        removed = 0
        with self._lock:
            if conversation_id:
                key = (int(tenant_id), int(user_id), scope.value, conversation_id)
                if self._sessions.pop(key, None) is not None:
                    removed = 1
            else:
                keys = [
                    key
                    for key in self._sessions
                    if key[0] == int(tenant_id)
                    and key[1] == int(user_id)
                    and key[2] == scope.value
                ]
                for key in keys:
                    self._sessions.pop(key, None)
                    removed += 1
        return removed

    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()


MEMORY_STORE = ConversationMemoryStore()
