from __future__ import annotations

from typing import Any

from humungousaur.tools.activity.implementation import ACTIVITY_SOURCES

from ..definitions import SENSITIVE_COLLECTORS
from ..models import CollectorEvent, CollectorProfile


def activity_payload(event: CollectorEvent) -> dict[str, Any]:
    activity_source = event.collector if event.collector in ACTIVITY_SOURCES else event.source
    return {
        "source": activity_source,
        "text": event.text,
        "app_name": str(event.metadata.get("app_name", "")),
        "window_title": str(event.metadata.get("window_title", "")),
        "url": str(event.metadata.get("url", "")),
        "metadata": {key: str(value) for key, value in event.metadata.items()},
    }


def sensitive_event_reason(profile: CollectorProfile, event: CollectorEvent) -> str | None:
    if event.collector in SENSITIVE_COLLECTORS and not profile.rich_capture_opt_in.get(event.collector, False):
        return "rich capture collector is not opted in"
    if event.collector in {"active_window", "browser", "screen_ocr", "screenshot", "video_frame"}:
        text = " ".join(
            [
                str(event.metadata.get("app_name", "")),
                str(event.metadata.get("window_title", "")),
                str(event.metadata.get("url", "")),
            ]
        ).lower()
        if any(term in text for term in ("private browsing", "incognito", "password", "1password", "keychain")):
            return "sensitive private or credential context"
    return None
