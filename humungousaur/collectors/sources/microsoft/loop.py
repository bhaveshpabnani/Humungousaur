from __future__ import annotations

from .common import Microsoft365BridgeCollector


MICROSOFT_LOOP_COLLECTOR = Microsoft365BridgeCollector(
    app="loop",
    required_scopes=(),
    description="Collects Microsoft Loop component/page/task metadata from Loop web app, Teams, Outlook, OneNote, or browser-extension ingress; Graph does not expose a stable first-class Loop delta API.",
    source_channel="loop_web_app+teams_outlook_onenote_ingress",
    implementation_level="browser_or_app_ingress",
    poller_supported=False,
    webhook_supported=True,
)
