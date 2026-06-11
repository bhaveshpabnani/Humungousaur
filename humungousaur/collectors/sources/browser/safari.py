from __future__ import annotations

from .common import BROWSER_EVENT_FAMILIES, BrowserAppCollector


SAFARI_BROWSER_COLLECTOR = BrowserAppCollector(
    browser="safari",
    display_name="Safari",
    engine="webkit",
    extension_family="safari_web_extensions",
    description="Collects Safari browser workflow metadata through Safari Web Extensions or the native app-extension bridge where APIs are available.",
    supported_events=BROWSER_EVENT_FAMILIES,
)
