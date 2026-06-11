from __future__ import annotations

from typing import Any


_EXPORTS = {
    "CLOUD_FILE_PROVIDER_IDS": (".registry", "CLOUD_FILE_PROVIDER_IDS"),
    "CLOUD_FILE_SOURCE_MANIFESTS": (".registry", "CLOUD_FILE_SOURCE_MANIFESTS"),
    "append_cloud_file_event": (".events", "append_cloud_file_event"),
    "cloud_file_source_status": (".events", "cloud_file_source_status"),
    "run_cloud_file_source_tick": (".registry", "run_cloud_file_source_tick"),
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
