from __future__ import annotations

from .common import BusinessOperationsCollector


HUBSPOT_COLLECTOR = BusinessOperationsCollector(
    provider_id="hubspot",
    app="hubspot",
    domain="crm",
    description="Accepts HubSpot CRM object webhook, ticket, deal, export/report, and browser-extension CRM activity metadata.",
    source_channel="crm_webhooks+browser_extension",
    docs_url="https://developers.hubspot.com/docs/api-reference/legacy/webhooks/guide",
    required_scopes=("crm.objects.contacts.read", "crm.objects.deals.read", "tickets"),
)
