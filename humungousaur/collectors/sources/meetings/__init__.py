from __future__ import annotations

from typing import Any


_EXPORTS = {
    "MEETING_PROVIDER_CATALOG": (".catalog", "MEETING_PROVIDER_CATALOG"),
    "MeetingMappingSpec": (".catalog", "MeetingMappingSpec"),
    "MeetingProviderCatalogEntry": (".catalog", "MeetingProviderCatalogEntry"),
    "append_discord_call_gateway_event": (".events", "append_discord_call_gateway_event"),
    "append_google_meet_event": (".events", "append_google_meet_event"),
    "append_meeting_source_event": (".events", "append_meeting_source_event"),
    "append_meeting_source_health": (".events", "append_meeting_source_health"),
    "append_teams_meeting_graph_event": (".events", "append_teams_meeting_graph_event"),
    "append_webex_webhook_event": (".events", "append_webex_webhook_event"),
    "append_zoom_webhook_event": (".events", "append_zoom_webhook_event"),
    "meeting_app_status_records": (".registry", "meeting_app_status_records"),
    "meeting_mapping_specs": (".catalog", "meeting_mapping_specs"),
    "meeting_provider_entry": (".catalog", "meeting_provider_entry"),
    "meeting_provider_ids": (".catalog", "meeting_provider_ids"),
    "meeting_source_status": (".events", "meeting_source_status"),
    "read_meeting_source_events": (".events", "read_meeting_source_events"),
    "run_meeting_source_tick": (".events", "run_meeting_source_tick"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    from importlib import import_module

    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
