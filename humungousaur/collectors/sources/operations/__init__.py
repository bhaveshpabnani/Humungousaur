from __future__ import annotations

from typing import Any


_EXPORTS = {
    "OPERATIONS_APP_COLLECTORS": (".registry", "OPERATIONS_APP_COLLECTORS"),
    "OPERATIONS_CONSUMER": (".common", "OPERATIONS_CONSUMER"),
    "OPERATIONS_MAX_EVENTS_PER_APP": (".common", "OPERATIONS_MAX_EVENTS_PER_APP"),
    "OPERATIONS_PROVIDER_DISPLAY_NAMES": (".common", "OPERATIONS_PROVIDER_DISPLAY_NAMES"),
    "OPERATIONS_PROVIDER_IDS": (".common", "OPERATIONS_PROVIDER_IDS"),
    "OPERATIONS_SOURCE_MANIFESTS": (".registry", "OPERATIONS_SOURCE_MANIFESTS"),
    "append_operations_event": (".events", "append_operations_event"),
    "append_operations_health": (".events", "append_operations_health"),
    "operations_app_status_records": (".registry", "operations_app_status_records"),
    "operations_source_status": (".events", "operations_source_status"),
    "read_operations_events": (".events", "read_operations_events"),
    "run_operations_source_tick": (".registry", "run_operations_source_tick"),
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
