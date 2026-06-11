from __future__ import annotations

from .common import BusinessOperationsCollector


QUICKBOOKS_COLLECTOR = BusinessOperationsCollector(
    provider_id="quickbooks",
    app="quickbooks",
    domain="finance",
    description="Accepts QuickBooks Online webhook metadata for invoices, payments, customers, reports, exports, and browser-extension finance workflow events.",
    source_channel="quickbooks_webhooks+browser_extension",
    docs_url="https://developer.intuit.com/app/developer/qbo/docs/develop/webhooks",
    required_scopes=("com.intuit.quickbooks.accounting",),
)
