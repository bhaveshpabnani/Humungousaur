from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from ...models import CollectorEvent
from ..workspace_connectors import append_connector_source_event, connector_source_status, record_connector_source_health
from .common import OPERATIONS_PROVIDER_DISPLAY_NAMES, OPERATIONS_PROVIDER_IDS, clean_token
from .registry import operations_app_status_records


_PROVIDER_ALIASES = {provider: provider for provider in OPERATIONS_PROVIDER_IDS}
_PROVIDER_ALIASES.update({"google_cloud": "gcp", "google_cloud_platform": "gcp", "pager_duty": "pagerduty", "ops_genie": "opsgenie"})

_EVENT_ALIASES = {
    "incident_triggered": "incident_declared",
    "incident_declared": "incident_declared",
    "trigger": "incident_declared",
    "incident_acknowledged": "incident_acknowledged",
    "acknowledged": "incident_acknowledged",
    "acknowledge": "incident_acknowledged",
    "incident_escalated": "incident_escalated",
    "escalated": "incident_escalated",
    "incident_resolved": "incident_resolved",
    "resolved": "incident_resolved",
    "alert_triggered": "on_call_alert_received",
    "monitor_alert": "on_call_alert_received",
    "on_call_alert_received": "on_call_alert_received",
    "runbook_opened": "runbook_opened",
    "status_page_updated": "status_page_updated",
    "metric_threshold_crossed": "metric_threshold_crossed",
    "threshold_crossed": "metric_threshold_crossed",
    "dashboard_opened": "dashboard_opened",
    "dashboard_filter_changed": "dashboard_filter_changed",
    "resource_opened": "cloud_resource_opened",
    "cloud_resource_opened": "cloud_resource_opened",
    "resource_changed": "cloud_resource_changed",
    "cloud_resource_changed": "cloud_resource_changed",
    "deployment_created": "deployment_started",
    "deployment_started": "deployment_started",
    "deploy_started": "deployment_started",
    "deployment_failed": "deployment_failed",
    "deploy_failed": "deployment_failed",
    "deployment_error": "deployment_failed",
    "secret_view_attempted": "secret_view_attempted",
    "secret_accessed": "secret_view_attempted",
    "billing_alert": "billing_alert_seen",
    "billing_alert_seen": "billing_alert_seen",
    "permission_denied": "permission_error_seen",
    "permission_error_seen": "permission_error_seen",
    "container_started": "container_started",
    "container_stopped": "container_stopped",
    "container_failed": "container_failed",
    "image_build_started": "image_build_started",
    "build_started": "image_build_started",
    "image_build_failed": "image_build_failed",
    "build_failed": "image_build_failed",
}


def append_operations_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
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


def append_operations_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
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


def operations_source_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    provider = _normalize_provider(provider_id) if provider_id else None
    sources = []
    for item in ([provider] if provider else OPERATIONS_PROVIDER_IDS):
        sources.extend(connector_source_status(config, provider_id=item)["sources"])
    app_records = {item["provider_id"]: item for item in operations_app_status_records()}
    return {
        "sources": [
            {
                **source,
                "operations_app": app_records.get(str(source.get("provider_id")), {}).get("app", str(source.get("provider_id"))),
                "operations_domain": app_records.get(str(source.get("provider_id")), {}).get("domain", ""),
                "source_channel": app_records.get(str(source.get("provider_id")), {}).get("source_channel", ""),
                "docs_url": app_records.get(str(source.get("provider_id")), {}).get("docs_url", ""),
            }
            for source in sources
        ],
        "source_count": len(sources),
        "app_collectors": operations_app_status_records(),
        "owner": "humungousaur.collectors.sources.operations",
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "resource_ids_hashed": True,
            "alert_bodies_redacted": True,
            "logs_redacted": True,
            "secrets_redacted": True,
        },
    }


def read_operations_events(
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
        raise ValueError(f"unsupported operations provider: {value or '<provider>'}")
    return provider


def _source_event(provider_id: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("topic"))
    canonical = _EVENT_ALIASES.get(event_type)
    if not canonical:
        raise ValueError(f"unsupported operations event mapping: {provider_id}:{event_type or '<event_type>'}")
    return f"{provider_id}_{canonical}"


def _metadata_from_payload(provider_id: str, payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean["source_event"] = source_event
    clean["app"] = provider_id
    clean["provider_display_name"] = OPERATIONS_PROVIDER_DISPLAY_NAMES[provider_id]
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("topic"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "alert_id",
        "deployment_id",
        "event_id",
        "incident_id",
        "namespace",
        "object_type",
        "project_id",
        "provider_event_id",
        "region",
        "resource_id",
        "service",
        "severity",
        "source_channel",
        "status",
        "team_id",
        "workflow_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in ("title", "name", "description", "message", "body", "log", "query", "url", "path", "email", "resource_name", "secret_name"):
        if redacted in payload:
            clean[f"{redacted}_redacted"] = True
    return clean


def _object_id(payload: dict[str, Any]) -> str:
    for key in ("object_id", "incident_id", "alert_id", "event_id", "deployment_id", "resource_id", "container_id", "pod_uid"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _object_type(payload: dict[str, Any]) -> str:
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("source_event"))
    if "incident" in event_type or "alert" in event_type:
        return "incident"
    if "deployment" in event_type or "deploy" in event_type:
        return "deployment"
    if "container" in event_type or "image" in event_type:
        return "runtime"
    return "cloud_resource"


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized())
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": "operations",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / "operations" / "dead_letters.jsonl"
