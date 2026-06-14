from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig

from ...models import CollectorEvent
from ..workspace_connectors import (
    append_connector_source_event,
    connector_source_status,
    record_connector_source_health,
)
from .common import BUSINESS_OPERATIONS_PROVIDER_DISPLAY_NAMES, BUSINESS_OPERATIONS_PROVIDER_IDS
from .registry import business_operations_app_status_records


_PROVIDER_ALIASES = {
    "salesforce": "salesforce",
    "sf": "salesforce",
    "hubspot": "hubspot",
    "zendesk": "zendesk",
    "intercom": "intercom",
    "freshdesk": "freshdesk",
    "freshworks": "freshdesk",
    "stripe": "stripe",
    "shopify": "shopify",
    "square": "square",
    "paypal": "paypal",
    "quickbooks": "quickbooks",
    "quickbooks_online": "quickbooks",
    "qbo": "quickbooks",
    "xero": "xero",
    "plaid": "plaid",
    "wise": "wise",
    "mercury": "mercury",
    "brex": "brex",
    "ramp": "ramp",
    "mailchimp": "mailchimp",
}

_EVENT_ALIASES = {
    ("salesforce", "record_viewed"): "salesforce_record_viewed",
    ("salesforce", "record_opened"): "salesforce_record_viewed",
    ("salesforce", "change_data_capture"): "salesforce_record_updated",
    ("salesforce", "record_updated"): "salesforce_record_updated",
    ("salesforce", "lead_created"): "salesforce_lead_created",
    ("salesforce", "deal_stage_changed"): "salesforce_deal_stage_changed",
    ("salesforce", "opportunity_stage_changed"): "salesforce_deal_stage_changed",
    ("salesforce", "casecommentchangeevent"): "salesforce_customer_note_added",
    ("salesforce", "customer_note_added"): "salesforce_customer_note_added",
    ("salesforce", "followup_scheduled"): "salesforce_followup_scheduled",
    ("salesforce", "dashboard_viewed"): "salesforce_dashboard_viewed",
    ("salesforce", "report_exported"): "salesforce_report_exported",
    ("hubspot", "record_viewed"): "hubspot_record_viewed",
    ("hubspot", "record_opened"): "hubspot_record_viewed",
    ("hubspot", "contact.propertychange"): "hubspot_record_updated",
    ("hubspot", "company.propertychange"): "hubspot_record_updated",
    ("hubspot", "deal.propertychange"): "hubspot_deal_stage_changed",
    ("hubspot", "record_updated"): "hubspot_record_updated",
    ("hubspot", "lead_created"): "hubspot_lead_created",
    ("hubspot", "deal_stage_changed"): "hubspot_deal_stage_changed",
    ("hubspot", "note_created"): "hubspot_customer_note_added",
    ("hubspot", "customer_note_added"): "hubspot_customer_note_added",
    ("hubspot", "followup_scheduled"): "hubspot_followup_scheduled",
    ("hubspot", "ticket.creation"): "hubspot_ticket_opened",
    ("hubspot", "ticket.propertychange"): "hubspot_ticket_updated",
    ("hubspot", "ticket_opened"): "hubspot_ticket_opened",
    ("hubspot", "ticket_assigned"): "hubspot_ticket_assigned",
    ("hubspot", "ticket_updated"): "hubspot_ticket_updated",
    ("hubspot", "ticket_replied"): "hubspot_ticket_replied",
    ("hubspot", "ticket_resolved"): "hubspot_ticket_resolved",
    ("hubspot", "ticket_escalated"): "hubspot_ticket_escalated",
    ("hubspot", "sla_breach_warning"): "hubspot_sla_breach_warning",
    ("hubspot", "dashboard_viewed"): "hubspot_dashboard_viewed",
    ("hubspot", "report_exported"): "hubspot_report_exported",
    ("zendesk", "ticket_created"): "zendesk_ticket_opened",
    ("zendesk", "ticket_opened"): "zendesk_ticket_opened",
    ("zendesk", "ticket_assigned"): "zendesk_ticket_assigned",
    ("zendesk", "ticket_updated"): "zendesk_ticket_updated",
    ("zendesk", "ticket_commented"): "zendesk_ticket_replied",
    ("zendesk", "ticket_replied"): "zendesk_ticket_replied",
    ("zendesk", "ticket_solved"): "zendesk_ticket_resolved",
    ("zendesk", "ticket_resolved"): "zendesk_ticket_resolved",
    ("zendesk", "ticket_escalated"): "zendesk_ticket_escalated",
    ("zendesk", "sla_breach_warning"): "zendesk_sla_breach_warning",
    ("intercom", "conversation.created"): "intercom_ticket_opened",
    ("intercom", "conversation.user.replied"): "intercom_ticket_replied",
    ("intercom", "conversation.admin.replied"): "intercom_ticket_replied",
    ("intercom", "conversation.assigned"): "intercom_ticket_assigned",
    ("intercom", "conversation.closed"): "intercom_ticket_resolved",
    ("intercom", "ticket.created"): "intercom_ticket_opened",
    ("intercom", "ticket.updated"): "intercom_ticket_updated",
    ("intercom", "ticket.resolved"): "intercom_ticket_resolved",
    ("freshdesk", "ticket_created"): "freshdesk_ticket_opened",
    ("freshdesk", "ticket_opened"): "freshdesk_ticket_opened",
    ("freshdesk", "ticket_assigned"): "freshdesk_ticket_assigned",
    ("freshdesk", "ticket_updated"): "freshdesk_ticket_updated",
    ("freshdesk", "ticket_replied"): "freshdesk_ticket_replied",
    ("freshdesk", "ticket_resolved"): "freshdesk_ticket_resolved",
    ("freshdesk", "ticket_escalated"): "freshdesk_ticket_escalated",
    ("freshdesk", "sla_breach_warning"): "freshdesk_sla_breach_warning",
    ("stripe", "payment_intent.succeeded"): "stripe_payment_completed",
    ("stripe", "charge.succeeded"): "stripe_payment_completed",
    ("stripe", "payment_intent.payment_failed"): "stripe_payment_failed",
    ("stripe", "invoice.created"): "stripe_invoice_created",
    ("stripe", "invoice.updated"): "stripe_invoice_updated",
    ("stripe", "invoice.paid"): "stripe_invoice_paid",
    ("stripe", "invoice.payment_failed"): "stripe_invoice_payment_failed",
    ("stripe", "customer.created"): "stripe_customer_created",
    ("stripe", "customer.updated"): "stripe_customer_updated",
    ("stripe", "customer.subscription.created"): "stripe_subscription_changed",
    ("stripe", "customer.subscription.updated"): "stripe_subscription_changed",
    ("stripe", "refund.created"): "stripe_refund_created",
    ("stripe", "reporting.report_run.succeeded"): "stripe_report_exported",
    ("stripe", "dashboard_viewed"): "stripe_dashboard_viewed",
    ("shopify", "orders/create"): "shopify_order_created",
    ("shopify", "orders/updated"): "shopify_order_updated",
    ("shopify", "orders/paid"): "shopify_order_paid",
    ("shopify", "orders/fulfilled"): "shopify_order_fulfilled",
    ("shopify", "orders/cancelled"): "shopify_order_cancelled",
    ("shopify", "customers/create"): "shopify_customer_created",
    ("shopify", "customers/update"): "shopify_customer_updated",
    ("shopify", "refunds/create"): "shopify_refund_status_changed",
    ("shopify", "dashboard_viewed"): "shopify_dashboard_viewed",
    ("shopify", "report_exported"): "shopify_report_exported",
    ("square", "payment.created"): "square_payment_completed",
    ("square", "payment.updated"): "square_payment_completed",
    ("square", "payment.failed"): "square_payment_failed",
    ("square", "order.created"): "square_order_created",
    ("square", "order.updated"): "square_order_updated",
    ("square", "refund.created"): "square_refund_created",
    ("square", "customer.created"): "square_customer_created",
    ("square", "customer.updated"): "square_customer_updated",
    ("square", "dashboard_viewed"): "square_dashboard_viewed",
    ("paypal", "checkout.order.approved"): "paypal_order_created",
    ("paypal", "payment.capture.completed"): "paypal_payment_completed",
    ("paypal", "payment.capture.denied"): "paypal_payment_failed",
    ("paypal", "invoicing.invoice.created"): "paypal_invoice_created",
    ("paypal", "invoicing.invoice.paid"): "paypal_invoice_paid",
    ("paypal", "customer.dispute.created"): "paypal_ticket_opened",
    ("paypal", "refund.created"): "paypal_refund_created",
    ("quickbooks", "invoice_create"): "quickbooks_invoice_created",
    ("quickbooks", "invoice_update"): "quickbooks_invoice_updated",
    ("quickbooks", "payment_create"): "quickbooks_payment_completed",
    ("quickbooks", "customer_create"): "quickbooks_customer_created",
    ("quickbooks", "customer_update"): "quickbooks_customer_updated",
    ("quickbooks", "report_exported"): "quickbooks_report_exported",
    ("quickbooks", "dashboard_viewed"): "quickbooks_dashboard_viewed",
    ("xero", "invoice_created"): "xero_invoice_created",
    ("xero", "invoice_updated"): "xero_invoice_updated",
    ("xero", "invoice_paid"): "xero_invoice_paid",
    ("xero", "payment_created"): "xero_payment_completed",
    ("xero", "contact_created"): "xero_customer_created",
    ("xero", "contact_updated"): "xero_customer_updated",
    ("xero", "report_exported"): "xero_report_exported",
    ("xero", "dashboard_viewed"): "xero_dashboard_viewed",
    ("plaid", "transactions"): "plaid_report_exported",
    ("plaid", "transactions_updates_available"): "plaid_report_exported",
    ("plaid", "item_error"): "plaid_payment_failed",
    ("plaid", "item_login_repaired"): "plaid_customer_updated",
    ("wise", "transfer_state_change"): "wise_payment_completed",
    ("wise", "balance_update"): "wise_report_exported",
    ("wise", "profile_updated"): "wise_customer_updated",
    ("mercury", "transaction.created"): "mercury_payment_completed",
    ("mercury", "transaction.updated"): "mercury_payment_completed",
    ("mercury", "payment.created"): "mercury_payment_completed",
    ("mercury", "payment.failed"): "mercury_payment_failed",
    ("brex", "transaction.created"): "brex_payment_completed",
    ("brex", "transaction.updated"): "brex_payment_completed",
    ("brex", "card.created"): "brex_customer_created",
    ("ramp", "transaction.created"): "ramp_payment_completed",
    ("ramp", "transaction.updated"): "ramp_payment_completed",
    ("ramp", "bill.created"): "ramp_invoice_created",
    ("ramp", "reimbursement.created"): "ramp_payment_completed",
    ("mailchimp", "subscribe"): "mailchimp_dashboard_viewed",
    ("mailchimp", "unsubscribe"): "mailchimp_dashboard_viewed",
    ("mailchimp", "campaign_sent"): "mailchimp_report_exported",
    ("mailchimp", "report_exported"): "mailchimp_report_exported",
}


def append_business_operations_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id = _provider_id(payload)
        source_event = _source_event(provider_id, payload)
        return append_connector_source_event(
            config,
            provider_id=provider_id,
            source_event=source_event,
            object_type=str(payload.get("object_type") or _object_type(payload) or ""),
            object_id=_object_id(payload),
            metadata=_metadata_from_payload(provider_id, payload, source_event),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or payload.get("created_at") or ""),
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_business_operations_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_id = _provider_id(payload)
        return record_connector_source_health(
            config,
            provider_id=provider_id,
            status=str(payload.get("status") or "running"),
            message=str(payload.get("message") or ""),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def business_operations_source_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    provider = _normalize_provider(provider_id) if provider_id else None
    if provider:
        status = connector_source_status(config, provider_id=provider)
        sources = status.get("sources", [])
    else:
        sources = []
        for item in BUSINESS_OPERATIONS_PROVIDER_IDS:
            try:
                sources.extend(connector_source_status(config, provider_id=item).get("sources", []))
            except KeyError:
                continue
    app_records = {item["provider_id"]: item for item in business_operations_app_status_records()}
    return {
        "sources": [
            {
                **source,
                "business_app": app_records.get(str(source.get("provider_id")), {}).get("app", str(source.get("provider_id"))),
                "business_domain": app_records.get(str(source.get("provider_id")), {}).get("domain", ""),
                "source_channel": app_records.get(str(source.get("provider_id")), {}).get("source_channel", ""),
                "docs_url": app_records.get(str(source.get("provider_id")), {}).get("docs_url", ""),
            }
            for source in sources
        ],
        "source_count": len(sources),
        "app_collectors": business_operations_app_status_records(),
        "owner": "humungousaur.collectors.sources.business_operations",
        "privacy_contract": {
            "default_privacy_tier": "sensitive_metadata",
            "raw_content_included": False,
            "customer_data_redacted": True,
        },
    }


def read_business_operations_events(
    config: AgentConfig,
    state: dict[str, Any],
    collector: str,
    allowed_stimulus_types: set[str],
    *,
    max_events: int = 20,
) -> list[CollectorEvent]:
    del config, state, collector, allowed_stimulus_types, max_events
    return []


def _provider_id(payload: dict[str, Any]) -> str:
    return _normalize_provider(payload.get("provider_id") or payload.get("provider") or payload.get("app") or payload.get("service"))


def _normalize_provider(value: Any) -> str:
    token = _clean_token(value)
    provider = _PROVIDER_ALIASES.get(token)
    if not provider:
        raise ValueError(f"unsupported business operations provider: {value or '<provider>'}")
    return provider


def _source_event(provider_id: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = _clean_event_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("topic"))
    source_event = _EVENT_ALIASES.get((provider_id, event_type))
    if not source_event:
        raise ValueError(f"unsupported business operations event mapping: {provider_id}:{event_type or '<event_type>'}")
    return source_event


def _object_type(payload: dict[str, Any]) -> str:
    for key in ("object_type", "entity_type", "resource_type", "record_type", "crm_object_type"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _object_id(payload: dict[str, Any]) -> str:
    for key in (
        "object_id",
        "entity_id",
        "record_id",
        "ticket_id",
        "conversation_id",
        "invoice_id",
        "payment_id",
        "customer_id",
        "order_id",
        "report_id",
        "dashboard_id",
        "provider_event_id",
        "id",
    ):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _metadata_from_payload(provider_id: str, payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean = dict(metadata)
    clean.update(
        {
            "app": provider_id,
            "provider_display_name": BUSINESS_OPERATIONS_PROVIDER_DISPLAY_NAMES[provider_id],
            "source_event": source_event,
            "source_channel": _source_channel(provider_id),
            "implementation_level": "webhook_or_browser_ingress",
        }
    )
    event_type = _clean_event_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type") or payload.get("topic"))
    if event_type:
        clean["provider_event_type"] = event_type
    for key in (
        "account_id",
        "company_id",
        "customer_id",
        "dashboard_id",
        "deal_id",
        "entity_id",
        "invoice_id",
        "object_type",
        "order_id",
        "payment_id",
        "provider_event_id",
        "record_id",
        "report_id",
        "subscription_id",
        "ticket_id",
        "user_id",
    ):
        if key in payload:
            clean[key] = payload[key]
    for redacted in (
        "account_name",
        "amount",
        "body",
        "company_name",
        "customer",
        "customer_email",
        "customer_name",
        "description",
        "email",
        "message",
        "name",
        "note",
        "phone",
        "record_name",
        "report_name",
        "subject",
        "ticket_title",
        "title",
        "url",
    ):
        if redacted in payload:
            clean[f"{redacted}_redacted"] = True
    return clean


def _source_channel(provider_id: str) -> str:
    mapping = {
        "salesforce": "change_data_capture+platform_events+browser_extension",
        "hubspot": "crm_webhooks+browser_extension",
        "zendesk": "zendesk_webhooks+browser_extension",
        "intercom": "intercom_webhooks+browser_extension",
        "freshdesk": "freshdesk_webhooks+browser_extension",
        "stripe": "stripe_webhooks+browser_extension",
        "shopify": "admin_webhooks+browser_extension",
        "square": "square_webhooks+browser_extension",
        "paypal": "paypal_webhooks+browser_extension",
        "quickbooks": "quickbooks_webhooks+browser_extension",
        "xero": "xero_webhooks+browser_extension",
        "plaid": "plaid_webhooks",
        "wise": "wise_webhooks+browser_extension",
        "mercury": "mercury_api_or_browser_extension",
        "brex": "brex_api_or_webhooks+browser_extension",
        "ramp": "ramp_api_or_webhooks+browser_extension",
        "mailchimp": "mailchimp_webhooks+browser_extension",
    }
    return mapping[provider_id]


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized())
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": "business_operations",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / "business_operations" / "dead_letters.jsonl"


def _clean_token(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_").replace(".", "_")
    return "".join(char for char in text if char.isalnum() or char in {"_", "/"})


def _clean_event_token(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return "".join(char for char in text if char.isalnum() or char in {"_", ".", ":", "/"})
