from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.definitions import DEFINITIONS_BY_NAME
from humungousaur.collectors.envelope import CollectorEventEnvelope
from humungousaur.collectors.event_log import CollectorEventLog

from .common import (
    AI_ASSISTANT_PRIVACY_TIER,
    AI_ASSISTANTS_SOURCE_ID,
    clean_token,
    hash_value,
    length_bucket,
    numeric_bucket,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class AiAssistantEventMapping:
    source_event: str
    collector: str
    stimulus_type: str
    text: str
    privacy_tier: str = AI_ASSISTANT_PRIVACY_TIER

    def to_record(self) -> dict[str, Any]:
        return {
            "source_event": self.source_event,
            "collector": self.collector,
            "stimulus_type": self.stimulus_type,
            "text": self.text,
            "privacy_tier": self.privacy_tier,
        }


_ASSISTANT_ALIASES = {
    "chatgpt": "chatgpt",
    "openai": "chatgpt",
    "openai_chatgpt": "chatgpt",
    "claude": "claude",
    "anthropic": "claude",
    "gemini": "gemini",
    "google_gemini": "gemini",
    "bard": "gemini",
    "copilot": "copilot",
    "github_copilot": "copilot",
    "microsoft_copilot": "copilot",
    "cursor": "cursor",
    "cody": "cody",
    "sourcegraph_cody": "cody",
    "ollama": "local_llm",
    "lm_studio": "local_llm",
    "llama_cpp": "local_llm",
    "local_llm": "local_llm",
    "local_llm_tools": "local_llm",
    "openai_compatible_local": "local_llm",
}

_DISPLAY_NAMES = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "gemini": "Gemini",
    "copilot": "Copilot",
    "cursor": "Cursor",
    "cody": "Cody",
    "local_llm": "Local LLM tools",
}

_EVENT_ALIASES = {
    "chat_opened": "chat_opened",
    "conversation_opened": "chat_opened",
    "thread_opened": "chat_opened",
    "prompt_submitted": "prompt_submitted_metadata",
    "prompt_submitted_metadata": "prompt_submitted_metadata",
    "message_submitted": "prompt_submitted_metadata",
    "response_received": "response_received_metadata",
    "response_received_metadata": "response_received_metadata",
    "completion_received": "response_received_metadata",
    "file_context_attached": "file_context_attached_redacted",
    "file_context_attached_redacted": "file_context_attached_redacted",
    "context_file_attached": "file_context_attached_redacted",
    "code_suggestion_accepted": "code_suggestion_accepted",
    "suggestion_accepted": "code_suggestion_accepted",
    "ai_suggestion_accepted": "code_suggestion_accepted",
    "code_suggestion_rejected": "code_suggestion_rejected",
    "suggestion_rejected": "code_suggestion_rejected",
    "model_error": "model_error",
    "model_request_failed": "model_error",
    "completion_failed": "model_error",
    "tool_error": "tool_error",
    "tool_call_failed": "tool_error",
    "tool_failed": "tool_error",
    "tool_call_started": "tool_call_started",
    "conversation_exported": "conversation_exported",
}

_MAPPINGS: tuple[AiAssistantEventMapping, ...] = (
    AiAssistantEventMapping("chat_opened", "ai_assistant_activity", "ai_chat_opened", "AI assistant chat was opened"),
    AiAssistantEventMapping("prompt_submitted_metadata", "ai_assistant_activity", "ai_prompt_submitted", "AI assistant prompt metadata was submitted"),
    AiAssistantEventMapping("response_received_metadata", "ai_assistant_activity", "ai_response_received", "AI assistant response metadata was received"),
    AiAssistantEventMapping("file_context_attached_redacted", "ai_assistant_activity", "ai_file_context_attached", "AI assistant file context was attached with paths and contents redacted"),
    AiAssistantEventMapping("code_suggestion_accepted", "ai_assistant_activity", "ai_code_suggestion_accepted", "AI assistant code suggestion was accepted"),
    AiAssistantEventMapping("code_suggestion_rejected", "ai_assistant_activity", "ai_code_suggestion_rejected", "AI assistant code suggestion was rejected"),
    AiAssistantEventMapping("model_error", "ai_assistant_activity", "ai_model_error", "AI assistant model error was observed"),
    AiAssistantEventMapping("tool_error", "ai_assistant_activity", "ai_tool_error", "AI assistant tool error was observed"),
    AiAssistantEventMapping("tool_call_started", "ai_assistant_activity", "ai_tool_call_started", "AI assistant tool call started"),
    AiAssistantEventMapping("conversation_exported", "ai_assistant_activity", "ai_conversation_exported", "AI assistant conversation export metadata was observed"),
)

_MAPPING_BY_SOURCE_EVENT = {mapping.source_event: mapping for mapping in _MAPPINGS}


def append_ai_assistant_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        source_event = _source_event(payload)
        mapping = _MAPPING_BY_SOURCE_EVENT[source_event]
        _validate_mapping(mapping)
        metadata = _metadata_from_payload(payload, source_event)
        signature = _signature(payload, mapping, metadata)
        envelope = CollectorEventEnvelope(
            event_id=f"ai-assistant-{signature[:24]}",
            collector=mapping.collector,
            source=AI_ASSISTANTS_SOURCE_ID,
            platform=platform.system(),
            stimulus_type=mapping.stimulus_type,
            privacy_tier=mapping.privacy_tier,
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or utc_now()),
            received_at=utc_now(),
            signature=f"{AI_ASSISTANTS_SOURCE_ID}:{source_event}:{signature}",
            text=mapping.text,
            metadata=metadata,
            payload=_payload_from_ai_event(payload),
            redaction={
                "privacy_tier": mapping.privacy_tier,
                "raw_content_included": False,
                "attention_safe": True,
                "paths_redacted": True,
                "urls_redacted": True,
                "titles_redacted": True,
                "prompt_redacted": True,
                "response_redacted": True,
                "file_context_redacted": True,
                "tool_payload_redacted": True,
                "payload_compacted_before_llm": True,
            },
        )
        from humungousaur.collectors.source_gate import append_source_envelope

        gate = append_source_envelope(config, envelope)
        if not gate.accepted:
            return {
                "accepted": False,
                "source": AI_ASSISTANTS_SOURCE_ID,
                "assistant": metadata.get("assistant", ""),
                "source_event": source_event,
                "collector": mapping.collector,
                "stimulus_type": mapping.stimulus_type,
                "reason": gate.reason,
            }
        appended = gate.appended or {}
        return {
            "accepted": True,
            "source": AI_ASSISTANTS_SOURCE_ID,
            "assistant": metadata.get("assistant", ""),
            "source_event": source_event,
            "collector": mapping.collector,
            "stimulus_type": mapping.stimulus_type,
            **appended,
        }
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_ai_assistant_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "running").strip()
    if status not in {"starting", "running", "degraded", "permission_denied", "stopped", "failed"}:
        raise ValueError(f"unsupported AI assistant source health status: {status or '<empty>'}")
    assistant = _normalize_assistant(payload.get("assistant") or payload.get("app") or payload.get("provider"))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    CollectorEventLog(config.normalized().collector_events_db_path).record_helper_health(
        helper_id=f"ai-assistant-source-{assistant or 'unknown'}",
        collector="ai_assistant_activity",
        platform=platform.system(),
        status=status,
        version="0.1",
        permission_state=str(payload.get("permission_state") or status),
        message=str(payload.get("message") or ""),
        metadata={
            "source": AI_ASSISTANTS_SOURCE_ID,
            "assistant": assistant,
            "display_name": _display_assistant(assistant),
            "source_channel": str(payload.get("source_channel") or "browser_extension_or_app_plugin"),
            **_safe_metadata_values(metadata),
        },
    )
    return {"accepted": True, "source": AI_ASSISTANTS_SOURCE_ID, "assistant": assistant, "status": status, "collector_count": 1}


def ai_assistant_source_status(config: AgentConfig) -> dict[str, Any]:
    from .registry import ai_assistant_collector_status_records

    normalized = config.normalized()
    log = CollectorEventLog(normalized.collector_events_db_path)
    health = [
        item
        for item in log.helper_health(limit=500)
        if str((item.get("metadata") or {}).get("source") or "") == AI_ASSISTANTS_SOURCE_ID
    ]
    pending_event_count = sum(1 for event in log.query(limit=1000) if event.get("source") == AI_ASSISTANTS_SOURCE_ID)
    return {
        "source": AI_ASSISTANTS_SOURCE_ID,
        "display_name": "AI assistants",
        "source_type": "browser_extension_app_plugin_or_local_tool_bridge",
        "auth_method": "local_extension_or_plugin_permission",
        "status": _health_status(health),
        "pending_event_count": pending_event_count,
        "dead_letter_count": _line_count(_dead_letters_path(normalized)),
        "dead_letters_path": str(_dead_letters_path(normalized)),
        "assistant_collectors": ai_assistant_collector_status_records(),
        "supported_assistants": ["chatgpt", "claude", "gemini", "copilot", "cursor", "cody", "local_llm"],
        "collector_mappings": [mapping.to_record() for mapping in _MAPPINGS],
        "mapping_count": len(_MAPPINGS),
        "helper_health": health,
        "health_count": len(health),
        "privacy_contract": {
            "default_privacy_tier": AI_ASSISTANT_PRIVACY_TIER,
            "raw_content_included": False,
            "prompts_redacted": True,
            "responses_redacted": True,
            "file_context_redacted": True,
            "code_context_redacted": True,
            "tool_payloads_redacted": True,
        },
    }


def _source_event(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit in _MAPPING_BY_SOURCE_EVENT:
        return explicit
    event_type = clean_token(payload.get("event_type") or payload.get("action") or explicit)
    source_event = _EVENT_ALIASES.get(event_type)
    if not source_event:
        raise ValueError(f"unsupported AI assistant event mapping: {event_type or '<event_type>'}")
    return source_event


def _normalize_assistant(value: Any) -> str:
    token = clean_token(value)
    return _ASSISTANT_ALIASES.get(token, token)


def _display_assistant(assistant: str) -> str:
    return _DISPLAY_NAMES.get(assistant, assistant.replace("_", " ").title() if assistant else "")


def _metadata_from_payload(payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    assistant = _normalize_assistant(payload.get("assistant") or payload.get("app") or payload.get("provider"))
    raw_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    model_value = payload.get("model") or raw_metadata.get("model") or raw_metadata.get("model_name")
    tool_value = payload.get("tool") or raw_metadata.get("tool") or raw_metadata.get("tool_name")
    metadata: dict[str, Any] = {
        "source": AI_ASSISTANTS_SOURCE_ID,
        "source_event": source_event,
        "assistant": assistant,
        "display_name": _display_assistant(assistant),
        "source_channel": str(payload.get("source_channel") or raw_metadata.get("source_channel") or "browser_extension_or_app_plugin")[:80],
        "surface": clean_token(payload.get("surface") or raw_metadata.get("surface") or ""),
        "content_redacted": True,
        "prompt_redacted": True,
        "response_redacted": True,
        "file_context_redacted": True,
        "tool_payload_redacted": True,
    }
    for key in ("conversation_id", "thread_id", "request_id", "response_id", "workspace_id", "project_id", "file_context_id"):
        value = payload.get(key) or raw_metadata.get(key)
        hashed = hash_value(value)
        if hashed:
            metadata[f"{key}_hash"] = hashed
    if model_value:
        metadata["model_name_hash"] = hash_value(model_value)
        metadata["model_name_redacted"] = True
    if tool_value:
        metadata["tool_name_hash"] = hash_value(tool_value)
        metadata["tool_name_redacted"] = True
    for key in ("provider", "runtime", "language", "error_type", "http_status", "finish_reason"):
        value = raw_metadata.get(key, payload.get(key))
        if value not in (None, ""):
            metadata[key] = str(value)[:80]
    for key in ("file_context_count", "attached_file_count", "suggestion_line_count", "token_count", "input_token_count", "output_token_count"):
        value = raw_metadata.get(key, payload.get(key))
        bucket = numeric_bucket(value, step=10, max_value=10_000)
        if bucket:
            metadata[f"{key}_bucket"] = bucket
    for key in ("prompt", "prompt_text", "response", "response_text", "code_context", "file_context", "tool_payload"):
        value = payload.get(key) or raw_metadata.get(key)
        bucket = length_bucket(value)
        if bucket:
            metadata[f"{key}_length_bucket"] = bucket
    return {key: value for key, value in metadata.items() if value not in ("", None)}


def _payload_from_ai_event(payload: dict[str, Any]) -> dict[str, Any]:
    raw_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return {
        "raw_prompt_omitted": bool(payload.get("prompt") or payload.get("prompt_text") or raw_metadata.get("prompt")),
        "raw_response_omitted": bool(payload.get("response") or payload.get("response_text") or raw_metadata.get("response")),
        "raw_file_context_omitted": bool(payload.get("file_context") or raw_metadata.get("file_context") or raw_metadata.get("file_path")),
        "raw_code_context_omitted": bool(payload.get("code_context") or raw_metadata.get("code_context")),
        "raw_tool_payload_omitted": bool(payload.get("tool_payload") or raw_metadata.get("tool_payload")),
    }


def _signature(payload: dict[str, Any], mapping: AiAssistantEventMapping, metadata: dict[str, Any]) -> str:
    basis = {
        "assistant": metadata.get("assistant"),
        "source_event": mapping.source_event,
        "conversation_id_hash": metadata.get("conversation_id_hash"),
        "request_id_hash": metadata.get("request_id_hash"),
        "response_id_hash": metadata.get("response_id_hash"),
        "occurred_at": payload.get("occurred_at") or payload.get("timestamp"),
        "surface": metadata.get("surface"),
        "source_channel": metadata.get("source_channel"),
    }
    return hash_value(json.dumps(basis, ensure_ascii=False, sort_keys=True)).removeprefix("sha256:")


def _validate_mapping(mapping: AiAssistantEventMapping) -> None:
    definition = DEFINITIONS_BY_NAME.get(mapping.collector)
    if definition is None:
        raise ValueError(f"AI assistant mapping references unknown collector: {mapping.collector}")
    if mapping.stimulus_type not in definition.stimulus_types:
        raise ValueError(f"AI assistant mapping references unsupported stimulus: {mapping.collector}/{mapping.stimulus_type}")


def _safe_metadata_values(metadata: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        cleaned_key = clean_token(key)
        if cleaned_key in {"prompt", "prompt_text", "response", "response_text", "message", "body", "content", "code", "tool_payload"} or any(
            sensitive in cleaned_key for sensitive in ("path", "url", "title", "filename", "file_name", "subject")
        ):
            safe[f"{cleaned_key}_redacted"] = True
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[cleaned_key] = str(value)[:120] if isinstance(value, str) else value
    return safe


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    normalized = config.normalized()
    path = _dead_letters_path(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "received_at": utc_now(),
        "reason": reason,
        "source": AI_ASSISTANTS_SOURCE_ID,
        "payload_keys": sorted(str(key) for key in payload.keys()),
        "assistant": str(payload.get("assistant") or payload.get("app") or ""),
        "source_event": str(payload.get("source_event") or payload.get("event_type") or payload.get("action") or ""),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / AI_ASSISTANTS_SOURCE_ID / "dead_letters.jsonl"


def _line_count(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8"))
    except OSError:
        return 0


def _health_status(health: list[dict[str, Any]]) -> str:
    if not health:
        return "not_connected"
    statuses = {str(item.get("status") or "") for item in health}
    if "running" in statuses and statuses - {"running"}:
        return "degraded"
    if "running" in statuses:
        return "running"
    if "degraded" in statuses:
        return "degraded"
    if "permission_denied" in statuses:
        return "permission_denied"
    if "failed" in statuses:
        return "failed"
    return "stopped"


__all__ = [
    "AiAssistantEventMapping",
    "append_ai_assistant_event",
    "append_ai_assistant_health",
    "ai_assistant_source_status",
]
