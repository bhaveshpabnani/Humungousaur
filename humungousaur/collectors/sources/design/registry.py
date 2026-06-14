from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from ..workspace_connectors import ConnectorEventMapping, ConnectorSourceManifest
from .common import (
    DESIGN_CONSUMER,
    DESIGN_MAX_EVENTS_PER_APP,
    DESIGN_PROVIDER_IDS,
    DesignAppCollector,
    aggregate_app_status,
    collector_status_record,
    utc_now,
)


DESIGN_EVENT_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("design_file_created", "creative_activity", "design_file_created", "Design file was created"),
    ConnectorEventMapping("design_file_opened", "creative_activity", "design_file_opened", "Design file was opened"),
    ConnectorEventMapping("design_file_updated", "creative_activity", "design_file_updated", "Design file was updated"),
    ConnectorEventMapping("design_comment_added", "creative_activity", "design_comment_added", "Design comment metadata was added"),
    ConnectorEventMapping("prototype_presented", "creative_activity", "prototype_presented", "Prototype presentation started"),
    ConnectorEventMapping("component_published", "creative_activity", "component_published", "Design component or library was published"),
    ConnectorEventMapping("design_exported", "creative_activity", "design_exported", "Design export completed"),
    ConnectorEventMapping("board_created", "whiteboard_activity", "board_created", "Whiteboard was created"),
    ConnectorEventMapping("board_opened", "whiteboard_activity", "board_opened", "Whiteboard was opened"),
    ConnectorEventMapping("board_edited", "whiteboard_activity", "board_edited", "Whiteboard was edited"),
    ConnectorEventMapping("whiteboard_item_created", "whiteboard_activity", "whiteboard_item_created", "Whiteboard item was created"),
    ConnectorEventMapping("sticky_created", "whiteboard_activity", "sticky_created", "Whiteboard sticky was created"),
    ConnectorEventMapping("diagram_exported", "whiteboard_activity", "diagram_exported", "Whiteboard diagram was exported"),
    ConnectorEventMapping("collaborator_joined", "whiteboard_activity", "collaborator_joined", "Whiteboard collaborator joined"),
    ConnectorEventMapping("whiteboard_comment_added", "whiteboard_activity", "whiteboard_comment_added", "Whiteboard comment metadata was added"),
    ConnectorEventMapping("board_shared", "whiteboard_activity", "board_shared", "Whiteboard sharing changed"),
)


DESIGN_APP_COLLECTORS: tuple[DesignAppCollector, ...] = (
    DesignAppCollector(
        provider_id="figma",
        app="figma",
        domain="design",
        description="Figma webhooks and plugin/app bridge events for file, version, comment, component, prototype, and export metadata.",
        source_channel="figma_webhook_or_plugin",
        docs_url="https://developers.figma.com/docs/rest-api/webhooks/",
        required_scopes=("file_content:read", "file_metadata:read"),
        poller_supported=True,
        webhook_supported=True,
    ),
    DesignAppCollector(
        provider_id="figjam",
        app="figjam",
        domain="whiteboard",
        description="FigJam/Figma bridge events for board, collaborator, sticky, comment, and export metadata.",
        source_channel="figma_webhook_or_plugin",
        docs_url="https://developers.figma.com/docs/rest-api/webhooks/",
        required_scopes=("file_content:read", "file_metadata:read"),
        poller_supported=True,
        webhook_supported=True,
    ),
    DesignAppCollector(
        provider_id="miro",
        app="miro",
        domain="whiteboard",
        description="Miro Web SDK/app events for board UI, realtime, item, collaborator, and export metadata.",
        source_channel="miro_app_sdk_or_webhook",
        docs_url="https://developers.miro.com/docs/events",
        required_scopes=("boards:read",),
        poller_supported=True,
        webhook_supported=True,
    ),
    DesignAppCollector(
        provider_id="canva",
        app="canva",
        domain="design",
        description="Canva design, export, template, and collaboration metadata through connector-backed app or webhook ingress.",
        source_channel="canva_app_or_webhook",
        docs_url="https://www.canva.dev/docs/connect/",
        required_scopes=("design:content:read",),
        poller_supported=True,
        webhook_supported=True,
    ),
    DesignAppCollector(
        provider_id="sketch",
        app="sketch",
        domain="design",
        description="Sketch document/plugin metadata for file opens, component/library changes, exports, and comments.",
        source_channel="local_plugin_or_cloud_webhook",
        docs_url="https://developer.sketch.com/",
        implementation_level="local_plugin_or_cloud_webhook",
        poller_supported=False,
        webhook_supported=True,
    ),
    DesignAppCollector(
        provider_id="adobe_xd",
        app="adobe_xd",
        domain="design",
        description="Adobe XD/plugin metadata for prototype, component, file, and export events.",
        source_channel="local_plugin_or_cloud_webhook",
        docs_url="https://developer.adobe.com/xd/uxp/",
        implementation_level="local_plugin_or_cloud_webhook",
        poller_supported=False,
        webhook_supported=True,
    ),
)


DESIGN_SOURCE_MANIFESTS: tuple[ConnectorSourceManifest, ...] = tuple(
    ConnectorSourceManifest(
        provider_id=collector.provider_id,
        display_name=collector_status_record(collector)["display_name"],
        source_type=collector.source_channel,
        auth_method="oauth2_or_local_plugin_permission",
        collector_mappings=tuple(
            ConnectorEventMapping(
                f"{collector.provider_id}_{mapping.source_event}",
                mapping.collector,
                mapping.stimulus_type,
                f"{collector_status_record(collector)['display_name']} {mapping.text[0].lower()}{mapping.text[1:]}",
            )
            for mapping in DESIGN_EVENT_MAPPINGS
        ),
        poller_supported=collector.poller_supported,
        webhook_supported=collector.webhook_supported,
        requires_connector=collector.requires_connector,
        official_docs=(collector.docs_url,),
        notes=collector.description,
    )
    for collector in DESIGN_APP_COLLECTORS
)


def design_app_status_records() -> list[dict[str, Any]]:
    return [collector_status_record(collector) for collector in DESIGN_APP_COLLECTORS]


def run_design_source_tick(config: AgentConfig, provider_id: str | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    from ..workspace_connectors import record_connector_source_health

    normalized = config.normalized()
    collectors = _collectors(provider_id)
    log = CollectorEventLog(normalized.collector_events_db_path)
    state = log.consumer_state(DESIGN_CONSUMER)
    source_state = state.setdefault("sources", {}).setdefault("design", {})
    app_states = source_state.setdefault("apps", {})
    runtime = ConnectorRuntime(normalized)
    results = []
    for collector in collectors:
        readiness = runtime.readiness(collector.provider_id)
        app_state = app_states.setdefault(collector.provider_id, {})
        app_state["last_tick_at"] = utc_now()
        app_state["tick_count"] = int(app_state.get("tick_count") or 0) + 1
        result = collector.collect(readiness, app_state, dry_run=dry_run, max_events=DESIGN_MAX_EVENTS_PER_APP)
        if not dry_run:
            record_connector_source_health(
                normalized,
                provider_id=collector.provider_id,
                status=str(result.get("status") or "running"),
                message=str(result.get("message") or ""),
                metadata={"last_tick_at": app_state["last_tick_at"], "source_channel": collector.source_channel},
            )
        results.append(result)
    if not dry_run:
        log.save_consumer_state(DESIGN_CONSUMER, state)
    return {
        "status": "succeeded",
        "sources": results,
        "source_count": len(results),
        "aggregate_status": aggregate_app_status(results),
        "dry_run": dry_run,
        "owner": "humungousaur.collectors.sources.design",
    }


def _collectors(provider_id: str | None = None) -> tuple[DesignAppCollector, ...]:
    provider = str(provider_id or "").strip()
    if not provider:
        return DESIGN_APP_COLLECTORS
    matches = tuple(collector for collector in DESIGN_APP_COLLECTORS if collector.provider_id == provider)
    if not matches:
        raise ValueError(f"unsupported design provider: {provider_id or '<provider>'}")
    return matches


__all__ = [
    "DESIGN_APP_COLLECTORS",
    "DESIGN_EVENT_MAPPINGS",
    "DESIGN_PROVIDER_IDS",
    "DESIGN_SOURCE_MANIFESTS",
    "design_app_status_records",
    "run_design_source_tick",
]
