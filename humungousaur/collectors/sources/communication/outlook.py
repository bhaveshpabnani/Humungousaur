from __future__ import annotations

from .common import CommunicationBridgeCollector


OUTLOOK_COMMUNICATION_COLLECTOR = CommunicationBridgeCollector(
    app="outlook",
    provider_id="microsoft_365",
    display_name="Outlook",
    required_scopes=("Mail.Read",),
    description="Collects Outlook received/opened/sent/draft/reply/forward/folder/label/search/attachment metadata from Microsoft Graph change notifications, delta queries, or add-in/browser ingress.",
    source_channel="graph_change_notifications+delta_query+office_addin+browser_extension",
    docs_url="https://learn.microsoft.com/en-us/graph/outlook-change-notifications-overview",
    implementation_level="poller_or_webhook_ingress",
    poller_supported=True,
    webhook_supported=True,
)

