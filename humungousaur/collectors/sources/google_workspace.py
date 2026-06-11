from __future__ import annotations

from .google import (
    GOOGLE_WORKSPACE_APP_COLLECTORS,
    GOOGLE_WORKSPACE_CALENDAR_SCOPE,
    GOOGLE_WORKSPACE_CHAT_SCOPE,
    GOOGLE_WORKSPACE_CONTACTS_SCOPE,
    GOOGLE_WORKSPACE_DRIVE_SCOPE,
    GOOGLE_WORKSPACE_GMAIL_SCOPE,
    GOOGLE_WORKSPACE_KEEP_SCOPE,
    GOOGLE_WORKSPACE_PROVIDER_ID,
    GOOGLE_WORKSPACE_TASKS_SCOPE,
    append_google_workspace_event,
    append_google_workspace_health,
    google_workspace_app_status_records,
    google_workspace_source_status,
    read_google_workspace_events,
)
from .google import registry as _google_registry
from .google.registry import ConnectorRuntime


def run_google_workspace_source_tick(config, *, dry_run: bool = False):
    original_runtime = _google_registry.ConnectorRuntime
    _google_registry.ConnectorRuntime = ConnectorRuntime
    try:
        return _google_registry.run_google_workspace_source_tick(config, dry_run=dry_run)
    finally:
        _google_registry.ConnectorRuntime = original_runtime

__all__ = [
    "GOOGLE_WORKSPACE_APP_COLLECTORS",
    "GOOGLE_WORKSPACE_CALENDAR_SCOPE",
    "GOOGLE_WORKSPACE_CHAT_SCOPE",
    "GOOGLE_WORKSPACE_CONTACTS_SCOPE",
    "GOOGLE_WORKSPACE_DRIVE_SCOPE",
    "GOOGLE_WORKSPACE_GMAIL_SCOPE",
    "GOOGLE_WORKSPACE_KEEP_SCOPE",
    "GOOGLE_WORKSPACE_PROVIDER_ID",
    "GOOGLE_WORKSPACE_TASKS_SCOPE",
    "ConnectorRuntime",
    "append_google_workspace_event",
    "append_google_workspace_health",
    "google_workspace_app_status_records",
    "google_workspace_source_status",
    "read_google_workspace_events",
    "run_google_workspace_source_tick",
]
