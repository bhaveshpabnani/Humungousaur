from __future__ import annotations

from typing import Any


_EXPORTS = {
    "DATA_ANALYTICS_APP_COLLECTORS": (".registry", "DATA_ANALYTICS_APP_COLLECTORS"),
    "DATA_ANALYTICS_CONSUMER": (".common", "DATA_ANALYTICS_CONSUMER"),
    "DATA_ANALYTICS_MAX_EVENTS_PER_APP": (".common", "DATA_ANALYTICS_MAX_EVENTS_PER_APP"),
    "DATA_ANALYTICS_PROVIDER_DISPLAY_NAMES": (".common", "DATA_ANALYTICS_PROVIDER_DISPLAY_NAMES"),
    "DATA_ANALYTICS_PROVIDER_IDS": (".common", "DATA_ANALYTICS_PROVIDER_IDS"),
    "DATA_ANALYTICS_SOURCE_MANIFESTS": (".registry", "DATA_ANALYTICS_SOURCE_MANIFESTS"),
    "append_data_analytics_event": (".events", "append_data_analytics_event"),
    "append_data_analytics_health": (".events", "append_data_analytics_health"),
    "data_analytics_app_status_records": (".registry", "data_analytics_app_status_records"),
    "data_analytics_source_status": (".events", "data_analytics_source_status"),
    "read_data_analytics_events": (".events", "read_data_analytics_events"),
    "run_data_analytics_source_tick": (".registry", "run_data_analytics_source_tick"),
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
