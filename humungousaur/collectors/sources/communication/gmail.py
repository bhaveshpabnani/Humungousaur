from __future__ import annotations

from .common import CommunicationBridgeCollector


GMAIL_COMMUNICATION_COLLECTOR = CommunicationBridgeCollector(
    app="gmail",
    provider_id="google_workspace",
    display_name="Gmail",
    required_scopes=("https://www.googleapis.com/auth/gmail.readonly",),
    description="Collects Gmail received/opened/sent/draft/reply/forward/label/search/attachment metadata from Gmail push notifications, History API deltas, or browser/add-on ingress.",
    source_channel="gmail_push+history_api+browser_extension+workspace_addon",
    docs_url="https://developers.google.com/workspace/gmail/api/guides/push",
    implementation_level="poller_or_webhook_ingress",
    poller_supported=True,
    webhook_supported=True,
)

