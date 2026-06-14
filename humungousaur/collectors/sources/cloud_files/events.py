from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from .common import CLOUD_FILE_PROVIDER_IDS, clean_token


_PROVIDER_ALIASES = {
    "dropbox": "dropbox",
    "box": "box",
    "icloud": "icloud",
    "icloud_drive": "icloud",
    "apple_icloud": "icloud",
    "google": "google_workspace",
    "google_drive": "google_workspace",
    "drive": "google_workspace",
    "gdrive": "google_workspace",
    "google_workspace": "google_workspace",
    "microsoft": "microsoft_365",
    "microsoft_365": "microsoft_365",
    "onedrive": "microsoft_365",
    "one_drive": "microsoft_365",
    "sharepoint": "microsoft_365",
    "nextcloud": "nextcloud",
    "nextcloud_files": "nextcloud",
    "nextcloud_drive": "nextcloud",
}

_EVENT_ALIASES = {
    "file_created": "file_created",
    "folder_created": "folder_created",
    "file_renamed": "file_renamed",
    "folder_renamed": "folder_renamed",
    "file_moved": "file_moved",
    "folder_moved": "folder_moved",
    "file_deleted": "file_deleted",
    "folder_deleted": "folder_deleted",
    "file_shared": "file_shared",
    "folder_shared": "file_shared",
    "shared": "file_shared",
    "permission_changed": "permission_changed",
    "permissions_changed": "permission_changed",
    "collaboration_changed": "permission_changed",
    "sync_error": "sync_failed",
    "sync_failed": "sync_failed",
    "conflict": "sync_conflict_detected",
    "sync_conflict": "sync_conflict_detected",
    "sync_conflict_detected": "sync_conflict_detected",
    "restored": "file_restored",
    "file_restored": "file_restored",
    "folder_restored": "file_restored",
    "version_event": "file_version_event",
    "version_created": "file_version_event",
    "version_restored": "file_version_event",
    "file_version_event": "file_version_event",
    "remote_file_changed": "remote_file_changed",
    "file_modified": "remote_file_changed",
}


def append_cloud_file_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    from ..workspace_connectors import append_connector_source_event

    provider_id = _provider_id(payload)
    try:
        source_event = _source_event(provider_id, payload)
        return append_connector_source_event(
            config,
            provider_id=provider_id,
            source_event=source_event,
            object_type=str(payload.get("object_type") or _object_type(payload)),
            object_id=str(payload.get("object_id") or payload.get("file_id") or payload.get("folder_id") or payload.get("item_id") or ""),
            metadata=_metadata_from_payload(payload, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, provider_id, payload, str(exc))
        raise ValueError(str(exc)) from exc


def cloud_file_source_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    from ..workspace_connectors import connector_source_status

    provider = _provider_alias(provider_id) if provider_id else None
    if provider:
        return connector_source_status(config, provider_id=provider)
    sources = []
    for candidate in CLOUD_FILE_PROVIDER_IDS:
        sources.extend(connector_source_status(config, provider_id=candidate)["sources"])
    return {
        "sources": sources,
        "source_count": len(sources),
        "owner": "humungousaur.collectors.sources.cloud_files",
    }


def _provider_id(payload: dict[str, Any]) -> str:
    provider = _provider_alias(payload.get("provider_id") or payload.get("provider") or payload.get("service") or payload.get("app"))
    if not provider:
        raise ValueError("cloud file event requires provider_id")
    return provider


def _provider_alias(value: Any) -> str:
    token = clean_token(value)
    return _PROVIDER_ALIASES.get(token, token if token in CLOUD_FILE_PROVIDER_IDS else "")


def _source_event(provider_id: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    canonical = _EVENT_ALIASES.get(event_type)
    if not canonical:
        raise ValueError(f"unsupported cloud file event mapping: {provider_id}:{event_type or '<event_type>'}")
    if provider_id == "google_workspace":
        return f"drive_cloud_{canonical}"
    if provider_id == "microsoft_365":
        service = clean_token(
            payload.get("service")
            or payload.get("app")
            or payload.get("drive_type")
            or payload.get("provider_id")
            or payload.get("provider")
        )
        prefix = "sharepoint" if "sharepoint" in service else "onedrive"
        return f"{prefix}_{canonical}"
    return f"{provider_id}_{canonical}"


def _metadata_from_payload(payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean["source_event"] = source_event
    clean["app"] = f"{_provider_id(payload)}_drive"
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "account_type",
        "change_origin",
        "conflict",
        "etag",
        "event_id",
        "file_id",
        "folder_id",
        "has_file_facet",
        "has_folder_facet",
        "item_id",
        "mime_type",
        "object_type",
        "permission_role",
        "permission_scope",
        "provider_event_id",
        "rev",
        "source_channel",
        "sync_state",
        "version_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in ("title", "name", "file_name", "filename", "path", "url", "shared_link", "email", "participants", "owner_name"):
        if redacted in payload:
            clean[f"{redacted}_redacted"] = True
    return clean


def _object_type(payload: dict[str, Any]) -> str:
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    if "folder" in event_type:
        return "folder"
    return "cloud_file"


def _append_dead_letter(config: AgentConfig, provider_id: str, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized(), provider_id or "cloud_files")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": provider_id or "cloud_files",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig, provider_id: str) -> Path:
    return config.normalized().data_dir / "collector_sources" / provider_id / "dead_letters.jsonl"
