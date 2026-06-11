from __future__ import annotations

from .common import (
    MICROSOFT_365_CALENDAR_SCOPE,
    MICROSOFT_365_FILES_SCOPE,
    MICROSOFT_365_MAIL_SCOPE,
    MICROSOFT_365_ONENOTE_SCOPE,
    MICROSOFT_365_PRESENCE_SCOPE,
    MICROSOFT_365_PROVIDER_ID,
    MICROSOFT_365_SITES_SCOPE,
    MICROSOFT_365_TASKS_SCOPE,
    MICROSOFT_365_TEAMS_CHANNEL_SCOPE,
    MICROSOFT_365_TEAMS_CHAT_SCOPE,
)
from .events import (
    append_microsoft_365_event,
    append_microsoft_365_health,
    microsoft_365_source_status,
    read_microsoft_365_events,
)
from .registry import MICROSOFT_365_APP_COLLECTORS, microsoft_365_app_status_records, run_microsoft_365_source_tick


__all__ = [
    "MICROSOFT_365_APP_COLLECTORS",
    "MICROSOFT_365_CALENDAR_SCOPE",
    "MICROSOFT_365_FILES_SCOPE",
    "MICROSOFT_365_MAIL_SCOPE",
    "MICROSOFT_365_ONENOTE_SCOPE",
    "MICROSOFT_365_PRESENCE_SCOPE",
    "MICROSOFT_365_PROVIDER_ID",
    "MICROSOFT_365_SITES_SCOPE",
    "MICROSOFT_365_TASKS_SCOPE",
    "MICROSOFT_365_TEAMS_CHANNEL_SCOPE",
    "MICROSOFT_365_TEAMS_CHAT_SCOPE",
    "append_microsoft_365_event",
    "append_microsoft_365_health",
    "microsoft_365_app_status_records",
    "microsoft_365_source_status",
    "read_microsoft_365_events",
    "run_microsoft_365_source_tick",
]
