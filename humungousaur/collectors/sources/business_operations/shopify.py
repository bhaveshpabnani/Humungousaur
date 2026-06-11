from __future__ import annotations

from .common import BusinessOperationsCollector


SHOPIFY_COLLECTOR = BusinessOperationsCollector(
    provider_id="shopify",
    app="shopify",
    domain="commerce",
    description="Accepts Shopify webhook metadata for orders, customers, refunds, fulfillments, products, exports, and admin dashboard views.",
    source_channel="admin_webhooks+browser_extension",
    docs_url="https://shopify.dev/docs/apps/build/webhooks",
    required_scopes=("read_orders", "read_customers", "read_products"),
)
