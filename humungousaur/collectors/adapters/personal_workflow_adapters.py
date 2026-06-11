from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from ..bridge import read_bridge_events
from ..models import CollectorEvent, CollectorProfile
from ..sources.business_operations import read_business_operations_events
from ..sources.google_workspace import read_google_workspace_events


NOTES_ACTIVITY_STIMULUS_TYPES = {
    "note_created",
    "note_edited",
    "note_deleted",
    "note_pinned",
    "note_shared",
    "checklist_item_completed",
}
BOOKMARK_HISTORY_ACTIVITY_STIMULUS_TYPES = {
    "bookmark_added",
    "bookmark_removed",
    "reading_list_added",
    "history_item_opened",
    "history_search_performed",
    "saved_tab_group_changed",
}
CONTACT_ACTIVITY_STIMULUS_TYPES = {
    "contact_opened",
    "contact_created",
    "contact_updated",
    "contact_shared",
    "address_copied",
    "phone_number_clicked",
}
COMMERCE_ACTIVITY_STIMULUS_TYPES = {
    "cart_updated",
    "checkout_started",
    "checkout_completed",
    "order_confirmation_seen",
    "order_created",
    "order_updated",
    "order_paid",
    "order_fulfilled",
    "order_cancelled",
    "customer_created",
    "customer_updated",
    "subscription_changed",
    "return_started",
    "refund_status_changed",
}
FINANCE_ACTIVITY_STIMULUS_TYPES = {
    "payment_prompt_shown",
    "payment_completed",
    "payment_failed",
    "wallet_opened",
    "bank_transfer_started",
    "invoice_opened",
    "invoice_created",
    "invoice_updated",
    "invoice_paid",
    "invoice_payment_failed",
    "customer_created",
    "customer_updated",
    "refund_created",
    "receipt_captured",
}
SOCIAL_FEED_ACTIVITY_STIMULUS_TYPES = {
    "feed_opened",
    "post_composed",
    "post_published",
    "comment_received",
    "follow_request_received",
    "saved_post_added",
    "social_notification_received",
}


def collect_notes_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_google_workspace_events(config, state, "notes_activity", NOTES_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "notes_activity", NOTES_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_bookmark_history_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "bookmark_history_activity", BOOKMARK_HISTORY_ACTIVITY_STIMULUS_TYPES, source="browser", max_events=20)


def collect_contact_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "contact_activity", CONTACT_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20)


def collect_commerce_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_business_operations_events(config, state, "commerce_activity", COMMERCE_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "commerce_activity", COMMERCE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_finance_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_business_operations_events(config, state, "finance_activity", FINANCE_ACTIVITY_STIMULUS_TYPES) + read_bridge_events(
        config, state, "finance_activity", FINANCE_ACTIVITY_STIMULUS_TYPES, source="activity", max_events=20
    )


def collect_social_feed_activity(config: AgentConfig, profile: CollectorProfile, state: dict[str, Any]) -> list[CollectorEvent]:
    del profile
    return read_bridge_events(config, state, "social_feed_activity", SOCIAL_FEED_ACTIVITY_STIMULUS_TYPES, source="channel_message", max_events=20)
