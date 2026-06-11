from __future__ import annotations

from .common import BROWSER_EVENT_FAMILIES, BrowserAppCollector


FIREFOX_BROWSER_COLLECTOR = BrowserAppCollector(
    browser="firefox",
    display_name="Firefox",
    engine="gecko",
    extension_family="webextensions",
    description="Collects Firefox tab, navigation, download/upload, form, page-error, extension, web-app, and view-mode metadata through WebExtensions or native messaging.",
    supported_events=BROWSER_EVENT_FAMILIES,
)
