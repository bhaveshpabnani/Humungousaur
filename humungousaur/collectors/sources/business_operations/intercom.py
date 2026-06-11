from __future__ import annotations

from .common import BusinessOperationsCollector


INTERCOM_COLLECTOR = BusinessOperationsCollector(
    provider_id="intercom",
    app="intercom",
    domain="support",
    description="Accepts Intercom conversation, ticket, reply, assignment, resolution, and browser-extension support workflow metadata.",
    source_channel="intercom_webhooks+browser_extension",
    docs_url="https://developers.intercom.com/docs/references/webhooks/",
    required_scopes=("read_conversations", "read_tickets"),
)
