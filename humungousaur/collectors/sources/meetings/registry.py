from __future__ import annotations

from typing import Any

from .catalog import MEETING_PROVIDER_CATALOG


def meeting_app_status_records() -> list[dict[str, Any]]:
    return [
        {
            "provider_id": entry.provider_id,
            "app": entry.app,
            "display_name": entry.display_name,
            "source_type": entry.source_type,
            "source_channel": entry.source_channel,
            "implementation_level": entry.implementation_level,
            "poller_supported": entry.poller_supported,
            "webhook_supported": entry.webhook_supported,
            "notes": entry.notes,
            "docs_url": entry.docs_url,
        }
        for entry in MEETING_PROVIDER_CATALOG
    ]


__all__ = ["meeting_app_status_records"]
