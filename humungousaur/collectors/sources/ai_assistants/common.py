from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any


AI_ASSISTANTS_SOURCE_ID = "ai_assistants"
AI_ASSISTANT_PRIVACY_TIER = "sensitive_metadata"

AI_ASSISTANT_SOURCE_EVENTS = (
    "chat_opened",
    "prompt_submitted_metadata",
    "response_received_metadata",
    "file_context_attached_redacted",
    "code_suggestion_accepted",
    "code_suggestion_rejected",
    "model_error",
    "tool_error",
)


@dataclass(frozen=True, slots=True)
class AiAssistantAppCollector:
    assistant: str
    display_name: str
    provider: str
    surfaces: tuple[str, ...]
    description: str
    source_channel: str = "browser_extension_or_app_plugin"
    implementation_level: str = "bridge_ingress"
    supported_events: tuple[str, ...] = AI_ASSISTANT_SOURCE_EVENTS

    def status_record(self) -> dict[str, Any]:
        return {
            "assistant": self.assistant,
            "display_name": self.display_name,
            "provider": self.provider,
            "surfaces": list(self.surfaces),
            "description": self.description,
            "source_channel": self.source_channel,
            "implementation_level": self.implementation_level,
            "supported_events": list(self.supported_events),
            "connector_boundary": "local app/browser/IDE source; no provider token access",
        }


def clean_token(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").replace(".", "_").split())


def hash_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def length_bucket(value: Any) -> str:
    text = str(value or "")
    length = len(text)
    if length <= 0:
        return ""
    if length <= 128:
        return "1-128"
    if length <= 512:
        return "129-512"
    if length <= 2_000:
        return "513-2000"
    return "2001+"


def numeric_bucket(value: Any, *, step: int, max_value: int) -> str:
    try:
        number = max(0, int(float(value)))
    except (TypeError, ValueError):
        return ""
    if number >= max_value:
        return f"{max_value}+"
    lower = (number // step) * step
    upper = lower + step - 1
    return f"{lower}-{upper}"


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
