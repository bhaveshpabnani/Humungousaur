from __future__ import annotations

from .common import GOOGLE_WORKSPACE_CALENDAR_SCOPE, GoogleWorkspaceBridgeCollector


GOOGLE_MEET_COLLECTOR = GoogleWorkspaceBridgeCollector(
    app="meet",
    required_scopes=(GOOGLE_WORKSPACE_CALENDAR_SCOPE,),
    description="Collects Google Meet lifecycle, call-control, screen-share, transcript, and recording metadata from Calendar context, browser extensions, add-ons, and webhooks.",
    source_channel="calendar_events+meet_browser_extension+webhook",
    implementation_level="calendar_context_and_extension_ingress",
    poller_supported=False,
    webhook_supported=True,
    derived_from=("calendar",),
)
