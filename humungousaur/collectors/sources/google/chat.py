from __future__ import annotations

from .common import GOOGLE_WORKSPACE_CHAT_SCOPE, GoogleWorkspaceBridgeCollector


GOOGLE_CHAT_COLLECTOR = GoogleWorkspaceBridgeCollector(
    app="chat",
    required_scopes=(GOOGLE_WORKSPACE_CHAT_SCOPE,),
    description="Collects Google Chat message, mention, thread, reaction, space navigation, and presence metadata from Chat events or browser extension ingress.",
    source_channel="chat_events+browser_extension+webhook",
    implementation_level="webhook_or_extension_ingress",
    poller_supported=False,
    webhook_supported=True,
)
