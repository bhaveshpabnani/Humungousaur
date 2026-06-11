from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.config import AgentConfig

from ...models import CollectorEvent
from ..workspace_connectors import (
    append_connector_source_event,
    connector_source_status,
    record_connector_source_health,
    safe_metadata_values,
)
from .common import KNOWLEDGE_BASE_PROVIDER_IDS


_APP_PROVIDER_ALIASES = {
    "notion": ("notion", "notion"),
    "confluence": ("confluence", "confluence"),
    "atlassian_confluence": ("confluence", "confluence"),
    "coda": ("coda", "coda"),
    "obsidian": ("obsidian", "obsidian"),
    "obsidian_vault": ("obsidian", "obsidian"),
    "evernote": ("evernote", "evernote"),
    "apple_notes": ("apple_local", "apple_notes"),
    "notes": ("apple_local", "apple_notes"),
    "onenote": ("microsoft_365", "onenote"),
    "one_note": ("microsoft_365", "onenote"),
    "microsoft_onenote": ("microsoft_365", "onenote"),
}

_EVENT_ALIASES = {
    ("notion", "page_created"): "notion_page_created",
    ("notion", "page_updated"): "notion_page_updated",
    ("notion", "page_edited"): "notion_page_updated",
    ("notion", "database_changed"): "notion_database_changed",
    ("notion", "database_updated"): "notion_database_changed",
    ("notion", "table_changed"): "notion_database_changed",
    ("notion", "task_completed"): "notion_task_completed",
    ("notion", "comment_added"): "notion_comment_added",
    ("notion", "link_created"): "notion_link_created",
    ("notion", "workspace_opened"): "notion_workspace_opened",
    ("confluence", "page_created"): "confluence_page_created",
    ("confluence", "page_updated"): "confluence_page_updated",
    ("confluence", "page_edited"): "confluence_page_updated",
    ("confluence", "database_changed"): "confluence_database_changed",
    ("confluence", "whiteboard_database_changed"): "confluence_database_changed",
    ("confluence", "comment_added"): "confluence_comment_added",
    ("confluence", "link_created"): "confluence_link_created",
    ("confluence", "workspace_opened"): "confluence_workspace_opened",
    ("coda", "page_created"): "coda_page_created",
    ("coda", "page_updated"): "coda_page_updated",
    ("coda", "page_edited"): "coda_page_updated",
    ("coda", "table_changed"): "coda_table_changed",
    ("coda", "row_changed"): "coda_table_changed",
    ("coda", "task_completed"): "coda_task_completed",
    ("coda", "comment_added"): "coda_comment_added",
    ("coda", "link_created"): "coda_link_created",
    ("coda", "workspace_opened"): "coda_workspace_opened",
    ("obsidian", "note_created"): "obsidian_note_created",
    ("obsidian", "note_updated"): "obsidian_note_updated",
    ("obsidian", "note_edited"): "obsidian_note_updated",
    ("obsidian", "task_completed"): "obsidian_task_completed",
    ("obsidian", "link_created"): "obsidian_link_created",
    ("obsidian", "backlink_created"): "obsidian_backlink_created",
    ("obsidian", "vault_opened"): "obsidian_vault_opened",
    ("evernote", "note_created"): "evernote_note_created",
    ("evernote", "note_updated"): "evernote_note_updated",
    ("evernote", "note_edited"): "evernote_note_updated",
    ("evernote", "task_completed"): "evernote_task_completed",
    ("evernote", "comment_added"): "evernote_comment_added",
    ("evernote", "link_created"): "evernote_link_created",
    ("evernote", "workspace_opened"): "evernote_workspace_opened",
    ("apple_notes", "note_created"): "apple_notes_note_created",
    ("apple_notes", "note_updated"): "apple_notes_note_updated",
    ("apple_notes", "note_edited"): "apple_notes_note_updated",
    ("apple_notes", "task_completed"): "apple_notes_task_completed",
    ("apple_notes", "link_created"): "apple_notes_link_created",
    ("apple_notes", "workspace_opened"): "apple_notes_workspace_opened",
    ("onenote", "page_created"): "onenote_page_created",
    ("onenote", "page_updated"): "onenote_page_updated",
    ("onenote", "page_edited"): "onenote_page_updated",
    ("onenote", "note_created"): "onenote_page_created",
    ("onenote", "note_updated"): "onenote_page_updated",
    ("onenote", "section_changed"): "onenote_section_changed",
    ("onenote", "comment_added"): "onenote_comment_added",
    ("onenote", "link_created"): "onenote_link_created",
    ("onenote", "workspace_opened"): "onenote_workspace_opened",
}


def append_knowledge_base_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id, app = _provider_and_app(payload)
        source_event = _source_event(payload, app)
        return append_connector_source_event(
            config,
            provider_id=provider_id,
            source_event=source_event,
            object_type=str(payload.get("object_type") or _default_object_type(source_event)),
            object_id=str(
                payload.get("object_id")
                or payload.get("page_id")
                or payload.get("note_id")
                or payload.get("database_id")
                or payload.get("table_id")
                or payload.get("workspace_id")
                or payload.get("vault_id")
                or ""
            ),
            metadata=_metadata_from_payload(payload, app, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_knowledge_base_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id, app = _provider_and_app(payload)
        status = str(payload.get("status") or "running").strip()
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        metadata = {"app": app, **metadata}
        return record_connector_source_health(
            config,
            provider_id=provider_id,
            status=status,
            message=str(payload.get("message") or ""),
            metadata=metadata,
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def knowledge_base_source_status(config: AgentConfig) -> dict[str, Any]:
    from .registry import knowledge_base_app_status_records

    config = config.normalized()
    source_status = connector_source_status(config)
    providers = set(KNOWLEDGE_BASE_PROVIDER_IDS)
    sources = [source for source in source_status.get("sources", []) if str(source.get("provider_id")) in providers]
    pending_counts = {provider: 0 for provider in providers}
    for event in CollectorEventLog(config.collector_events_db_path).query(limit=2000):
        source = str(event.get("source") or "")
        if source in pending_counts:
            pending_counts[source] += 1
    for source in sources:
        provider = str(source.get("provider_id") or "")
        source["pending_event_count"] = pending_counts.get(provider, 0)
        source["dead_letter_count"] = _line_count(_dead_letters_path(config))
    return {
        "source": "knowledge_bases",
        "status": _aggregate_health_status(sources),
        "sources": sources,
        "source_count": len(sources),
        "app_collectors": knowledge_base_app_status_records(),
        "supported_apps": ["apple_notes", "coda", "confluence", "evernote", "notion", "obsidian", "onenote"],
        "mapping_count": sum(len(source.get("collector_mappings", ())) for source in sources if isinstance(source, dict)),
        "dead_letters_path": str(_dead_letters_path(config)),
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "provider_content_redacted": True,
        },
    }


def read_knowledge_base_events(
    config: AgentConfig,
    state: dict[str, Any],
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    max_events: int = 20,
) -> list[CollectorEvent]:
    del config, state, collector, allowed_stimulus_types, max_events
    return []


def _provider_and_app(payload: dict[str, Any]) -> tuple[str, str]:
    explicit_provider = _clean_token(payload.get("provider_id") or payload.get("provider"))
    app_token = _clean_token(payload.get("app") or payload.get("service") or payload.get("application") or explicit_provider)
    provider_id, app = _APP_PROVIDER_ALIASES.get(app_token, (explicit_provider, app_token))
    if explicit_provider and explicit_provider in KNOWLEDGE_BASE_PROVIDER_IDS:
        provider_id = explicit_provider
    if provider_id == "apple_local" and app not in {"apple_notes", "notes"}:
        app = "apple_notes"
    if provider_id == "microsoft_365" and app not in {"onenote", "one_note", "microsoft_onenote"}:
        app = "onenote"
    app = "apple_notes" if app == "notes" else "onenote" if app in {"one_note", "microsoft_onenote"} else app
    if provider_id not in KNOWLEDGE_BASE_PROVIDER_IDS:
        raise ValueError(f"unsupported knowledge-base provider: {provider_id or '<provider>'}")
    if not app:
        raise ValueError("knowledge-base event requires app or provider")
    return provider_id, app


def _source_event(payload: dict[str, Any], app: str) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = _clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    source_event = _EVENT_ALIASES.get((app, event_type))
    if not source_event:
        raise ValueError(f"unsupported knowledge-base event mapping: {app or '<app>'}:{event_type or '<event_type>'}")
    return source_event


def _metadata_from_payload(payload: dict[str, Any], app: str, source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean["app"] = app
    clean["source_event"] = source_event
    event_type = _clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "attachment_count",
        "backlink_count",
        "block_count",
        "comment_count",
        "database_id",
        "database_count",
        "has_attachments",
        "link_count",
        "note_id",
        "object_type",
        "page_id",
        "provider_event_id",
        "row_count",
        "table_id",
        "task_id",
        "vault_id",
        "workspace_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in (
        "title",
        "name",
        "body",
        "text",
        "content",
        "url",
        "path",
        "query",
        "comment",
        "task_title",
        "page_title",
        "note_title",
        "table_name",
        "database_name",
        "workspace_name",
        "vault_name",
        "author",
        "participants",
    ):
        if redacted in payload:
            clean[f"{redacted}_redacted"] = True
    return clean


def _default_object_type(source_event: str) -> str:
    if "database" in source_event:
        return "database"
    if "table" in source_event:
        return "table"
    if "vault" in source_event:
        return "vault"
    if "workspace" in source_event:
        return "workspace"
    if "note" in source_event:
        return "note"
    if "task" in source_event:
        return "task"
    if "comment" in source_event:
        return "comment"
    if "link" in source_event:
        return "link"
    return "page"


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized())
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": "knowledge_bases",
        "metadata": safe_metadata_values(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / "knowledge_bases" / "dead_letters.jsonl"


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


def _aggregate_health_status(sources: list[dict[str, Any]]) -> str:
    statuses = {
        str((source.get("helper_health") or [{}])[0].get("status") or "")
        for source in sources
        if isinstance(source.get("helper_health"), list) and source.get("helper_health")
    }
    if "running" in statuses and statuses.intersection({"permission_denied", "failed", "rate_limited"}):
        return "degraded"
    if "running" in statuses:
        return "running"
    if "failed" in statuses:
        return "failed"
    if "permission_denied" in statuses:
        return "permission_denied"
    return "not_configured"


def _clean_token(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", "_").replace(".", "_").split())
