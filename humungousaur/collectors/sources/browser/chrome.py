from __future__ import annotations

from .common import BROWSER_EVENT_FAMILIES, BrowserAppCollector


CHROME_BROWSER_COLLECTOR = BrowserAppCollector(
    browser="chrome",
    display_name="Google Chrome",
    engine="chromium",
    extension_family="chrome_extensions_mv3",
    description="Collects Chrome tab, window, profile, navigation, download/upload, form, page-error, extension, web-app, and view-mode metadata from an opt-in extension or native messaging host.",
    supported_events=BROWSER_EVENT_FAMILIES,
)
