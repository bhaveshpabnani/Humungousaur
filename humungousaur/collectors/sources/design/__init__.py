from __future__ import annotations

from typing import Any


_EXPORTS = {
    "DESIGN_APP_COLLECTORS": (".registry", "DESIGN_APP_COLLECTORS"),
    "DESIGN_CONSUMER": (".common", "DESIGN_CONSUMER"),
    "DESIGN_MAX_EVENTS_PER_APP": (".common", "DESIGN_MAX_EVENTS_PER_APP"),
    "DESIGN_PROVIDER_DISPLAY_NAMES": (".common", "DESIGN_PROVIDER_DISPLAY_NAMES"),
    "DESIGN_PROVIDER_IDS": (".common", "DESIGN_PROVIDER_IDS"),
    "DESIGN_SOURCE_MANIFESTS": (".registry", "DESIGN_SOURCE_MANIFESTS"),
    "append_design_event": (".events", "append_design_event"),
    "append_design_health": (".events", "append_design_health"),
    "design_app_status_records": (".registry", "design_app_status_records"),
    "design_source_status": (".events", "design_source_status"),
    "read_design_events": (".events", "read_design_events"),
    "run_design_source_tick": (".registry", "run_design_source_tick"),
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
