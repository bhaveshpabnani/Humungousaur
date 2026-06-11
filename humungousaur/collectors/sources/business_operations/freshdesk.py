from __future__ import annotations

from .common import BusinessOperationsCollector


FRESHDESK_COLLECTOR = BusinessOperationsCollector(
    provider_id="freshdesk",
    app="freshdesk",
    domain="support",
    description="Accepts Freshdesk ticket webhook, reply, assignment, resolution, SLA, and browser-extension support workflow metadata.",
    source_channel="freshdesk_webhooks+browser_extension",
    docs_url="https://developers.freshdesk.com/api/",
    required_scopes=("tickets.read",),
)
