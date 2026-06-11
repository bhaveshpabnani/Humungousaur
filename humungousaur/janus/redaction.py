from __future__ import annotations

from typing import Any

from humungousaur.planning.model_clients import redact_secrets


BLOCKED_KEYS = {
    "raw",
    "raw_text",
    "content",
    "body",
    "document_body",
    "email_body",
    "chat_body",
    "message_body",
    "transcript",
    "screenshot",
    "clipboard",
    "password",
    "passcode",
    "token",
    "secret",
    "api_key",
    "authorization",
    "cookie",
}


def safe_compact_value(value: Any, *, key: str = "", depth: int = 0, string_limit: int = 500) -> Any:
    """Return a compact, recursively redacted value for Reflex prompts and candidates."""

    if _blocked_key(key):
        return "[redacted]"
    if depth > 4:
        return "[omitted]"
    if isinstance(value, str):
        return redact_secrets(" ".join(value.split()))[: max(1, int(string_limit))]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [safe_compact_value(item, depth=depth + 1, string_limit=min(string_limit, 240)) for item in value[:20]]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for index, (item_key, item_value) in enumerate(value.items()):
            if index >= 40:
                break
            cleaned_key = _clean_key(item_key)
            if not cleaned_key:
                continue
            if _blocked_key(cleaned_key):
                cleaned[cleaned_key] = "[redacted]"
                continue
            cleaned[cleaned_key] = safe_compact_value(
                item_value,
                key=cleaned_key,
                depth=depth + 1,
                string_limit=min(string_limit, 500),
            )
        return cleaned
    return redact_secrets(str(value))[: max(1, min(int(string_limit), 500))]


def safe_compact_mapping(value: Any, *, limit: int = 40) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact = safe_compact_value(value, depth=0)
    if not isinstance(compact, dict):
        return {}
    return dict(list(compact.items())[: max(1, int(limit))])


def _clean_key(value: object) -> str:
    return " ".join(str(value or "").split())[:120]


def _blocked_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    if not normalized:
        return False
    return normalized in BLOCKED_KEYS or any(part in normalized for part in ("password", "token", "secret", "api_key", "authorization"))
