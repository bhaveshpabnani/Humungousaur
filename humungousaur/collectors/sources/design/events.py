from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from ...models import CollectorEvent
from ..workspace_connectors import append_connector_source_event, connector_source_status, record_connector_source_health
from .common import DESIGN_PROVIDER_DISPLAY_NAMES, DESIGN_PROVIDER_IDS, clean_token
from .registry import design_app_status_records


_PROVIDER_ALIASES = {
    "figma": "figma",
    "figjam": "figjam",
    "fig_jam": "figjam",
    "miro": "miro",
    "canva": "canva",
    "sketch": "sketch",
    "adobe_xd": "adobe_xd",
    "xd": "adobe_xd",
}

_EVENT_ALIASES = {
    "file_created": "design_file_created",
    "design_file_created": "design_file_created",
    "file_opened": "design_file_opened",
    "design_file_opened": "design_file_opened",
    "file_update": "design_file_updated",
    "file_updated": "design_file_updated",
    "file_version_update": "design_file_updated",
    "design_file_updated": "design_file_updated",
    "file_comment": "design_comment_added",
    "file_commented": "design_comment_added",
    "comment_added": "design_comment_added",
    "design_comment_added": "design_comment_added",
    "prototype_presented": "prototype_presented",
    "presentation_started": "prototype_presented",
    "library_update": "component_published",
    "component_published": "component_published",
    "component_updated": "component_published",
    "export_completed": "design_exported",
    "design_exported": "design_exported",
    "frame_exported": "design_exported",
    "board_created": "board_created",
    "board_opened": "board_opened",
    "board_updated": "board_edited",
    "board_edited": "board_edited",
    "item_created": "whiteboard_item_created",
    "whiteboard_item_created": "whiteboard_item_created",
    "sticky_created": "sticky_created",
    "diagram_exported": "diagram_exported",
    "collaborator_joined": "collaborator_joined",
    "member_joined": "collaborator_joined",
    "whiteboard_comment_added": "whiteboard_comment_added",
    "board_shared": "board_shared",
}


def append_design_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id = _provider_id(payload)
        source_event = _source_event(provider_id, payload)
        return append_connector_source_event(
            config,
            provider_id=provider_id,
            source_event=source_event,
            object_type=str(payload.get("object_type") or _object_type(payload)),
            object_id=_object_id(payload),
            metadata=_metadata_from_payload(provider_id, payload, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or payload.get("created_at") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_design_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id = _provider_id(payload)
        return record_connector_source_health(
            config,
            provider_id=provider_id,
            status=str(payload.get("status") or "running"),
            message=str(payload.get("message") or ""),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def design_source_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    provider = _normalize_provider(provider_id) if provider_id else None
    sources = []
    for item in ([provider] if provider else DESIGN_PROVIDER_IDS):
        sources.extend(connector_source_status(config, provider_id=item)["sources"])
    app_records = {item["provider_id"]: item for item in design_app_status_records()}
    return {
        "sources": [
            {
                **source,
                "design_app": app_records.get(str(source.get("provider_id")), {}).get("app", str(source.get("provider_id"))),
                "design_domain": app_records.get(str(source.get("provider_id")), {}).get("domain", ""),
                "source_channel": app_records.get(str(source.get("provider_id")), {}).get("source_channel", ""),
                "docs_url": app_records.get(str(source.get("provider_id")), {}).get("docs_url", ""),
            }
            for source in sources
        ],
        "source_count": len(sources),
        "app_collectors": design_app_status_records(),
        "owner": "humungousaur.collectors.sources.design",
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "file_names_redacted": True,
            "comments_redacted": True,
            "export_paths_redacted": True,
        },
    }


def read_design_events(
    config: AgentConfig,
    state: dict[str, Any],
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    max_events: int = 20,
) -> list[CollectorEvent]:
    del config, state, collector, allowed_stimulus_types, max_events
    return []


def _provider_id(payload: dict[str, Any]) -> str:
    return _normalize_provider(payload.get("provider_id") or payload.get("provider") or payload.get("app") or payload.get("service"))


def _normalize_provider(value: Any) -> str:
    token = clean_token(value)
    provider = _PROVIDER_ALIASES.get(token)
    if not provider:
        raise ValueError(f"unsupported design provider: {value or '<provider>'}")
    return provider


def _source_event(provider_id: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("topic"))
    canonical = _EVENT_ALIASES.get(event_type)
    if not canonical:
        raise ValueError(f"unsupported design event mapping: {provider_id}:{event_type or '<event_type>'}")
    return f"{provider_id}_{canonical}"


def _metadata_from_payload(provider_id: str, payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean["source_event"] = source_event
    clean["app"] = provider_id
    clean["provider_display_name"] = DESIGN_PROVIDER_DISPLAY_NAMES[provider_id]
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("topic"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "actor_count",
        "board_id",
        "component_count",
        "context",
        "event_id",
        "export_format",
        "file_id",
        "file_key",
        "item_count",
        "object_type",
        "provider_event_id",
        "source_channel",
        "team_id",
        "version_id",
        "workspace_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in ("title", "name", "file_name", "board_name", "comment", "comment_body", "path", "url", "email", "actor_name", "participant_name"):
        if redacted in payload:
            clean[f"{redacted}_redacted"] = True
    return clean


def _object_id(payload: dict[str, Any]) -> str:
    for key in ("object_id", "file_key", "file_id", "board_id", "design_id", "item_id", "version_id", "component_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _object_type(payload: dict[str, Any]) -> str:
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("source_event"))
    if "board" in event_type or "sticky" in event_type or "whiteboard" in event_type:
        return "whiteboard"
    if "component" in event_type or "library" in event_type:
        return "component"
    if "comment" in event_type:
        return "comment"
    return "design_file"


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized())
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": "design",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / "design" / "dead_letters.jsonl"
