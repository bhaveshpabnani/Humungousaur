from __future__ import annotations

from .common import BROWSER_EVENT_FAMILIES, BrowserAppCollector


BRAVE_BROWSER_COLLECTOR = BrowserAppCollector(
    browser="brave",
    display_name="Brave",
    engine="chromium",
    extension_family="chrome_extensions_mv3",
    description="Collects Brave browser workflow metadata through Chromium-compatible extension events with privacy-first URL/title redaction.",
    supported_events=BROWSER_EVENT_FAMILIES,
)
