from __future__ import annotations

from typing import Any

from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.config import AgentConfig

from ..workspace_connectors import record_connector_source_health
from .common import (
    KNOWLEDGE_BASE_CONSUMER,
    KnowledgeBaseAppCollector,
    _aggregate_app_status,
    _collector_status_record,
    _readiness,
    _utc_now,
)


KNOWLEDGE_BASE_APP_COLLECTORS: tuple[KnowledgeBaseAppCollector, ...] = (
    KnowledgeBaseAppCollector(
        provider_id="notion",
        app="notion",
        display_name="Notion",
        description="Accepts Notion page, database, task, comment, link, and workspace metadata from webhooks, browser extensions, or connector pollers.",
        source_channel="notion_webhook+api_poller+browser_extension",
        implementation_level="webhook_or_extension_ingress",
        required_scopes=("read_content",),
        poller_supported=True,
        webhook_supported=True,
        official_docs=("https://developers.notion.com/reference/intro", "https://developers.notion.com/reference/webhooks"),
    ),
    KnowledgeBaseAppCollector(
        provider_id="confluence",
        app="confluence",
        display_name="Confluence",
        description="Accepts Confluence page, database, comment, link, and workspace metadata from webhooks or connector pollers.",
        source_channel="confluence_webhook+api_poller+browser_extension",
        implementation_level="webhook_or_extension_ingress",
        required_scopes=("read:page:confluence",),
        poller_supported=True,
        webhook_supported=True,
        official_docs=("https://developer.atlassian.com/cloud/confluence/rest/v2/",),
    ),
    KnowledgeBaseAppCollector(
        provider_id="coda",
        app="coda",
        display_name="Coda",
        description="Accepts Coda doc, page, table, row, task, comment, link, and workspace metadata from connector pollers or Pack/browser ingress.",
        source_channel="coda_api_poller+pack_or_browser_extension",
        implementation_level="poller_or_extension_ingress",
        poller_supported=True,
        webhook_supported=True,
        official_docs=("https://coda.io/developers/apis/v1",),
    ),
    KnowledgeBaseAppCollector(
        provider_id="obsidian",
        app="obsidian",
        display_name="Obsidian",
        description="Accepts local Obsidian vault, note, task, link, and backlink metadata from a plugin or local vault bridge.",
        source_channel="obsidian_plugin+local_vault_bridge",
        implementation_level="local_plugin_or_bridge_ingress",
        poller_supported=False,
        webhook_supported=False,
        local_bridge_supported=True,
        official_docs=("https://docs.obsidian.md/Plugins/Getting+started/Plugin+structure",),
    ),
    KnowledgeBaseAppCollector(
        provider_id="evernote",
        app="evernote",
        display_name="Evernote",
        description="Accepts Evernote note, task, comment, link, and workspace metadata from webhooks or connector pollers.",
        source_channel="evernote_webhook+api_poller",
        implementation_level="webhook_or_poller_ingress",
        poller_supported=True,
        webhook_supported=True,
        official_docs=("https://dev.evernote.com/doc/",),
    ),
    KnowledgeBaseAppCollector(
        provider_id="apple_local",
        app="apple_notes",
        display_name="Apple Notes",
        description="Accepts Apple Notes note, checklist, link, and workspace metadata from local automation or app bridges.",
        source_channel="apple_notes_local_bridge+app_automation",
        implementation_level="local_app_bridge_ingress",
        poller_supported=False,
        webhook_supported=False,
        local_bridge_supported=True,
        official_docs=("https://developer.apple.com/documentation/scriptingbridge",),
    ),
    KnowledgeBaseAppCollector(
        provider_id="microsoft_365",
        app="onenote",
        display_name="OneNote",
        description="Accepts OneNote page, section, comment, link, and notebook metadata through Microsoft Graph change notifications or delta-style pollers.",
        source_channel="microsoft_graph_onenote+change_notifications",
        implementation_level="scope_gated_poller_or_webhook_ingress",
        required_scopes=("Notes.Read",),
        poller_supported=True,
        webhook_supported=True,
        official_docs=("https://learn.microsoft.com/en-us/graph/api/resources/onenote-api-overview", "https://learn.microsoft.com/en-us/graph/change-notifications-overview"),
    ),
)


def knowledge_base_app_status_records(provider_id: str | None = None) -> list[dict[str, Any]]:
    provider = str(provider_id or "").strip()
    collectors = [collector for collector in KNOWLEDGE_BASE_APP_COLLECTORS if not provider or collector.provider_id == provider]
    return [_collector_status_record(collector) for collector in collectors]


def run_knowledge_base_source_tick(
    config: AgentConfig,
    *,
    provider_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized = config.normalized()
    provider = str(provider_id or "").strip()
    collectors = [collector for collector in KNOWLEDGE_BASE_APP_COLLECTORS if not provider or collector.provider_id == provider]
    if provider and not collectors:
        raise KeyError(f"Unknown knowledge-base source provider: {provider_id}")
    event_log = CollectorEventLog(normalized.collector_events_db_path)
    state = event_log.consumer_state(KNOWLEDGE_BASE_CONSUMER)
    source_states = state.setdefault("sources", {})
    results = []
    for collector in collectors:
        source_state = source_states.setdefault(collector.provider_id, {})
        app_states = source_state.setdefault("apps", {})
        app_state = app_states.setdefault(collector.app, {})
        source_state["last_tick_at"] = _utc_now()
        source_state["tick_count"] = int(source_state.get("tick_count") or 0) + 1
        source_state["collector_owner"] = "humungousaur.collectors.sources.knowledge_base"
        readiness = _readiness(normalized, collector.provider_id)
        app_result = collector.collect(normalized, readiness, app_state, dry_run=dry_run, max_events=20)
        status = _aggregate_app_status([app_result])
        if not dry_run:
            record_connector_source_health(
                normalized,
                provider_id=collector.provider_id,
                status=status,
                message="Knowledge-base source collector tick completed; events arrive through provider webhooks, app plugins, browser extensions, or local bridges.",
                metadata={
                    "app": collector.app,
                    "source_channel": collector.source_channel,
                    "last_tick_at": source_state["last_tick_at"],
                },
            )
        results.append(
            {
                "provider_id": collector.provider_id,
                "status": status,
                "events_appended": int(app_result.get("events_appended") or 0),
                "last_tick_at": source_state["last_tick_at"],
                "poller_supported": collector.poller_supported,
                "webhook_supported": collector.webhook_supported,
                "local_bridge_supported": collector.local_bridge_supported,
                "connector_readiness": readiness,
                "apps": [app_result],
            }
        )
    if not dry_run:
        event_log.save_consumer_state(KNOWLEDGE_BASE_CONSUMER, state)
    return {"status": "succeeded", "sources": results, "source_count": len(results), "dry_run": dry_run}


__all__ = [
    "KNOWLEDGE_BASE_APP_COLLECTORS",
    "knowledge_base_app_status_records",
    "run_knowledge_base_source_tick",
]
