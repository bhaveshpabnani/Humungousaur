from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import asdict, dataclass
from typing import Any

from humungousaur.config import AgentConfig

from .meetings.catalog import meeting_mapping_specs, meeting_provider_entry


@dataclass(frozen=True, slots=True)
class ConnectorEventMapping:
    source_event: str
    collector: str
    stimulus_type: str
    text: str
    privacy_tier: str = "sensitive_metadata"

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ConnectorSourceManifest:
    provider_id: str
    display_name: str
    source_type: str
    auth_method: str
    collector_mappings: tuple[ConnectorEventMapping, ...]
    poller_supported: bool = True
    webhook_supported: bool = False
    requires_connector: bool = True
    official_docs: tuple[str, ...] = ()
    notes: str = ""

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["collector_mappings"] = [mapping.to_record() for mapping in self.collector_mappings]
        record["official_docs"] = list(self.official_docs)
        return record


def _chat_connector_mappings(display_name: str) -> tuple[ConnectorEventMapping, ...]:
    return (
        ConnectorEventMapping("message_received", "channel_activity", "message_received", f"{display_name} message metadata was received"),
        ConnectorEventMapping("mention_received", "channel_activity", "mention_received", f"{display_name} mention metadata was received"),
        ConnectorEventMapping("dm_received", "channel_activity", "dm_received", f"{display_name} direct message metadata was received"),
        ConnectorEventMapping("thread_reply_received", "channel_activity", "thread_reply_received", f"{display_name} thread reply metadata was received"),
        ConnectorEventMapping("reaction_added", "channel_activity", "reaction_added", f"{display_name} reaction metadata was received"),
        ConnectorEventMapping("message_sent", "chat_composition_activity", "chat_message_sent", f"{display_name} message was sent"),
        ConnectorEventMapping("message_edited", "chat_composition_activity", "chat_message_edited", f"{display_name} message was edited"),
        ConnectorEventMapping("message_deleted", "chat_composition_activity", "chat_message_deleted", f"{display_name} message was deleted"),
        ConnectorEventMapping("draft_started", "chat_composition_activity", "chat_draft_started", f"{display_name} draft was started"),
        ConnectorEventMapping("draft_updated", "chat_composition_activity", "chat_draft_updated", f"{display_name} draft was updated"),
        ConnectorEventMapping("attachment_added", "chat_composition_activity", "chat_attachment_added", f"{display_name} attachment metadata was added"),
        ConnectorEventMapping("attachment_removed", "chat_composition_activity", "chat_attachment_removed", f"{display_name} attachment metadata was removed"),
        ConnectorEventMapping("thread_opened", "chat_thread_activity", "thread_opened", f"{display_name} thread was opened"),
        ConnectorEventMapping("thread_reply_started", "chat_thread_activity", "thread_reply_started", f"{display_name} thread reply draft was started"),
        ConnectorEventMapping("thread_reply_sent", "chat_thread_activity", "thread_reply_sent", f"{display_name} thread reply was sent"),
        ConnectorEventMapping("thread_resolved", "chat_thread_activity", "thread_resolved", f"{display_name} thread was resolved"),
        ConnectorEventMapping("thread_unread_changed", "chat_thread_activity", "thread_unread_changed", f"{display_name} thread unread state changed"),
        ConnectorEventMapping("workspace_switched", "chat_channel_navigation_activity", "chat_workspace_switched", f"{display_name} workspace was switched"),
        ConnectorEventMapping("channel_opened", "chat_channel_navigation_activity", "chat_channel_opened", f"{display_name} channel was opened"),
        ConnectorEventMapping("channel_joined", "chat_channel_navigation_activity", "chat_channel_joined", f"{display_name} channel was joined"),
        ConnectorEventMapping("channel_left", "chat_channel_navigation_activity", "chat_channel_left", f"{display_name} channel was left"),
        ConnectorEventMapping("channel_muted", "chat_channel_navigation_activity", "chat_channel_muted", f"{display_name} channel was muted"),
        ConnectorEventMapping("channel_pinned", "chat_channel_navigation_activity", "chat_channel_pinned", f"{display_name} channel was pinned"),
        ConnectorEventMapping("channel_search_performed", "chat_channel_navigation_activity", "chat_channel_search_performed", f"{display_name} channel search was performed"),
        ConnectorEventMapping("saved_item_opened", "chat_channel_navigation_activity", "chat_saved_item_opened", f"{display_name} saved item was opened"),
        ConnectorEventMapping("presence_changed", "chat_presence_activity", "presence_changed", f"{display_name} presence changed"),
        ConnectorEventMapping("status_changed", "chat_presence_activity", "chat_status_changed", f"{display_name} status changed"),
        ConnectorEventMapping("status_cleared", "chat_presence_activity", "chat_status_cleared", f"{display_name} status was cleared"),
        ConnectorEventMapping("dnd_scheduled", "chat_presence_activity", "do_not_disturb_scheduled", f"{display_name} DND was scheduled"),
        ConnectorEventMapping("dnd_enabled", "chat_presence_activity", "do_not_disturb_enabled", f"{display_name} DND was enabled"),
        ConnectorEventMapping("dnd_disabled", "chat_presence_activity", "do_not_disturb_disabled", f"{display_name} DND was disabled"),
        ConnectorEventMapping("notification_preference_changed", "chat_presence_activity", "notification_preference_changed", f"{display_name} notification preference changed"),
    )


def _mail_connector_mappings(prefix: str, display_name: str) -> tuple[ConnectorEventMapping, ...]:
    return (
        ConnectorEventMapping(f"{prefix}_message_received", "mail_activity", "email_received", f"{display_name} message metadata was received"),
        ConnectorEventMapping(f"{prefix}_important_message_received", "mail_activity", "important_email_received", f"Important {display_name} message metadata was received"),
        ConnectorEventMapping(f"{prefix}_message_opened", "mail_activity", "email_opened", f"{display_name} message was opened"),
        ConnectorEventMapping(f"{prefix}_draft_started", "mail_composition_activity", "email_draft_started", f"{display_name} draft was started"),
        ConnectorEventMapping(f"{prefix}_draft_updated", "mail_composition_activity", "email_draft_updated", f"{display_name} draft was updated"),
        ConnectorEventMapping(f"{prefix}_reply_started", "mail_composition_activity", "email_reply_started", f"{display_name} reply was started"),
        ConnectorEventMapping(f"{prefix}_forward_started", "mail_composition_activity", "email_forward_started", f"{display_name} forward was started"),
        ConnectorEventMapping(f"{prefix}_message_sent", "mail_composition_activity", "email_sent", f"{display_name} message was sent"),
        ConnectorEventMapping(f"{prefix}_send_scheduled", "mail_composition_activity", "email_send_scheduled", f"{display_name} send was scheduled"),
        ConnectorEventMapping(f"{prefix}_send_cancelled", "mail_composition_activity", "email_send_cancelled", f"{display_name} scheduled send was cancelled"),
        ConnectorEventMapping(f"{prefix}_attachment_added", "mail_composition_activity", "email_attachment_added", f"{display_name} attachment metadata was added"),
        ConnectorEventMapping(f"{prefix}_attachment_removed", "mail_composition_activity", "email_attachment_removed", f"{display_name} attachment metadata was removed"),
        ConnectorEventMapping(f"{prefix}_message_archived", "mail_organization_activity", "email_archived", f"{display_name} message was archived"),
        ConnectorEventMapping(f"{prefix}_message_deleted", "mail_organization_activity", "email_deleted", f"{display_name} message was deleted"),
        ConnectorEventMapping(f"{prefix}_message_moved", "mail_organization_activity", "email_moved", f"{display_name} message was moved"),
        ConnectorEventMapping(f"{prefix}_message_labeled", "mail_organization_activity", "email_labeled", f"{display_name} message label changed"),
        ConnectorEventMapping(f"{prefix}_message_flagged", "mail_organization_activity", "email_flagged", f"{display_name} message was flagged"),
        ConnectorEventMapping(f"{prefix}_unread_marked", "mail_organization_activity", "email_unread_marked", f"{display_name} unread state changed"),
        ConnectorEventMapping(f"{prefix}_search_performed", "mail_organization_activity", "email_search_performed", f"{display_name} search was performed"),
        ConnectorEventMapping(f"{prefix}_filter_changed", "mail_organization_activity", "mailbox_filter_changed", f"{display_name} mailbox filter changed"),
    )


def _crm_connector_mappings(prefix: str, display_name: str) -> tuple[ConnectorEventMapping, ...]:
    return (
        ConnectorEventMapping(f"{prefix}_record_viewed", "crm_activity", "record_opened", f"{display_name} CRM record was viewed"),
        ConnectorEventMapping(f"{prefix}_record_updated", "crm_activity", "record_updated", f"{display_name} CRM record was updated"),
        ConnectorEventMapping(f"{prefix}_lead_created", "crm_activity", "lead_created", f"{display_name} lead was created"),
        ConnectorEventMapping(f"{prefix}_deal_stage_changed", "crm_activity", "deal_stage_changed", f"{display_name} deal stage changed"),
        ConnectorEventMapping(f"{prefix}_customer_note_added", "crm_activity", "customer_note_added", f"{display_name} customer note metadata was added"),
        ConnectorEventMapping(f"{prefix}_followup_scheduled", "crm_activity", "followup_scheduled", f"{display_name} follow-up was scheduled"),
    )


def _support_connector_mappings(prefix: str, display_name: str) -> tuple[ConnectorEventMapping, ...]:
    return (
        ConnectorEventMapping(f"{prefix}_ticket_opened", "support_desk_activity", "ticket_opened", f"{display_name} ticket was opened"),
        ConnectorEventMapping(f"{prefix}_ticket_assigned", "support_desk_activity", "ticket_assigned", f"{display_name} ticket was assigned"),
        ConnectorEventMapping(f"{prefix}_ticket_updated", "support_desk_activity", "ticket_updated", f"{display_name} ticket was updated"),
        ConnectorEventMapping(f"{prefix}_ticket_replied", "support_desk_activity", "ticket_replied", f"{display_name} ticket received a reply"),
        ConnectorEventMapping(f"{prefix}_ticket_resolved", "support_desk_activity", "ticket_resolved", f"{display_name} ticket was resolved"),
        ConnectorEventMapping(f"{prefix}_ticket_escalated", "support_desk_activity", "ticket_escalated", f"{display_name} ticket was escalated"),
        ConnectorEventMapping(f"{prefix}_sla_breach_warning", "support_desk_activity", "sla_breach_warning", f"{display_name} SLA breach warning was observed"),
    )


def _finance_connector_mappings(prefix: str, display_name: str) -> tuple[ConnectorEventMapping, ...]:
    return (
        ConnectorEventMapping(f"{prefix}_payment_completed", "finance_activity", "payment_completed", f"{display_name} payment completed"),
        ConnectorEventMapping(f"{prefix}_payment_failed", "finance_activity", "payment_failed", f"{display_name} payment failed"),
        ConnectorEventMapping(f"{prefix}_invoice_created", "finance_activity", "invoice_created", f"{display_name} invoice was created"),
        ConnectorEventMapping(f"{prefix}_invoice_updated", "finance_activity", "invoice_updated", f"{display_name} invoice was updated"),
        ConnectorEventMapping(f"{prefix}_invoice_paid", "finance_activity", "invoice_paid", f"{display_name} invoice was paid"),
        ConnectorEventMapping(f"{prefix}_invoice_payment_failed", "finance_activity", "invoice_payment_failed", f"{display_name} invoice payment failed"),
        ConnectorEventMapping(f"{prefix}_customer_created", "finance_activity", "customer_created", f"{display_name} customer record was created"),
        ConnectorEventMapping(f"{prefix}_customer_updated", "finance_activity", "customer_updated", f"{display_name} customer record was updated"),
        ConnectorEventMapping(f"{prefix}_refund_created", "finance_activity", "refund_created", f"{display_name} refund metadata was created"),
    )


def _commerce_connector_mappings(prefix: str, display_name: str) -> tuple[ConnectorEventMapping, ...]:
    return (
        ConnectorEventMapping(f"{prefix}_order_created", "commerce_activity", "order_created", f"{display_name} order was created"),
        ConnectorEventMapping(f"{prefix}_order_updated", "commerce_activity", "order_updated", f"{display_name} order was updated"),
        ConnectorEventMapping(f"{prefix}_order_paid", "commerce_activity", "order_paid", f"{display_name} order was paid"),
        ConnectorEventMapping(f"{prefix}_order_fulfilled", "commerce_activity", "order_fulfilled", f"{display_name} order was fulfilled"),
        ConnectorEventMapping(f"{prefix}_order_cancelled", "commerce_activity", "order_cancelled", f"{display_name} order was cancelled"),
        ConnectorEventMapping(f"{prefix}_customer_created", "commerce_activity", "customer_created", f"{display_name} customer was created"),
        ConnectorEventMapping(f"{prefix}_customer_updated", "commerce_activity", "customer_updated", f"{display_name} customer was updated"),
        ConnectorEventMapping(f"{prefix}_subscription_changed", "commerce_activity", "subscription_changed", f"{display_name} subscription changed"),
        ConnectorEventMapping(f"{prefix}_refund_status_changed", "commerce_activity", "refund_status_changed", f"{display_name} refund status changed"),
    )


def _analytics_connector_mappings(prefix: str, display_name: str) -> tuple[ConnectorEventMapping, ...]:
    return (
        ConnectorEventMapping(f"{prefix}_dashboard_viewed", "analytics_activity", "dashboard_opened", f"{display_name} dashboard was viewed"),
        ConnectorEventMapping(f"{prefix}_report_exported", "analytics_activity", "report_exported", f"{display_name} report was exported"),
    )


def _meeting_event_mappings(provider_id: str) -> tuple[ConnectorEventMapping, ...]:
    return tuple(
        ConnectorEventMapping(spec.source_event, spec.collector, spec.stimulus_type, spec.text)
        for spec in meeting_mapping_specs(provider_id)
    )


def _meeting_source_manifest(provider_id: str) -> ConnectorSourceManifest:
    entry = meeting_provider_entry(provider_id)
    return ConnectorSourceManifest(
        provider_id=entry.provider_id,
        display_name=entry.display_name,
        source_type=entry.source_type,
        auth_method="oauth2_authorization_code" if provider_id != "discord" else "bot_token_or_local_bridge",
        collector_mappings=_meeting_event_mappings(provider_id),
        poller_supported=entry.poller_supported,
        webhook_supported=entry.webhook_supported,
        notes=entry.notes,
    )


_TASK_SOURCE_EVENTS = (
    ("task_created", "task_manager_activity", "task_created", "task was created"),
    ("task_updated", "task_manager_activity", "task_updated", "task metadata changed"),
    ("task_completed", "task_manager_activity", "task_completed", "task was completed"),
    ("task_reopened", "task_manager_activity", "task_reopened", "task was reopened"),
    ("task_assigned", "task_manager_activity", "task_assigned", "task was assigned"),
    ("task_moved", "task_manager_activity", "task_moved", "task was moved"),
    ("task_priority_changed", "task_manager_activity", "task_priority_changed", "task priority changed"),
    ("task_due_date_changed", "task_manager_activity", "task_due_date_changed", "task due date changed"),
    ("task_comment_added", "task_manager_activity", "task_comment_added", "task received a comment"),
    ("project_opened", "task_manager_activity", "project_opened", "project was opened"),
    ("project_changed", "task_manager_activity", "project_changed", "project metadata changed"),
)

_ISSUE_SOURCE_EVENTS = (
    ("issue_created", "issue_tracker_activity", "issue_created", "issue was created"),
    ("issue_assigned", "issue_tracker_activity", "issue_assigned", "issue was assigned"),
    ("issue_status_changed", "issue_tracker_activity", "issue_status_changed", "issue status changed"),
    ("issue_comment_received", "issue_tracker_activity", "issue_comment_received", "issue received a comment"),
    ("issue_blocker_added", "issue_tracker_activity", "issue_blocker_added", "issue blocker changed"),
    ("issue_moved", "issue_tracker_activity", "issue_moved", "issue was moved"),
    ("issue_priority_changed", "issue_tracker_activity", "issue_priority_changed", "issue priority changed"),
    ("issue_due_date_changed", "issue_tracker_activity", "issue_due_date_changed", "issue due date changed"),
    ("sprint_started", "issue_tracker_activity", "sprint_started", "sprint started"),
    ("sprint_changed", "issue_tracker_activity", "sprint_changed", "sprint changed"),
    ("project_opened", "issue_tracker_activity", "project_opened", "project was opened"),
    ("project_changed", "issue_tracker_activity", "project_changed", "project metadata changed"),
)


def _prefixed_mappings(provider_id: str, display_name: str, events: tuple[tuple[str, str, str, str], ...]) -> tuple[ConnectorEventMapping, ...]:
    return tuple(
        ConnectorEventMapping(f"{provider_id}_{source_event}", collector, stimulus_type, f"{display_name} {text}")
        for source_event, collector, stimulus_type, text in events
    )


def _planning_source_manifest(
    provider_id: str,
    display_name: str,
    *,
    issue_tracker: bool,
    notes: str,
) -> ConnectorSourceManifest:
    return ConnectorSourceManifest(
        provider_id=provider_id,
        display_name=display_name,
        source_type="saas_webhook_or_browser_ingress",
        auth_method="connector_profile_or_api_key",
        collector_mappings=_prefixed_mappings(provider_id, display_name, _ISSUE_SOURCE_EVENTS if issue_tracker else _TASK_SOURCE_EVENTS),
        poller_supported=False,
        webhook_supported=True,
        notes=notes,
    )


_NOTION_KNOWLEDGE_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("notion_page_created", "knowledge_base_activity", "page_created", "Notion page was created"),
    ConnectorEventMapping("notion_page_updated", "knowledge_base_activity", "page_edited", "Notion page was updated"),
    ConnectorEventMapping("notion_database_changed", "knowledge_base_activity", "database_changed", "Notion database metadata changed"),
    ConnectorEventMapping("notion_task_completed", "task_manager_activity", "task_completed", "Notion task was completed"),
    ConnectorEventMapping("notion_comment_added", "knowledge_base_activity", "page_commented", "Notion page received a comment"),
    ConnectorEventMapping("notion_link_created", "knowledge_base_activity", "link_created", "Notion page link or mention was created"),
    ConnectorEventMapping("notion_workspace_opened", "knowledge_base_activity", "workspace_opened", "Notion workspace was opened"),
)

_CONFLUENCE_KNOWLEDGE_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("confluence_page_created", "knowledge_base_activity", "page_created", "Confluence page was created"),
    ConnectorEventMapping("confluence_page_updated", "knowledge_base_activity", "page_edited", "Confluence page was updated"),
    ConnectorEventMapping("confluence_database_changed", "knowledge_base_activity", "database_changed", "Confluence database metadata changed"),
    ConnectorEventMapping("confluence_comment_added", "knowledge_base_activity", "page_commented", "Confluence page received a comment"),
    ConnectorEventMapping("confluence_link_created", "knowledge_base_activity", "link_created", "Confluence page link was created"),
    ConnectorEventMapping("confluence_workspace_opened", "knowledge_base_activity", "workspace_opened", "Confluence space or workspace was opened"),
)

_CODA_KNOWLEDGE_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("coda_page_created", "knowledge_base_activity", "page_created", "Coda page was created"),
    ConnectorEventMapping("coda_page_updated", "knowledge_base_activity", "page_edited", "Coda page was updated"),
    ConnectorEventMapping("coda_table_changed", "knowledge_base_activity", "table_changed", "Coda table metadata changed"),
    ConnectorEventMapping("coda_task_completed", "task_manager_activity", "task_completed", "Coda task was completed"),
    ConnectorEventMapping("coda_comment_added", "knowledge_base_activity", "page_commented", "Coda page received a comment"),
    ConnectorEventMapping("coda_link_created", "knowledge_base_activity", "link_created", "Coda link or relation was created"),
    ConnectorEventMapping("coda_workspace_opened", "knowledge_base_activity", "workspace_opened", "Coda doc or workspace was opened"),
)

_OBSIDIAN_KNOWLEDGE_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("obsidian_note_created", "notes_activity", "note_created", "Obsidian note was created"),
    ConnectorEventMapping("obsidian_note_updated", "notes_activity", "note_edited", "Obsidian note was updated"),
    ConnectorEventMapping("obsidian_task_completed", "task_manager_activity", "task_completed", "Obsidian task was completed"),
    ConnectorEventMapping("obsidian_link_created", "knowledge_base_activity", "link_created", "Obsidian wiki link was created"),
    ConnectorEventMapping("obsidian_backlink_created", "knowledge_base_activity", "backlink_created", "Obsidian backlink was created"),
    ConnectorEventMapping("obsidian_vault_opened", "knowledge_base_activity", "vault_opened", "Obsidian vault was opened"),
)

_EVERNOTE_KNOWLEDGE_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("evernote_note_created", "notes_activity", "note_created", "Evernote note was created"),
    ConnectorEventMapping("evernote_note_updated", "notes_activity", "note_edited", "Evernote note was updated"),
    ConnectorEventMapping("evernote_task_completed", "task_manager_activity", "task_completed", "Evernote task was completed"),
    ConnectorEventMapping("evernote_comment_added", "knowledge_base_activity", "page_commented", "Evernote note received a comment"),
    ConnectorEventMapping("evernote_link_created", "knowledge_base_activity", "link_created", "Evernote note link was created"),
    ConnectorEventMapping("evernote_workspace_opened", "knowledge_base_activity", "workspace_opened", "Evernote workspace was opened"),
)

_APPLE_NOTES_KNOWLEDGE_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("apple_notes_note_created", "notes_activity", "note_created", "Apple Notes note was created"),
    ConnectorEventMapping("apple_notes_note_updated", "notes_activity", "note_edited", "Apple Notes note was updated"),
    ConnectorEventMapping("apple_notes_task_completed", "notes_activity", "checklist_item_completed", "Apple Notes checklist item was completed"),
    ConnectorEventMapping("apple_notes_link_created", "knowledge_base_activity", "link_created", "Apple Notes note link was created"),
    ConnectorEventMapping("apple_notes_workspace_opened", "knowledge_base_activity", "workspace_opened", "Apple Notes workspace was opened"),
)

_ONENOTE_KNOWLEDGE_MAPPINGS: tuple[ConnectorEventMapping, ...] = (
    ConnectorEventMapping("onenote_page_created", "knowledge_base_activity", "page_created", "OneNote page was created"),
    ConnectorEventMapping("onenote_page_updated", "knowledge_base_activity", "page_edited", "OneNote page was updated"),
    ConnectorEventMapping("onenote_section_changed", "knowledge_base_activity", "database_changed", "OneNote notebook section metadata changed"),
    ConnectorEventMapping("onenote_comment_added", "knowledge_base_activity", "page_commented", "OneNote page received a comment"),
    ConnectorEventMapping("onenote_link_created", "knowledge_base_activity", "link_created", "OneNote page link was created"),
    ConnectorEventMapping("onenote_workspace_opened", "knowledge_base_activity", "workspace_opened", "OneNote notebook was opened"),
)


from .cloud_files.registry import CLOUD_FILE_PROVIDER_IDS, CLOUD_FILE_SOURCE_MANIFESTS, run_cloud_file_source_tick
from .data_analytics.registry import DATA_ANALYTICS_PROVIDER_IDS, DATA_ANALYTICS_SOURCE_MANIFESTS
from .developer.registry import DEVELOPER_SOURCE_MANIFESTS
from .design.registry import DESIGN_PROVIDER_IDS, DESIGN_SOURCE_MANIFESTS
from .operations.registry import OPERATIONS_PROVIDER_IDS, OPERATIONS_SOURCE_MANIFESTS


CONNECTOR_SOURCE_MANIFESTS: tuple[ConnectorSourceManifest, ...] = (
    ConnectorSourceManifest(
        provider_id="google_workspace",
        display_name="Google Workspace",
        source_type="saas_api_poller_or_webhook",
        auth_method="oauth2_authorization_code",
        collector_mappings=(
            ConnectorEventMapping("drive_file_created", "document_composition_activity", "document_draft_started", "Google Drive file was created"),
            ConnectorEventMapping("drive_file_modified", "document_composition_activity", "document_edited", "Google Drive file was modified"),
            ConnectorEventMapping("drive_file_deleted", "cloud_sync_activity", "remote_file_changed", "Google Drive file was deleted"),
            ConnectorEventMapping("drive_file_shared", "document_export_publish_activity", "document_share_link_created", "Google Drive file sharing changed"),
            ConnectorEventMapping("drive_cloud_file_created", "cloud_sync_activity", "cloud_file_created", "Google Drive file was created"),
            ConnectorEventMapping("drive_cloud_folder_created", "cloud_sync_activity", "cloud_folder_created", "Google Drive folder was created"),
            ConnectorEventMapping("drive_cloud_file_renamed", "cloud_sync_activity", "cloud_file_renamed", "Google Drive file was renamed"),
            ConnectorEventMapping("drive_cloud_folder_renamed", "cloud_sync_activity", "cloud_folder_renamed", "Google Drive folder was renamed"),
            ConnectorEventMapping("drive_cloud_file_moved", "cloud_sync_activity", "cloud_file_moved", "Google Drive file was moved"),
            ConnectorEventMapping("drive_cloud_folder_moved", "cloud_sync_activity", "cloud_folder_moved", "Google Drive folder was moved"),
            ConnectorEventMapping("drive_cloud_file_deleted", "cloud_sync_activity", "cloud_file_deleted", "Google Drive file was deleted"),
            ConnectorEventMapping("drive_cloud_folder_deleted", "cloud_sync_activity", "cloud_folder_deleted", "Google Drive folder was deleted"),
            ConnectorEventMapping("drive_cloud_file_shared", "cloud_sync_activity", "cloud_file_shared", "Google Drive file sharing changed"),
            ConnectorEventMapping("drive_cloud_permission_changed", "cloud_sync_activity", "cloud_permission_changed", "Google Drive permissions changed"),
            ConnectorEventMapping("drive_cloud_sync_failed", "cloud_sync_activity", "sync_failed", "Google Drive sync error was detected"),
            ConnectorEventMapping("drive_cloud_sync_conflict_detected", "cloud_sync_activity", "sync_conflict_detected", "Google Drive sync conflict was detected"),
            ConnectorEventMapping("drive_cloud_file_restored", "cloud_sync_activity", "cloud_file_restored", "Google Drive file was restored"),
            ConnectorEventMapping("drive_cloud_file_version_event", "cloud_sync_activity", "cloud_file_version_event", "Google Drive version event occurred"),
            ConnectorEventMapping("docs_document_draft_started", "document_composition_activity", "document_draft_started", "Google Docs draft was started"),
            ConnectorEventMapping("docs_document_edited", "document_composition_activity", "document_edited", "Google Docs document was edited"),
            ConnectorEventMapping("docs_document_saved", "document_composition_activity", "document_saved", "Google Docs document was saved"),
            ConnectorEventMapping("docs_comment_added", "document_review_activity", "document_comment_added", "Google Docs comment was added"),
            ConnectorEventMapping("docs_suggestion_received", "document_review_activity", "document_suggestion_received", "Google Docs suggestion was received"),
            ConnectorEventMapping("docs_document_exported", "document_export_publish_activity", "document_export_completed", "Google Docs export completed"),
            ConnectorEventMapping("docs_document_shared", "document_export_publish_activity", "document_share_link_created", "Google Docs document was shared"),
            ConnectorEventMapping("docs_permissions_changed", "document_export_publish_activity", "document_permissions_changed", "Google Docs permissions changed"),
            *_mail_connector_mappings("gmail", "Gmail"),
            ConnectorEventMapping("calendar_meeting_starting", "calendar_activity", "meeting_starting", "Google Calendar meeting is starting"),
            ConnectorEventMapping("calendar_meeting_started", "calendar_activity", "meeting_started", "Google Calendar meeting started"),
            ConnectorEventMapping("calendar_meeting_ended", "calendar_activity", "meeting_ended", "Google Calendar meeting ended"),
            ConnectorEventMapping("calendar_event_created", "calendar_scheduling_activity", "calendar_event_created", "Google Calendar event was created"),
            ConnectorEventMapping("calendar_event_updated", "calendar_scheduling_activity", "calendar_event_updated", "Google Calendar event was updated"),
            ConnectorEventMapping("calendar_event_deleted", "calendar_scheduling_activity", "calendar_event_deleted", "Google Calendar event was deleted"),
            ConnectorEventMapping("calendar_event_rescheduled", "calendar_scheduling_activity", "calendar_event_rescheduled", "Google Calendar event was rescheduled"),
            ConnectorEventMapping("calendar_invite_received", "calendar_scheduling_activity", "calendar_invite_received", "Google Calendar invite was received"),
            ConnectorEventMapping("calendar_invite_accepted", "calendar_scheduling_activity", "calendar_invite_accepted", "Google Calendar invite was accepted"),
            ConnectorEventMapping("calendar_invite_declined", "calendar_scheduling_activity", "calendar_invite_declined", "Google Calendar invite was declined"),
            ConnectorEventMapping("calendar_availability_checked", "calendar_scheduling_activity", "calendar_availability_checked", "Google Calendar availability was checked"),
            ConnectorEventMapping("sheets_spreadsheet_opened", "spreadsheet_activity", "workbook_opened", "Google Sheets spreadsheet was opened"),
            ConnectorEventMapping("sheets_sheet_created", "spreadsheet_editing_activity", "sheet_created", "Google Sheets sheet was created"),
            ConnectorEventMapping("sheets_range_edited", "spreadsheet_editing_activity", "cell_range_edited", "Google Sheets range was edited"),
            ConnectorEventMapping("sheets_row_inserted", "spreadsheet_editing_activity", "row_inserted", "Google Sheets row was inserted"),
            ConnectorEventMapping("sheets_formula_entered", "spreadsheet_formula_activity", "formula_entered", "Google Sheets formula was entered"),
            ConnectorEventMapping("sheets_formula_error", "spreadsheet_formula_activity", "formula_error_detected", "Google Sheets formula error was detected"),
            ConnectorEventMapping("sheets_filter_applied", "spreadsheet_data_analysis_activity", "filter_applied", "Google Sheets filter was applied"),
            ConnectorEventMapping("sheets_chart_created", "spreadsheet_data_analysis_activity", "chart_created", "Google Sheets chart was created"),
            ConnectorEventMapping("sheets_csv_imported", "spreadsheet_import_export_activity", "csv_imported", "Google Sheets CSV import completed"),
            ConnectorEventMapping("sheets_workbook_exported", "spreadsheet_import_export_activity", "workbook_exported", "Google Sheets workbook was exported"),
            ConnectorEventMapping("sheets_sheet_shared", "spreadsheet_import_export_activity", "sheet_shared", "Google Sheets spreadsheet was shared"),
            ConnectorEventMapping("sheets_permissions_changed", "spreadsheet_import_export_activity", "permissions_changed", "Google Sheets permissions changed"),
            ConnectorEventMapping("slides_deck_opened", "presentation_activity", "deck_opened", "Google Slides deck was opened"),
            ConnectorEventMapping("slides_slide_created", "presentation_authoring_activity", "slide_created", "Google Slides slide was created"),
            ConnectorEventMapping("slides_slide_edited", "presentation_authoring_activity", "slide_edited", "Google Slides slide was edited"),
            ConnectorEventMapping("slides_slideshow_started", "presentation_delivery_activity", "slideshow_started", "Google Slides slideshow started"),
            ConnectorEventMapping("slides_slideshow_ended", "presentation_delivery_activity", "slideshow_ended", "Google Slides slideshow ended"),
            ConnectorEventMapping("slides_deck_exported", "presentation_export_activity", "deck_exported", "Google Slides deck was exported"),
            ConnectorEventMapping("slides_deck_shared", "presentation_export_activity", "deck_shared", "Google Slides deck was shared"),
            ConnectorEventMapping("slides_permissions_changed", "presentation_export_activity", "deck_permissions_changed", "Google Slides deck permissions changed"),
            *_meeting_event_mappings("google_workspace"),
            ConnectorEventMapping("tasks_task_created", "task_manager_activity", "task_created", "Google Tasks task was created"),
            ConnectorEventMapping("tasks_task_updated", "task_manager_activity", "task_updated", "Google Tasks task was updated"),
            ConnectorEventMapping("tasks_task_completed", "task_manager_activity", "task_completed", "Google Tasks task was completed"),
            ConnectorEventMapping("tasks_task_due_date_changed", "task_manager_activity", "task_due_date_changed", "Google Tasks due date changed"),
            ConnectorEventMapping("keep_note_created", "notes_activity", "note_created", "Google Keep note was created"),
            ConnectorEventMapping("keep_note_edited", "notes_activity", "note_edited", "Google Keep note was edited"),
            ConnectorEventMapping("keep_note_deleted", "notes_activity", "note_deleted", "Google Keep note was deleted"),
            ConnectorEventMapping("keep_note_shared", "notes_activity", "note_shared", "Google Keep note was shared"),
            ConnectorEventMapping("keep_checklist_item_completed", "notes_activity", "checklist_item_completed", "Google Keep checklist item completed"),
            ConnectorEventMapping("chat_message_received", "channel_activity", "message_received", "Google Chat message metadata was received"),
            ConnectorEventMapping("chat_message_sent", "channel_activity", "message_sent", "Google Chat message was sent"),
            ConnectorEventMapping("chat_mention_received", "channel_activity", "mention_received", "Google Chat mention metadata was received"),
            ConnectorEventMapping("chat_thread_reply_received", "channel_activity", "thread_reply_received", "Google Chat thread reply metadata was received"),
            ConnectorEventMapping("chat_reaction_added", "channel_activity", "reaction_added", "Google Chat reaction metadata was received"),
            ConnectorEventMapping("chat_space_opened", "chat_channel_navigation_activity", "chat_channel_opened", "Google Chat space was opened"),
            ConnectorEventMapping("chat_presence_changed", "chat_presence_activity", "presence_changed", "Google Chat presence changed"),
            ConnectorEventMapping("contacts_contact_opened", "contact_activity", "contact_opened", "Google Contacts contact was opened"),
            ConnectorEventMapping("contacts_contact_created", "contact_activity", "contact_created", "Google Contacts contact was created"),
            ConnectorEventMapping("contacts_contact_updated", "contact_activity", "contact_updated", "Google Contacts contact was updated"),
            ConnectorEventMapping("contacts_contact_shared", "contact_activity", "contact_shared", "Google Contacts contact was shared"),
            ConnectorEventMapping("contacts_address_copied", "contact_activity", "address_copied", "Google Contacts address was copied"),
            ConnectorEventMapping("contacts_phone_number_clicked", "contact_activity", "phone_number_clicked", "Google Contacts phone number was clicked"),
        ),
        webhook_supported=True,
        notes="Use Google Workspace push notifications where available; poll Drive/Gmail/Calendar deltas otherwise.",
    ),
    ConnectorSourceManifest(
        provider_id="microsoft_365",
        display_name="Microsoft 365",
        source_type="saas_api_poller_or_webhook",
        auth_method="oauth2_authorization_code",
        collector_mappings=(
            ConnectorEventMapping("onedrive_file_modified", "document_composition_activity", "document_edited", "OneDrive file was modified"),
            ConnectorEventMapping("sharepoint_file_shared", "document_export_publish_activity", "document_share_link_created", "SharePoint file sharing changed"),
            ConnectorEventMapping("onedrive_file_created", "cloud_sync_activity", "cloud_file_created", "OneDrive file was created"),
            ConnectorEventMapping("onedrive_folder_created", "cloud_sync_activity", "cloud_folder_created", "OneDrive folder was created"),
            ConnectorEventMapping("onedrive_file_renamed", "cloud_sync_activity", "cloud_file_renamed", "OneDrive file was renamed"),
            ConnectorEventMapping("onedrive_folder_renamed", "cloud_sync_activity", "cloud_folder_renamed", "OneDrive folder was renamed"),
            ConnectorEventMapping("onedrive_file_moved", "cloud_sync_activity", "cloud_file_moved", "OneDrive file was moved"),
            ConnectorEventMapping("onedrive_folder_moved", "cloud_sync_activity", "cloud_folder_moved", "OneDrive folder was moved"),
            ConnectorEventMapping("onedrive_file_deleted", "cloud_sync_activity", "cloud_file_deleted", "OneDrive file was deleted"),
            ConnectorEventMapping("onedrive_folder_deleted", "cloud_sync_activity", "cloud_folder_deleted", "OneDrive folder was deleted"),
            ConnectorEventMapping("onedrive_file_shared", "cloud_sync_activity", "cloud_file_shared", "OneDrive file sharing changed"),
            ConnectorEventMapping("onedrive_permissions_changed", "cloud_sync_activity", "cloud_permission_changed", "OneDrive permissions changed"),
            ConnectorEventMapping("onedrive_sync_failed", "cloud_sync_activity", "sync_failed", "OneDrive sync error was detected"),
            ConnectorEventMapping("onedrive_sync_conflict_detected", "cloud_sync_activity", "sync_conflict_detected", "OneDrive sync conflict was detected"),
            ConnectorEventMapping("onedrive_file_restored", "cloud_sync_activity", "cloud_file_restored", "OneDrive file was restored"),
            ConnectorEventMapping("onedrive_file_version_event", "cloud_sync_activity", "cloud_file_version_event", "OneDrive version event occurred"),
            ConnectorEventMapping("sharepoint_file_created", "cloud_sync_activity", "cloud_file_created", "SharePoint file was created"),
            ConnectorEventMapping("sharepoint_folder_created", "cloud_sync_activity", "cloud_folder_created", "SharePoint folder was created"),
            ConnectorEventMapping("sharepoint_file_modified", "cloud_sync_activity", "remote_file_changed", "SharePoint file was modified"),
            ConnectorEventMapping("sharepoint_file_renamed", "cloud_sync_activity", "cloud_file_renamed", "SharePoint file was renamed"),
            ConnectorEventMapping("sharepoint_folder_renamed", "cloud_sync_activity", "cloud_folder_renamed", "SharePoint folder was renamed"),
            ConnectorEventMapping("sharepoint_file_moved", "cloud_sync_activity", "cloud_file_moved", "SharePoint file was moved"),
            ConnectorEventMapping("sharepoint_folder_moved", "cloud_sync_activity", "cloud_folder_moved", "SharePoint folder was moved"),
            ConnectorEventMapping("sharepoint_file_deleted", "cloud_sync_activity", "cloud_file_deleted", "SharePoint file was deleted"),
            ConnectorEventMapping("sharepoint_folder_deleted", "cloud_sync_activity", "cloud_folder_deleted", "SharePoint folder was deleted"),
            ConnectorEventMapping("sharepoint_permissions_changed", "cloud_sync_activity", "cloud_permission_changed", "SharePoint permissions changed"),
            ConnectorEventMapping("sharepoint_sync_failed", "cloud_sync_activity", "sync_failed", "SharePoint sync error was detected"),
            ConnectorEventMapping("sharepoint_sync_conflict_detected", "cloud_sync_activity", "sync_conflict_detected", "SharePoint sync conflict was detected"),
            ConnectorEventMapping("sharepoint_file_restored", "cloud_sync_activity", "cloud_file_restored", "SharePoint file was restored"),
            ConnectorEventMapping("sharepoint_file_version_event", "cloud_sync_activity", "cloud_file_version_event", "SharePoint version event occurred"),
            ConnectorEventMapping("word_document_draft_started", "document_composition_activity", "document_draft_started", "Word document draft was started"),
            ConnectorEventMapping("word_document_edited", "document_composition_activity", "document_edited", "Word document was edited"),
            ConnectorEventMapping("word_document_saved", "document_composition_activity", "document_saved", "Word document was saved"),
            ConnectorEventMapping("word_comment_added", "document_review_activity", "document_comment_added", "Word comment was added"),
            ConnectorEventMapping("word_suggestion_received", "document_review_activity", "document_suggestion_received", "Word suggestion was received"),
            ConnectorEventMapping("word_tracked_changes_enabled", "document_review_activity", "tracked_changes_enabled", "Word tracked changes were enabled"),
            ConnectorEventMapping("word_document_exported", "document_export_publish_activity", "document_export_completed", "Word document export completed"),
            ConnectorEventMapping("word_document_shared", "document_export_publish_activity", "document_share_link_created", "Word document was shared"),
            ConnectorEventMapping("word_permissions_changed", "document_export_publish_activity", "document_permissions_changed", "Word document permissions changed"),
            *_mail_connector_mappings("outlook", "Outlook"),
            ConnectorEventMapping("outlook_calendar_meeting_starting", "calendar_activity", "meeting_starting", "Outlook calendar meeting is starting"),
            ConnectorEventMapping("outlook_calendar_meeting_started", "calendar_activity", "meeting_started", "Outlook calendar meeting started"),
            ConnectorEventMapping("outlook_calendar_meeting_ended", "calendar_activity", "meeting_ended", "Outlook calendar meeting ended"),
            ConnectorEventMapping("outlook_calendar_event_created", "calendar_scheduling_activity", "calendar_event_created", "Outlook calendar event was created"),
            ConnectorEventMapping("outlook_calendar_event_updated", "calendar_scheduling_activity", "calendar_event_updated", "Outlook calendar event was updated"),
            ConnectorEventMapping("outlook_calendar_event_deleted", "calendar_scheduling_activity", "calendar_event_deleted", "Outlook calendar event was deleted"),
            ConnectorEventMapping("outlook_calendar_event_rescheduled", "calendar_scheduling_activity", "calendar_event_rescheduled", "Outlook calendar event was rescheduled"),
            ConnectorEventMapping("outlook_calendar_invite_received", "calendar_scheduling_activity", "calendar_invite_received", "Outlook calendar invite was received"),
            ConnectorEventMapping("outlook_calendar_invite_accepted", "calendar_scheduling_activity", "calendar_invite_accepted", "Outlook calendar invite was accepted"),
            ConnectorEventMapping("outlook_calendar_invite_declined", "calendar_scheduling_activity", "calendar_invite_declined", "Outlook calendar invite was declined"),
            ConnectorEventMapping("outlook_calendar_availability_checked", "calendar_scheduling_activity", "calendar_availability_checked", "Outlook calendar availability was checked"),
            ConnectorEventMapping("excel_workbook_opened", "spreadsheet_activity", "workbook_opened", "Excel workbook was opened"),
            ConnectorEventMapping("excel_range_edited", "spreadsheet_editing_activity", "cell_range_edited", "Excel range was edited"),
            ConnectorEventMapping("excel_sheet_created", "spreadsheet_editing_activity", "sheet_created", "Excel sheet was created"),
            ConnectorEventMapping("excel_row_inserted", "spreadsheet_editing_activity", "row_inserted", "Excel row was inserted"),
            ConnectorEventMapping("excel_formula_entered", "spreadsheet_formula_activity", "formula_entered", "Excel formula was entered"),
            ConnectorEventMapping("excel_formula_error", "spreadsheet_formula_activity", "formula_error_detected", "Excel formula error was detected"),
            ConnectorEventMapping("excel_filter_applied", "spreadsheet_data_analysis_activity", "filter_applied", "Excel filter was applied"),
            ConnectorEventMapping("excel_chart_created", "spreadsheet_data_analysis_activity", "chart_created", "Excel chart was created"),
            ConnectorEventMapping("excel_pivot_table_changed", "spreadsheet_data_analysis_activity", "pivot_table_changed", "Excel pivot table changed"),
            ConnectorEventMapping("excel_workbook_exported", "spreadsheet_import_export_activity", "workbook_exported", "Excel workbook was exported"),
            ConnectorEventMapping("excel_sheet_shared", "spreadsheet_import_export_activity", "sheet_shared", "Excel workbook was shared"),
            ConnectorEventMapping("excel_permissions_changed", "spreadsheet_import_export_activity", "permissions_changed", "Excel permissions changed"),
            ConnectorEventMapping("powerpoint_deck_opened", "presentation_activity", "deck_opened", "PowerPoint deck was opened"),
            ConnectorEventMapping("powerpoint_slide_created", "presentation_authoring_activity", "slide_created", "PowerPoint slide was created"),
            ConnectorEventMapping("powerpoint_slide_edited", "presentation_authoring_activity", "slide_edited", "PowerPoint slide was edited"),
            ConnectorEventMapping("powerpoint_slideshow_started", "presentation_delivery_activity", "slideshow_started", "PowerPoint slideshow started"),
            ConnectorEventMapping("powerpoint_slideshow_ended", "presentation_delivery_activity", "slideshow_ended", "PowerPoint slideshow ended"),
            ConnectorEventMapping("powerpoint_deck_exported", "presentation_export_activity", "deck_exported", "PowerPoint deck was exported"),
            ConnectorEventMapping("powerpoint_deck_shared", "presentation_export_activity", "deck_shared", "PowerPoint deck was shared"),
            ConnectorEventMapping("powerpoint_permissions_changed", "presentation_export_activity", "deck_permissions_changed", "PowerPoint deck permissions changed"),
            ConnectorEventMapping("teams_message_received", "channel_activity", "message_received", "Teams message metadata was received"),
            ConnectorEventMapping("teams_mention_received", "channel_activity", "mention_received", "Teams mention metadata was received"),
            ConnectorEventMapping("teams_thread_reply_received", "channel_activity", "thread_reply_received", "Teams thread reply metadata was received"),
            ConnectorEventMapping("teams_reaction_added", "channel_activity", "reaction_added", "Teams reaction metadata was received"),
            ConnectorEventMapping("teams_message_sent", "chat_composition_activity", "chat_message_sent", "Teams message was sent"),
            ConnectorEventMapping("teams_message_edited", "chat_composition_activity", "chat_message_edited", "Teams message was edited"),
            ConnectorEventMapping("teams_message_deleted", "chat_composition_activity", "chat_message_deleted", "Teams message was deleted"),
            ConnectorEventMapping("teams_draft_started", "chat_composition_activity", "chat_draft_started", "Teams draft was started"),
            ConnectorEventMapping("teams_thread_opened", "chat_thread_activity", "thread_opened", "Teams thread was opened"),
            ConnectorEventMapping("teams_thread_reply_sent", "chat_thread_activity", "thread_reply_sent", "Teams thread reply was sent"),
            ConnectorEventMapping("teams_thread_resolved", "chat_thread_activity", "thread_resolved", "Teams thread was resolved"),
            ConnectorEventMapping("teams_workspace_switched", "chat_channel_navigation_activity", "chat_workspace_switched", "Teams workspace was switched"),
            ConnectorEventMapping("teams_channel_opened", "chat_channel_navigation_activity", "chat_channel_opened", "Teams channel was opened"),
            ConnectorEventMapping("teams_presence_changed", "chat_presence_activity", "presence_changed", "Teams presence changed"),
            ConnectorEventMapping("teams_dnd_enabled", "chat_presence_activity", "do_not_disturb_enabled", "Teams DND was enabled"),
            ConnectorEventMapping("teams_dnd_disabled", "chat_presence_activity", "do_not_disturb_disabled", "Teams DND was disabled"),
            ConnectorEventMapping("teams_attachment_added", "chat_composition_activity", "chat_attachment_added", "Teams attachment metadata was added"),
            ConnectorEventMapping("onenote_note_created", "notes_activity", "note_created", "OneNote note was created"),
            ConnectorEventMapping("onenote_note_edited", "notes_activity", "note_edited", "OneNote note was edited"),
            ConnectorEventMapping("onenote_note_deleted", "notes_activity", "note_deleted", "OneNote note was deleted"),
            ConnectorEventMapping("onenote_note_shared", "notes_activity", "note_shared", "OneNote note was shared"),
            ConnectorEventMapping("onenote_checklist_item_completed", "notes_activity", "checklist_item_completed", "OneNote checklist item completed"),
            ConnectorEventMapping("todo_task_created", "task_manager_activity", "task_created", "Microsoft To Do task was created"),
            ConnectorEventMapping("todo_task_updated", "task_manager_activity", "task_updated", "Microsoft To Do task was updated"),
            ConnectorEventMapping("todo_task_completed", "task_manager_activity", "task_completed", "Microsoft To Do task was completed"),
            ConnectorEventMapping("todo_task_due_date_changed", "task_manager_activity", "task_due_date_changed", "Microsoft To Do due date changed"),
            ConnectorEventMapping("loop_component_created", "knowledge_base_activity", "page_created", "Loop component was created"),
            ConnectorEventMapping("loop_component_edited", "knowledge_base_activity", "page_edited", "Loop component was edited"),
            ConnectorEventMapping("loop_component_shared", "knowledge_base_activity", "page_shared", "Loop component was shared"),
            ConnectorEventMapping("loop_task_completed", "task_manager_activity", "task_completed", "Loop task was completed"),
            ConnectorEventMapping("loop_page_created", "knowledge_base_activity", "page_created", "Loop page was created"),
            ConnectorEventMapping("loop_page_edited", "knowledge_base_activity", "page_edited", "Loop page was edited"),
            *_meeting_event_mappings("microsoft_365"),
            *_ONENOTE_KNOWLEDGE_MAPPINGS,
        ),
        webhook_supported=True,
        notes="Use Microsoft Graph delta queries for files, mail, calendar, OneNote, and To Do; use Graph change notifications, Office add-ins, Teams app/browser ingress, and Loop web ingress for richer app workflow events.",
    ),
    ConnectorSourceManifest(
        provider_id="notion",
        display_name="Notion",
        source_type="saas_api_poller_or_webhook_or_browser_extension",
        auth_method="oauth2_authorization_code_or_internal_integration_token",
        collector_mappings=_NOTION_KNOWLEDGE_MAPPINGS,
        poller_supported=True,
        webhook_supported=True,
        notes="Use Notion webhooks for page/database events where available; browser/add-on ingress can emit workspace-open and link/backlink metadata.",
    ),
    ConnectorSourceManifest(
        provider_id="confluence",
        display_name="Confluence",
        source_type="saas_api_poller_or_webhook_or_browser_extension",
        auth_method="oauth2_authorization_code",
        collector_mappings=_CONFLUENCE_KNOWLEDGE_MAPPINGS,
        poller_supported=True,
        webhook_supported=True,
        notes="Use Atlassian Confluence REST APIs and webhooks for page/comment/database metadata; page bodies stay redacted.",
    ),
    ConnectorSourceManifest(
        provider_id="coda",
        display_name="Coda",
        source_type="saas_api_poller_or_pack_or_browser_extension",
        auth_method="api_token_or_oauth2",
        collector_mappings=_CODA_KNOWLEDGE_MAPPINGS,
        poller_supported=True,
        webhook_supported=True,
        notes="Use Coda docs/pages/tables/rows metadata and Pack/browser ingress; row values and page contents stay redacted.",
    ),
    ConnectorSourceManifest(
        provider_id="obsidian",
        display_name="Obsidian",
        source_type="local_vault_plugin_or_bridge",
        auth_method="local_plugin_permission",
        collector_mappings=_OBSIDIAN_KNOWLEDGE_MAPPINGS,
        poller_supported=False,
        webhook_supported=False,
        requires_connector=False,
        notes="Use an Obsidian plugin or local vault bridge for note, task, link, backlink, and vault-open metadata; paths and note text stay redacted.",
    ),
    ConnectorSourceManifest(
        provider_id="evernote",
        display_name="Evernote",
        source_type="saas_api_poller_or_webhook",
        auth_method="oauth2_authorization_code",
        collector_mappings=_EVERNOTE_KNOWLEDGE_MAPPINGS,
        poller_supported=True,
        webhook_supported=True,
        notes="Use Evernote note/task metadata from API polling or webhooks; note bodies and resource names stay redacted.",
    ),
    ConnectorSourceManifest(
        provider_id="apple_local",
        display_name="Apple Notes",
        source_type="local_app_bridge_or_automation",
        auth_method="local_app_permission",
        collector_mappings=_APPLE_NOTES_KNOWLEDGE_MAPPINGS,
        poller_supported=False,
        webhook_supported=False,
        requires_connector=False,
        notes="Use local Apple Notes automation or app bridge metadata; titles, account names, folders, links, and note contents stay redacted.",
    ),
    ConnectorSourceManifest(
        provider_id="slack",
        display_name="Slack",
        source_type="saas_webhook_or_socket_mode",
        auth_method="oauth2_authorization_code",
        collector_mappings=_chat_connector_mappings("Slack") + (
            ConnectorEventMapping("thread_replied", "chat_thread_activity", "thread_reply_sent", "Slack thread received a reply"),
            ConnectorEventMapping("file_shared", "chat_composition_activity", "chat_attachment_added", "Slack file attachment metadata was shared"),
        ),
        poller_supported=False,
        webhook_supported=True,
        notes="Events API or Socket Mode should feed redacted chat/channel metadata into channel collectors.",
    ),
    ConnectorSourceManifest(
        provider_id="msteams",
        display_name="Microsoft Teams",
        source_type="saas_webhook_or_graph_change_notification_or_browser_extension",
        auth_method="oauth2_authorization_code",
        collector_mappings=_chat_connector_mappings("Microsoft Teams"),
        poller_supported=False,
        webhook_supported=True,
        notes="Use Microsoft Graph Teams message change notifications or Teams app/bot events; browser/native app bridges can emit navigation, draft, presence, and DND metadata.",
    ),
    _meeting_source_manifest("zoom"),
    _meeting_source_manifest("webex"),
    ConnectorSourceManifest(
        provider_id="discord",
        display_name="Discord",
        source_type="gateway_or_browser_extension",
        auth_method="bot_token_or_oauth2",
        collector_mappings=_chat_connector_mappings("Discord") + _meeting_event_mappings("discord"),
        poller_supported=False,
        webhook_supported=True,
        notes="Discord Gateway dispatch events should feed message, thread, channel, presence, and voice-state metadata without raw message or transcript content.",
    ),
    ConnectorSourceManifest(
        provider_id="telegram",
        display_name="Telegram",
        source_type="bot_api_webhook_or_long_polling",
        auth_method="bot_token",
        collector_mappings=_chat_connector_mappings("Telegram"),
        poller_supported=True,
        webhook_supported=True,
        notes="Telegram Bot API updates should feed message, edit, channel post, attachment, and chat navigation metadata.",
    ),
    ConnectorSourceManifest(
        provider_id="whatsapp",
        display_name="WhatsApp",
        source_type="cloud_api_webhook_or_local_bridge",
        auth_method="business_cloud_api_token_or_pairing_bridge",
        collector_mappings=_chat_connector_mappings("WhatsApp"),
        poller_supported=False,
        webhook_supported=True,
        notes="WhatsApp Cloud API webhooks cover business messages and status updates; personal account collectors require a local paired bridge.",
    ),
    ConnectorSourceManifest(
        provider_id="signal",
        display_name="Signal",
        source_type="signal_cli_json_rpc_or_local_bridge",
        auth_method="signal_cli_pairing",
        collector_mappings=_chat_connector_mappings("Signal"),
        poller_supported=True,
        webhook_supported=False,
        notes="Signal collectors should use signal-cli JSON-RPC/daemon metadata and avoid raw message bodies or attachment filenames.",
    ),
    ConnectorSourceManifest(
        provider_id="linear",
        display_name="Linear",
        source_type="saas_webhook_or_browser_ingress",
        auth_method="oauth2_authorization_code",
        collector_mappings=_prefixed_mappings("linear", "Linear", _ISSUE_SOURCE_EVENTS) + (
            ConnectorEventMapping("issue_created", "issue_tracker_activity", "issue_created", "Linear issue was created"),
            ConnectorEventMapping("issue_assigned", "issue_tracker_activity", "issue_assigned", "Linear issue was assigned"),
            ConnectorEventMapping("issue_status_changed", "issue_tracker_activity", "issue_status_changed", "Linear issue status changed"),
            ConnectorEventMapping("issue_comment_received", "issue_tracker_activity", "issue_comment_received", "Linear issue received a comment"),
            ConnectorEventMapping("issue_blocker_added", "issue_tracker_activity", "issue_blocker_added", "Linear issue blocker changed"),
            ConnectorEventMapping("project_updated", "issue_tracker_activity", "project_changed", "Linear project metadata changed"),
        ),
        poller_supported=False,
        webhook_supported=True,
        notes="Linear webhooks should emit issue metadata and project/task changes with titles redacted by default.",
    ),
    _planning_source_manifest(
        "jira",
        "Jira",
        issue_tracker=True,
        notes="Jira webhooks should emit issue, sprint, board, and project navigation metadata with summaries and comments redacted.",
    ),
    _planning_source_manifest(
        "asana",
        "Asana",
        issue_tracker=False,
        notes="Asana webhooks should emit task, story, section, and project metadata with task names and comments redacted.",
    ),
    _planning_source_manifest(
        "trello",
        "Trello",
        issue_tracker=False,
        notes="Trello webhooks should emit card, list, board, and comment metadata with card names and comment bodies redacted.",
    ),
    _planning_source_manifest(
        "clickup",
        "ClickUp",
        issue_tracker=False,
        notes="ClickUp webhooks should emit task, list, sprint, priority, assignee, and comment metadata with names and comments redacted.",
    ),
    _planning_source_manifest(
        "monday",
        "Monday.com",
        issue_tracker=False,
        notes="Monday.com webhooks should emit item, board, column, status, priority, date, and update metadata with values redacted.",
    ),
    _planning_source_manifest(
        "todoist",
        "Todoist",
        issue_tracker=False,
        notes="Todoist webhooks or activity relays should emit task, project, comment, and due-date metadata with content redacted.",
    ),
    ConnectorSourceManifest(
        provider_id="github",
        display_name="GitHub",
        source_type="saas_api_poller_or_webhook",
        auth_method="oauth2_authorization_code",
        collector_mappings=(
            ConnectorEventMapping("pull_request_opened", "github_activity", "pr_opened", "GitHub pull request was opened"),
            ConnectorEventMapping("pull_request_merged", "github_activity", "merge_ready", "GitHub pull request was merged"),
            ConnectorEventMapping("review_requested", "github_activity", "pr_review_requested", "GitHub review was requested"),
            ConnectorEventMapping("ci_failed", "github_activity", "ci_failed", "GitHub CI failed"),
            ConnectorEventMapping("ci_passed", "github_activity", "ci_passed", "GitHub CI passed"),
            ConnectorEventMapping("pull_request_review_submitted", "code_hosting_activity", "review_submitted", "GitHub pull request review was submitted"),
            ConnectorEventMapping("branch_created", "code_hosting_activity", "branch_created", "GitHub branch was created"),
            ConnectorEventMapping("branch_deleted", "code_hosting_activity", "branch_deleted", "GitHub branch was deleted"),
            ConnectorEventMapping("commit_pushed", "code_hosting_activity", "commit_pushed", "GitHub commit was pushed"),
            ConnectorEventMapping("ci_started", "code_hosting_activity", "ci_started", "GitHub CI run started"),
            ConnectorEventMapping("ci_canceled", "code_hosting_activity", "ci_canceled", "GitHub CI run was canceled"),
            ConnectorEventMapping("issue_created", "issue_tracker_activity", "issue_created", "GitHub issue was created"),
            ConnectorEventMapping("issue_assigned", "github_activity", "issue_assigned", "GitHub issue was assigned"),
            ConnectorEventMapping("issue_status_changed", "issue_tracker_activity", "issue_status_changed", "GitHub issue status changed"),
            ConnectorEventMapping("issue_comment_received", "issue_tracker_activity", "issue_comment_received", "GitHub issue received a comment"),
            ConnectorEventMapping("comment_received", "github_activity", "comment_received", "GitHub comment metadata was received"),
        ),
        webhook_supported=True,
        official_docs=("https://docs.github.com/en/webhooks/webhook-events-and-payloads",),
        notes="GitHub webhooks and Actions polling should feed PR, issue, review, and CI metadata into developer collectors.",
    ),
    ConnectorSourceManifest(
        provider_id="salesforce",
        display_name="Salesforce",
        source_type="change_data_capture_platform_event_or_browser_extension",
        auth_method="oauth2_authorization_code",
        collector_mappings=_crm_connector_mappings("salesforce", "Salesforce") + _analytics_connector_mappings("salesforce", "Salesforce"),
        poller_supported=False,
        webhook_supported=True,
        notes="Use Salesforce Change Data Capture or Platform Events for record changes; browser/app ingress is required for record-view and dashboard-view metadata.",
    ),
    ConnectorSourceManifest(
        provider_id="hubspot",
        display_name="HubSpot",
        source_type="crm_webhook_or_browser_extension",
        auth_method="oauth2_authorization_code_or_private_app_token",
        collector_mappings=(
            _crm_connector_mappings("hubspot", "HubSpot")
            + _support_connector_mappings("hubspot", "HubSpot")
            + _analytics_connector_mappings("hubspot", "HubSpot")
        ),
        poller_supported=False,
        webhook_supported=True,
        notes="Use HubSpot CRM webhooks for object property changes and ticket events; browser/add-on ingress is required for viewed dashboards and records.",
    ),
    ConnectorSourceManifest(
        provider_id="zendesk",
        display_name="Zendesk",
        source_type="support_webhook_or_browser_extension",
        auth_method="oauth2_authorization_code_or_api_token",
        collector_mappings=_support_connector_mappings("zendesk", "Zendesk"),
        poller_supported=False,
        webhook_supported=True,
        notes="Use Zendesk webhooks/triggers for ticket lifecycle metadata; browser/app ingress covers agent-side views and macros without message bodies.",
    ),
    ConnectorSourceManifest(
        provider_id="intercom",
        display_name="Intercom",
        source_type="support_webhook_or_browser_extension",
        auth_method="oauth2_authorization_code_or_access_token",
        collector_mappings=_support_connector_mappings("intercom", "Intercom"),
        poller_supported=False,
        webhook_supported=True,
        notes="Use Intercom webhooks for conversation and ticket events; browser/app ingress covers inbox navigation and views with conversation content redacted.",
    ),
    ConnectorSourceManifest(
        provider_id="freshdesk",
        display_name="Freshdesk",
        source_type="support_webhook_or_browser_extension",
        auth_method="api_key_or_oauth2",
        collector_mappings=_support_connector_mappings("freshdesk", "Freshdesk"),
        poller_supported=False,
        webhook_supported=True,
        notes="Use Freshdesk ticket automations/webhooks for ticket lifecycle metadata; browser/app ingress covers agent views and dashboard metadata.",
    ),
    ConnectorSourceManifest(
        provider_id="stripe",
        display_name="Stripe",
        source_type="payment_webhook_or_browser_extension",
        auth_method="restricted_api_key_or_oauth2",
        collector_mappings=(
            _finance_connector_mappings("stripe", "Stripe")
            + (ConnectorEventMapping("stripe_subscription_changed", "commerce_activity", "subscription_changed", "Stripe subscription changed"),)
            + _analytics_connector_mappings("stripe", "Stripe")
        ),
        poller_supported=False,
        webhook_supported=True,
        notes="Use Stripe webhook events for payments, invoices, customers, refunds, and subscriptions; dashboard views require browser/app ingress.",
    ),
    ConnectorSourceManifest(
        provider_id="shopify",
        display_name="Shopify",
        source_type="admin_webhook_or_browser_extension",
        auth_method="oauth2_authorization_code_or_admin_token",
        collector_mappings=_commerce_connector_mappings("shopify", "Shopify") + _analytics_connector_mappings("shopify", "Shopify"),
        poller_supported=False,
        webhook_supported=True,
        notes="Use Shopify Admin webhooks for order/customer/refund/fulfillment metadata; admin dashboard/report views require browser/app ingress.",
    ),
    ConnectorSourceManifest(
        provider_id="quickbooks",
        display_name="QuickBooks",
        source_type="accounting_webhook_or_browser_extension",
        auth_method="oauth2_authorization_code",
        collector_mappings=_finance_connector_mappings("quickbooks", "QuickBooks") + _analytics_connector_mappings("quickbooks", "QuickBooks"),
        poller_supported=False,
        webhook_supported=True,
        notes="Use QuickBooks Online webhooks for accounting entity changes; report exports and dashboard views require browser/app ingress.",
    ),
    ConnectorSourceManifest(
        provider_id="xero",
        display_name="Xero",
        source_type="accounting_webhook_or_browser_extension",
        auth_method="oauth2_authorization_code",
        collector_mappings=_finance_connector_mappings("xero", "Xero") + _analytics_connector_mappings("xero", "Xero"),
        poller_supported=False,
        webhook_supported=True,
        notes="Use Xero webhooks for accounting events; report exports and dashboard views require browser/app ingress.",
    ),
    *CLOUD_FILE_SOURCE_MANIFESTS,
    *DESIGN_SOURCE_MANIFESTS,
    *DATA_ANALYTICS_SOURCE_MANIFESTS,
    *OPERATIONS_SOURCE_MANIFESTS,
    *DEVELOPER_SOURCE_MANIFESTS,
)


def connector_source_manifest_records(provider_id: str | None = None) -> dict[str, Any]:
    manifests = _source_manifests(provider_id)
    sources = [manifest.to_record() for manifest in manifests]
    return {
        "sources": sources,
        "source_count": len(sources),
        "owner": "humungousaur.collectors.sources.workspace_connectors",
        "connector_boundary": "uses connector readiness; does not own auth or token storage",
    }


def append_connector_source_event(
    config: AgentConfig,
    *,
    provider_id: str,
    source_event: str,
    object_type: str = "",
    object_id: str = "",
    metadata: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: str = "",
) -> dict[str, Any]:
    from humungousaur.collectors.envelope import CollectorEventEnvelope
    from humungousaur.collectors.event_log import CollectorEventLog

    config = config.normalized()
    manifest = _source_manifest(provider_id)
    mapping = _mapping(manifest.collector_mappings, source_event, provider_id)
    _validate_mapping(mapping)
    safe_metadata = _safe_metadata(
        provider_id=provider_id,
        display_name=manifest.display_name,
        source_event=source_event,
        object_type=object_type,
        object_id=object_id,
        metadata=metadata or {},
    )
    safe_payload = _safe_payload(payload or {})
    signature = _signature(
        {
            "provider_id": provider_id,
            "source_event": source_event,
            "collector": mapping.collector,
            "stimulus_type": mapping.stimulus_type,
            "object_id_hash": safe_metadata.get("object_id_hash"),
            "occurred_at": occurred_at,
            "payload": safe_payload,
        }
    )
    envelope = CollectorEventEnvelope(
        event_id=f"connector-{provider_id}-{signature[:24]}",
        collector=mapping.collector,
        source=provider_id,
        platform=platform.system(),
        stimulus_type=mapping.stimulus_type,
        privacy_tier=mapping.privacy_tier,
        occurred_at=occurred_at or _utc_now(),
        received_at=_utc_now(),
        signature=f"{provider_id}:{source_event}:{signature}",
        text=mapping.text,
        metadata=safe_metadata,
        payload=safe_payload,
        redaction={
            "privacy_tier": mapping.privacy_tier,
            "raw_content_included": False,
            "attention_safe": True,
            "paths_redacted": True,
            "payload_compacted_before_llm": True,
            "provider_content_redacted": True,
        },
    )
    from humungousaur.collectors.source_gate import append_source_envelope

    gate = append_source_envelope(config, envelope)
    if not gate.accepted:
        return {
            "accepted": False,
            "provider_id": provider_id,
            "source_event": source_event,
            "collector": mapping.collector,
            "stimulus_type": mapping.stimulus_type,
            "reason": gate.reason,
        }
    appended = gate.appended or {}
    return {
        "accepted": True,
        "provider_id": provider_id,
        "source_event": source_event,
        "collector": mapping.collector,
        "stimulus_type": mapping.stimulus_type,
        **appended,
    }


def record_connector_source_health(
    config: AgentConfig,
    *,
    provider_id: str,
    status: str,
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from humungousaur.collectors.event_log import CollectorEventLog

    config = config.normalized()
    manifest = _source_manifest(provider_id)
    if status not in {"starting", "running", "degraded", "permission_denied", "rate_limited", "stopped", "failed"}:
        raise ValueError(f"unsupported connector source health status: {status or '<empty>'}")
    collectors = sorted({mapping.collector for mapping in manifest.collector_mappings})
    event_log = CollectorEventLog(config.collector_events_db_path)
    for collector in collectors:
        event_log.record_helper_health(
            helper_id=f"connector-source-{provider_id}-{collector}",
            collector=collector,
            platform=platform.system(),
            status=status,
            version="0.1",
            permission_state="connector_ready" if status == "running" else status,
            last_event_at=str((metadata or {}).get("last_event_at") or ""),
            message=message,
            metadata={
                "provider_id": provider_id,
                "display_name": manifest.display_name,
                "source_type": manifest.source_type,
                "auth_method": manifest.auth_method,
                "source_owner": "collectors",
                **safe_metadata_values(metadata or {}),
            },
        )
    return {"accepted": True, "provider_id": provider_id, "status": status, "collector_count": len(collectors)}


def connector_source_status(config: AgentConfig, provider_id: str | None = None) -> dict[str, Any]:
    from humungousaur.collectors.event_log import CollectorEventLog

    config = config.normalized()
    manifest_records = connector_source_manifest_records(provider_id)["sources"]
    health = CollectorEventLog(config.collector_events_db_path).helper_health(limit=500)
    health_by_provider: dict[str, list[dict[str, Any]]] = {}
    for item in health:
        provider = str((item.get("metadata") or {}).get("provider_id") or "")
        if provider:
            health_by_provider.setdefault(provider, []).append(item)
    sources = []
    for manifest in manifest_records:
        provider = str(manifest["provider_id"])
        sources.append(
            {
                **manifest,
                "connector_readiness": _connector_readiness(config, provider),
                "helper_health": health_by_provider.get(provider, []),
                "health_count": len(health_by_provider.get(provider, [])),
            }
        )
    return {
        "sources": sources,
        "source_count": len(sources),
        "owner": "humungousaur.collectors.sources.workspace_connectors",
    }


def run_connector_source_tick(
    config: AgentConfig,
    *,
    provider_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    from humungousaur.collectors.event_log import CollectorEventLog

    config = config.normalized()
    if str(provider_id or "").strip() == "google_workspace":
        from .google_workspace import run_google_workspace_source_tick

        return run_google_workspace_source_tick(config, dry_run=dry_run)
    if str(provider_id or "").strip() in {
        "salesforce",
        "hubspot",
        "zendesk",
        "intercom",
        "freshdesk",
        "stripe",
        "shopify",
        "quickbooks",
        "xero",
    }:
        from .business_operations import run_business_operations_source_tick

        return run_business_operations_source_tick(config, provider_id=str(provider_id or "").strip(), dry_run=dry_run)
    if str(provider_id or "").strip() == "microsoft_365":
        from .microsoft_365 import run_microsoft_365_source_tick

        return run_microsoft_365_source_tick(config, dry_run=dry_run)
    if str(provider_id or "").strip() == "communication":
        from .communication import run_communication_source_tick

        return run_communication_source_tick(config, dry_run=dry_run)
    if str(provider_id or "").strip() in CLOUD_FILE_PROVIDER_IDS:
        return run_cloud_file_source_tick(config, provider_id=str(provider_id or "").strip(), dry_run=dry_run)
    if str(provider_id or "").strip() in DESIGN_PROVIDER_IDS:
        from .design import run_design_source_tick

        return run_design_source_tick(config, provider_id=str(provider_id or "").strip(), dry_run=dry_run)
    if str(provider_id or "").strip() in DATA_ANALYTICS_PROVIDER_IDS:
        from .data_analytics import run_data_analytics_source_tick

        return run_data_analytics_source_tick(config, provider_id=str(provider_id or "").strip(), dry_run=dry_run)
    if str(provider_id or "").strip() in OPERATIONS_PROVIDER_IDS:
        from .operations import run_operations_source_tick

        return run_operations_source_tick(config, provider_id=str(provider_id or "").strip(), dry_run=dry_run)
    try:
        from .developer.common import DEVELOPER_PROVIDER_IDS
        from .developer.registry import run_developer_source_tick

        if str(provider_id or "").strip() in DEVELOPER_PROVIDER_IDS:
            return run_developer_source_tick(config, provider_id=str(provider_id or "").strip(), dry_run=dry_run)
    except ImportError:
        pass
    try:
        from .knowledge_base import KNOWLEDGE_BASE_PROVIDER_IDS, run_knowledge_base_source_tick

        if str(provider_id or "").strip() in KNOWLEDGE_BASE_PROVIDER_IDS:
            return run_knowledge_base_source_tick(config, provider_id=str(provider_id or "").strip(), dry_run=dry_run)
    except ImportError:
        pass
    try:
        from .planning import PLANNING_PROVIDER_IDS, run_planning_source_tick

        if str(provider_id or "").strip() in PLANNING_PROVIDER_IDS:
            return run_planning_source_tick(config, provider_id=str(provider_id or "").strip(), dry_run=dry_run)
    except ImportError:
        pass
    manifests = connector_source_manifest_records(provider_id)["sources"]
    log = CollectorEventLog(config.collector_events_db_path)
    state = log.consumer_state("connector_sources")
    source_state = state.setdefault("sources", {})
    results = []
    for manifest in manifests:
        provider = str(manifest["provider_id"])
        provider_state = source_state.setdefault(provider, {})
        previous_tick = provider_state.get("last_tick_at", "")
        provider_state["last_tick_at"] = _utc_now()
        provider_state["tick_count"] = int(provider_state.get("tick_count") or 0) + 1
        provider_state["poller_supported"] = bool(manifest.get("poller_supported"))
        provider_state["webhook_supported"] = bool(manifest.get("webhook_supported"))
        provider_state["requires_connector"] = bool(manifest.get("requires_connector", True))
        readiness = _connector_readiness(config, provider)
        health_status = "running" if (not provider_state["requires_connector"] or readiness.get("connection_ready")) else "permission_denied"
        if not dry_run:
            record_connector_source_health(
                config,
                provider_id=provider,
                status=health_status,
                message="Collector source tick completed; provider polling uses connector readiness before API access.",
                metadata={"last_tick_at": provider_state["last_tick_at"], "previous_tick_at": previous_tick},
            )
        results.append(
            {
                "provider_id": provider,
                "status": health_status,
                "events_appended": 0,
                "last_tick_at": provider_state["last_tick_at"],
                "poller_supported": provider_state["poller_supported"],
                "webhook_supported": provider_state["webhook_supported"],
                "connector_readiness": readiness,
            }
        )
    if not dry_run:
        log.save_consumer_state("connector_sources", state)
    return {"status": "succeeded", "sources": results, "source_count": len(results), "dry_run": dry_run}


def safe_metadata_values(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed: dict[str, Any] = {}
    for key, value in metadata.items():
        clean_key = _clean_identifier(key)
        if not clean_key or clean_key in _FORBIDDEN_METADATA_KEYS:
            if clean_key:
                allowed[f"{clean_key}_redacted"] = True
            continue
        if clean_key == "id" or clean_key.endswith("_id"):
            clean_value = str(value or "").strip()
            if clean_value:
                allowed[f"{clean_key}_hash"] = f"sha256:{hashlib.sha256(clean_value.encode('utf-8')).hexdigest()}"
            continue
        if clean_key.endswith(("_title", "_body", "_text", "_name", "_email", "_url", "_path", "_query", "_sql")):
            allowed[f"{clean_key}_redacted"] = True
            continue
        if clean_key.endswith(("_value", "_formula", "_location", "_attendee", "_attendees")):
            allowed[f"{clean_key}_redacted"] = True
            continue
        if isinstance(value, bool):
            allowed[clean_key] = value
        elif isinstance(value, (int, float)):
            allowed[clean_key] = value
        elif isinstance(value, str):
            if clean_key in _SAFE_STRING_METADATA_KEYS:
                allowed[clean_key] = _clean_identifier(value)[:120]
            else:
                allowed[f"{clean_key}_redacted"] = True
        elif isinstance(value, list):
            allowed[f"{clean_key}_count"] = len(value)
        elif isinstance(value, dict):
            allowed[f"{clean_key}_keys"] = sorted(_clean_identifier(item) for item in value)[:20]
    return allowed


def _source_manifests(provider_id: str | None = None) -> list[ConnectorSourceManifest]:
    provider = str(provider_id or "").strip()
    manifests = list(CONNECTOR_SOURCE_MANIFESTS)
    if provider:
        manifests = [manifest for manifest in manifests if manifest.provider_id == provider]
        if not manifests:
            raise KeyError(f"Unknown connector source provider: {provider_id}")
    return manifests


def _source_manifest(provider_id: str) -> ConnectorSourceManifest:
    return _source_manifests(provider_id)[0]


def _connector_readiness(config: AgentConfig, provider_id: str) -> dict[str, Any]:
    try:
        manifest = _source_manifest(provider_id)
    except KeyError:
        manifest = None
    if manifest is not None and not manifest.requires_connector:
        return {
            "provider_id": provider_id,
            "configured": True,
            "connected": True,
            "connection_ready": True,
            "collector_ready": True,
            "auth_method": manifest.auth_method,
            "source_type": manifest.source_type,
            "local_bridge": True,
        }
    try:
        from humungousaur.connectors import ConnectorRuntime

        readiness = ConnectorRuntime(config).readiness(provider_id)
        readiness["connection_ready"] = bool(readiness.get("connected"))
        return readiness
    except Exception as exc:
        return {
            "provider_id": provider_id,
            "configured": False,
            "connected": False,
            "connection_ready": False,
            "error": str(exc),
        }


def _mapping(mappings: tuple[ConnectorEventMapping, ...], source_event: str, provider_id: str) -> ConnectorEventMapping:
    for mapping in mappings:
        if mapping.source_event == source_event:
            return mapping
    raise ValueError(f"Unsupported source_event for {provider_id}: {source_event or '<empty>'}")


def _validate_mapping(mapping: ConnectorEventMapping) -> None:
    from humungousaur.collectors.definitions import DEFINITIONS_BY_NAME

    definition = DEFINITIONS_BY_NAME.get(mapping.collector)
    if definition is None:
        raise ValueError(f"Unknown collector mapping: {mapping.collector}")
    if mapping.stimulus_type not in definition.stimulus_types:
        raise ValueError(f"Unsupported collector stimulus mapping: {mapping.collector}/{mapping.stimulus_type}")


def _safe_metadata(
    *,
    provider_id: str,
    display_name: str,
    source_event: str,
    object_type: str,
    object_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    clean: dict[str, Any] = {
        "provider": provider_id,
        "provider_display_name": display_name,
        "source_event": source_event,
        "source_integration_type": "workspace_connector",
        "source_owner": "collectors",
        "privacy_contract": "metadata_first",
        "title_redacted": True,
        "body_redacted": True,
        "participants_redacted": True,
        "raw_content_included": False,
    }
    object_type_clean = _clean_identifier(object_type)
    if object_type_clean:
        clean["object_type"] = object_type_clean
    object_id_clean = str(object_id or "").strip()
    if object_id_clean:
        clean["object_id_hash"] = f"sha256:{hashlib.sha256(object_id_clean.encode('utf-8')).hexdigest()}"
    clean.update(safe_metadata_values(metadata))
    return clean


def _safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return safe_metadata_values(payload)


def _signature(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _clean_identifier(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return "".join(char for char in text if char.isalnum() or char == "_")


_FORBIDDEN_METADATA_KEYS = {
    "attendee",
    "attendees",
    "title",
    "name",
    "body",
    "cell_value",
    "text",
    "content",
    "message",
    "formula",
    "location",
    "subject",
    "email",
    "url",
    "path",
    "filename",
    "file_name",
    "participant",
    "participants",
    "recipient",
    "recipients",
    "customer",
    "sql",
    "query",
    "token",
    "secret",
    "password",
    "credential",
}

_SAFE_STRING_METADATA_KEYS = {
    "app",
    "calendar_event_status",
    "box_event_type",
    "change_origin",
    "mime_type",
    "object_type",
    "permission_role",
    "permission_scope",
    "priority_bucket",
    "provider_event_type",
    "source_event",
    "source_channel",
    "status_bucket",
    "sync_state",
}

_safe_metadata_values = safe_metadata_values

__all__ = [
    "CONNECTOR_SOURCE_MANIFESTS",
    "ConnectorEventMapping",
    "ConnectorSourceManifest",
    "append_connector_source_event",
    "connector_source_manifest_records",
    "connector_source_status",
    "record_connector_source_health",
    "run_connector_source_tick",
]
