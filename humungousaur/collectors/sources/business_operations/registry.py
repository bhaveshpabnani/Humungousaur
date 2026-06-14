from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.event_log import CollectorEventLog
from humungousaur.connectors import ConnectorRuntime

from .common import (
    BUSINESS_OPERATIONS_CONSUMER,
    BUSINESS_OPERATIONS_MAX_EVENTS_PER_APP,
    BUSINESS_OPERATIONS_PROVIDER_DISPLAY_NAMES,
    BUSINESS_OPERATIONS_PROVIDER_IDS,
    BusinessOperationsCollector,
    aggregate_app_status,
    collector_status_record,
    utc_now,
)
from .freshdesk import FRESHDESK_COLLECTOR
from .hubspot import HUBSPOT_COLLECTOR
from .intercom import INTERCOM_COLLECTOR
from .quickbooks import QUICKBOOKS_COLLECTOR
from .salesforce import SALESFORCE_COLLECTOR
from .shopify import SHOPIFY_COLLECTOR
from .stripe import STRIPE_COLLECTOR
from .xero import XERO_COLLECTOR
from .zendesk import ZENDESK_COLLECTOR


SQUARE_COLLECTOR = BusinessOperationsCollector(
    provider_id="square",
    app="square",
    domain="commerce",
    description="Accepts Square webhook/browser metadata for payments, orders, customers, refunds, and dashboard activity.",
    source_channel="square_webhooks+browser_extension",
    docs_url="https://developer.squareup.com/docs/webhooks/overview",
)
PAYPAL_COLLECTOR = BusinessOperationsCollector(
    provider_id="paypal",
    app="paypal",
    domain="commerce",
    description="Accepts PayPal webhook/browser metadata for payments, orders, invoices, refunds, subscriptions, and dashboard activity.",
    source_channel="paypal_webhooks+browser_extension",
    docs_url="https://developer.paypal.com/api/rest/webhooks/",
)
PLAID_COLLECTOR = BusinessOperationsCollector(
    provider_id="plaid",
    app="plaid",
    domain="finance",
    description="Accepts Plaid webhook metadata for item, transaction, account, and sync status events.",
    source_channel="plaid_webhooks",
    docs_url="https://plaid.com/docs/api/webhooks/",
)
WISE_COLLECTOR = BusinessOperationsCollector(
    provider_id="wise",
    app="wise",
    domain="finance",
    description="Accepts Wise webhook/browser metadata for profiles, transfers, balances, recipients, and statements.",
    source_channel="wise_webhooks+browser_extension",
    docs_url="https://docs.wise.com/api-docs/guides/webhooks-notifications",
)
MERCURY_COLLECTOR = BusinessOperationsCollector(
    provider_id="mercury",
    app="mercury",
    domain="finance",
    description="Accepts Mercury API/webhook/browser metadata for accounts, transactions, payments, cards, and statements.",
    source_channel="mercury_api_or_browser_extension",
    docs_url="https://docs.mercury.com/reference/getting-started-with-your-api",
)
BREX_COLLECTOR = BusinessOperationsCollector(
    provider_id="brex",
    app="brex",
    domain="finance",
    description="Accepts Brex API/webhook/browser metadata for cards, expenses, transactions, vendors, and reimbursements.",
    source_channel="brex_api_or_webhooks+browser_extension",
    docs_url="https://developer.brex.com/guides/authentication",
)
RAMP_COLLECTOR = BusinessOperationsCollector(
    provider_id="ramp",
    app="ramp",
    domain="finance",
    description="Accepts Ramp API/webhook/browser metadata for transactions, cards, bills, reimbursements, and vendors.",
    source_channel="ramp_api_or_webhooks+browser_extension",
    docs_url="https://docs.ramp.com/developer-api/v1/authorization",
)
MAILCHIMP_COLLECTOR = BusinessOperationsCollector(
    provider_id="mailchimp",
    app="mailchimp",
    domain="marketing",
    description="Accepts Mailchimp webhook/API/browser metadata for campaign, audience, member, automation, and report activity.",
    source_channel="mailchimp_webhooks+browser_extension",
    docs_url="https://mailchimp.com/developer/marketing/guides/sync-audience-data-webhooks/",
)


BUSINESS_OPERATIONS_APP_COLLECTORS: tuple[Any, ...] = (
    SALESFORCE_COLLECTOR,
    HUBSPOT_COLLECTOR,
    ZENDESK_COLLECTOR,
    INTERCOM_COLLECTOR,
    FRESHDESK_COLLECTOR,
    STRIPE_COLLECTOR,
    SHOPIFY_COLLECTOR,
    SQUARE_COLLECTOR,
    PAYPAL_COLLECTOR,
    QUICKBOOKS_COLLECTOR,
    XERO_COLLECTOR,
    PLAID_COLLECTOR,
    WISE_COLLECTOR,
    MERCURY_COLLECTOR,
    BREX_COLLECTOR,
    RAMP_COLLECTOR,
    MAILCHIMP_COLLECTOR,
)


def business_operations_app_status_records() -> list[dict[str, Any]]:
    return [collector_status_record(collector) for collector in BUSINESS_OPERATIONS_APP_COLLECTORS]


def business_operations_provider_ids() -> tuple[str, ...]:
    return BUSINESS_OPERATIONS_PROVIDER_IDS


def business_operations_provider_display_name(provider_id: str) -> str:
    return BUSINESS_OPERATIONS_PROVIDER_DISPLAY_NAMES[provider_id]


def run_business_operations_source_tick(
    config: AgentConfig,
    provider_id: str | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized = config.normalized()
    collectors = _collectors(provider_id)
    log = CollectorEventLog(normalized.collector_events_db_path)
    state = log.consumer_state(BUSINESS_OPERATIONS_CONSUMER)
    source_state = state.setdefault("sources", {}).setdefault("business_operations", {})
    app_states = source_state.setdefault("apps", {})
    runtime = ConnectorRuntime(normalized)
    results = []
    for collector in collectors:
        readiness = runtime.readiness(collector.provider_id)
        app_state = app_states.setdefault(collector.provider_id, {})
        app_state["last_tick_at"] = utc_now()
        app_state["tick_count"] = int(app_state.get("tick_count") or 0) + 1
        result = collector.collect(
            readiness,
            app_state,
            dry_run=dry_run,
            max_events=BUSINESS_OPERATIONS_MAX_EVENTS_PER_APP,
        )
        results.append(result)
    if not dry_run:
        log.save_consumer_state(BUSINESS_OPERATIONS_CONSUMER, state)
    return {
        "status": "succeeded",
        "sources": results,
        "source_count": len(results),
        "aggregate_status": aggregate_app_status(results),
        "dry_run": dry_run,
        "owner": "humungousaur.collectors.sources.business_operations",
    }


def _collectors(provider_id: str | None = None) -> tuple[Any, ...]:
    provider = str(provider_id or "").strip()
    if not provider:
        return BUSINESS_OPERATIONS_APP_COLLECTORS
    matches = tuple(collector for collector in BUSINESS_OPERATIONS_APP_COLLECTORS if collector.provider_id == provider)
    if not matches:
        raise ValueError(f"unsupported business operations provider: {provider_id or '<provider>'}")
    return matches


__all__ = [
    "BUSINESS_OPERATIONS_APP_COLLECTORS",
    "business_operations_app_status_records",
    "business_operations_provider_display_name",
    "business_operations_provider_ids",
    "run_business_operations_source_tick",
]
