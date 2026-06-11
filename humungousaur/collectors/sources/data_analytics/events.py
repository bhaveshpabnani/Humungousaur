from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from ...models import CollectorEvent
from ..workspace_connectors import append_connector_source_event, connector_source_status, record_connector_source_health
from .common import DATA_ANALYTICS_PROVIDER_DISPLAY_NAMES, DATA_ANALYTICS_PROVIDER_IDS, clean_token
from .registry import data_analytics_app_status_records


_PROVIDER_ALIASES = {provider: provider for provider in DATA_ANALYTICS_PROVIDER_IDS}
_PROVIDER_ALIASES.update({"powerbi": "power_bi", "ga4": "google_analytics", "mongo_atlas": "mongodb_atlas", "mongo": "mongodb_atlas"})

_EVENT_ALIASES = {
    "dashboard_opened": "dashboard_opened",
    "dashboard_viewed": "dashboard_opened",
    "filter_changed": "dashboard_filter_changed",
    "dashboard_filter_changed": "dashboard_filter_changed",
    "report_exported": "report_exported",
    "export_completed": "report_exported",
    "alert_triggered": "metric_threshold_crossed",
    "threshold_crossed": "metric_threshold_crossed",
    "metric_threshold_crossed": "metric_threshold_crossed",
    "query_result_viewed": "query_result_viewed",
    "query_result": "query_result_viewed",
    "chart_drilled_down": "chart_drilled_down",
    "drilldown": "chart_drilled_down",
    "database_connected": "database_connected",
    "connection_opened": "database_connected",
    "database_disconnected": "database_disconnected",
    "connection_closed": "database_disconnected",
    "query_started": "query_started",
    "job_started": "query_started",
    "query_completed": "query_completed",
    "job_completed": "query_completed",
    "query_failed": "query_failed",
    "job_failed": "query_failed",
    "schema_changed": "schema_changed",
    "table_schema_changed": "schema_changed",
    "migration_started": "migration_started",
    "migration_failed": "migration_failed",
}


def append_data_analytics_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
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


def append_data_analytics_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
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


def data_analytics_source_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    provider = _normalize_provider(provider_id) if provider_id else None
    sources = []
    for item in ([provider] if provider else DATA_ANALYTICS_PROVIDER_IDS):
        sources.extend(connector_source_status(config, provider_id=item)["sources"])
    app_records = {item["provider_id"]: item for item in data_analytics_app_status_records()}
    return {
        "sources": [
            {
                **source,
                "data_app": app_records.get(str(source.get("provider_id")), {}).get("app", str(source.get("provider_id"))),
                "data_domain": app_records.get(str(source.get("provider_id")), {}).get("domain", ""),
                "source_channel": app_records.get(str(source.get("provider_id")), {}).get("source_channel", ""),
                "docs_url": app_records.get(str(source.get("provider_id")), {}).get("docs_url", ""),
            }
            for source in sources
        ],
        "source_count": len(sources),
        "app_collectors": data_analytics_app_status_records(),
        "owner": "humungousaur.collectors.sources.data_analytics",
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "sql_redacted": True,
            "query_results_redacted": True,
            "dashboard_titles_redacted": True,
        },
    }


def read_data_analytics_events(
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
        raise ValueError(f"unsupported data/analytics provider: {value or '<provider>'}")
    return provider


def _source_event(provider_id: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("topic"))
    canonical = _EVENT_ALIASES.get(event_type)
    if not canonical:
        raise ValueError(f"unsupported data/analytics event mapping: {provider_id}:{event_type or '<event_type>'}")
    return f"{provider_id}_{canonical}"


def _metadata_from_payload(provider_id: str, payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean["source_event"] = source_event
    clean["app"] = provider_id
    clean["provider_display_name"] = DATA_ANALYTICS_PROVIDER_DISPLAY_NAMES[provider_id]
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("topic"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "dashboard_id",
        "dataset_id",
        "duration_ms",
        "event_id",
        "job_id",
        "object_type",
        "project_id",
        "provider_event_id",
        "query_id",
        "refresh_state",
        "row_count_bucket",
        "schema_id",
        "source_channel",
        "status",
        "table_id",
        "warehouse_id",
        "workspace_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in ("title", "name", "dashboard_name", "report_name", "query", "sql", "result", "value", "path", "url", "email", "user_name"):
        if redacted in payload:
            clean[f"{redacted}_redacted"] = True
    return clean


def _object_id(payload: dict[str, Any]) -> str:
    for key in ("object_id", "query_id", "job_id", "dashboard_id", "report_id", "dataset_id", "table_id", "schema_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _object_type(payload: dict[str, Any]) -> str:
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("source_event"))
    if "dashboard" in event_type or "report" in event_type or "chart" in event_type:
        return "analytics_asset"
    if "schema" in event_type:
        return "schema"
    if "migration" in event_type:
        return "migration"
    return "query"


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized())
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": "data_analytics",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / "data_analytics" / "dead_letters.jsonl"
