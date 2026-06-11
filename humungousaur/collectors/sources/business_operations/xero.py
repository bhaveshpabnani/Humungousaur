from __future__ import annotations

from .common import BusinessOperationsCollector


XERO_COLLECTOR = BusinessOperationsCollector(
    provider_id="xero",
    app="xero",
    domain="finance",
    description="Accepts Xero webhook metadata for invoices, contacts/customers, payments, reports, exports, and browser-extension finance workflow events.",
    source_channel="xero_webhooks+browser_extension",
    docs_url="https://developer.xero.com/documentation/guides/webhooks/overview/",
    required_scopes=("accounting.transactions.read", "accounting.contacts.read", "offline_access"),
)
