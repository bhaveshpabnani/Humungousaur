from __future__ import annotations

from .common import BusinessOperationsCollector


STRIPE_COLLECTOR = BusinessOperationsCollector(
    provider_id="stripe",
    app="stripe",
    domain="finance",
    description="Accepts Stripe webhook metadata for payments, invoices, customers, subscriptions, refunds, exports, and dashboard views.",
    source_channel="stripe_webhooks+browser_extension",
    docs_url="https://docs.stripe.com/webhooks",
    required_scopes=("read_only",),
)
