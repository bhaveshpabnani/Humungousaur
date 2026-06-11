from __future__ import annotations

from .common import BusinessOperationsCollector


ZENDESK_COLLECTOR = BusinessOperationsCollector(
    provider_id="zendesk",
    app="zendesk",
    domain="support",
    description="Accepts Zendesk ticket, comment/reply, assignment, escalation, SLA, and browser-extension support desk metadata.",
    source_channel="zendesk_webhooks+browser_extension",
    docs_url="https://developer.zendesk.com/documentation/webhooks/",
    required_scopes=("read",),
)
