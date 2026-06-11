from __future__ import annotations

from .common import BROWSER_EVENT_FAMILIES, BrowserAppCollector


EDGE_BROWSER_COLLECTOR = BrowserAppCollector(
    browser="edge",
    display_name="Microsoft Edge",
    engine="chromium",
    extension_family="chrome_extensions_mv3",
    description="Collects Edge browser workflow metadata through the Chromium extension API surface or native messaging bridge.",
    supported_events=BROWSER_EVENT_FAMILIES,
)
