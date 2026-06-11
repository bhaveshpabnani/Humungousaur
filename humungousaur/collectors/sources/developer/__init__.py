from __future__ import annotations

from typing import Any


_EXPORTS = {
    "DEVELOPER_SOURCE_MANIFESTS": (".registry", "DEVELOPER_SOURCE_MANIFESTS"),
    "append_code_hosting_webhook_event": (".code_hosting", "append_code_hosting_webhook_event"),
    "append_developer_source_event": (".events", "append_developer_source_event"),
    "developer_source_manifest_records": (".registry", "developer_source_manifest_records"),
    "normalize_code_hosting_webhook": (".code_hosting", "normalize_code_hosting_webhook"),
    "normalize_developer_source_event": (".events", "normalize_developer_source_event"),
    "run_developer_source_tick": (".registry", "run_developer_source_tick"),
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
