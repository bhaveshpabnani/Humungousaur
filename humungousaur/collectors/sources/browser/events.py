from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.collectors.definitions import DEFINITIONS_BY_NAME
from humungousaur.collectors.envelope import CollectorEventEnvelope
from humungousaur.collectors.event_log import CollectorEventLog

from .common import BROWSER_PRIVACY_TIER, BROWSER_SOURCE_ID, clean_token, hash_value, safe_url_metadata, utc_now


@dataclass(frozen=True, slots=True)
class BrowserEventMapping:
    source_event: str
    collector: str
    stimulus_type: str
    text: str
    privacy_tier: str = BROWSER_PRIVACY_TIER

    def to_record(self) -> dict[str, Any]:
        return {
            "source_event": self.source_event,
            "collector": self.collector,
            "stimulus_type": self.stimulus_type,
            "text": self.text,
            "privacy_tier": self.privacy_tier,
        }


_BROWSER_ALIASES = {
    "chrome": "chrome",
    "google_chrome": "chrome",
    "edge": "edge",
    "microsoft_edge": "edge",
    "brave": "brave",
    "firefox": "firefox",
    "mozilla_firefox": "firefox",
    "safari": "safari",
    "apple_safari": "safari",
}

_EVENT_ALIASES = {
    "tab_observed": "browser_tab_observed",
    "tab_created": "browser_tab_opened",
    "tab_opened": "browser_tab_opened",
    "tab_removed": "browser_tab_closed",
    "tab_closed": "browser_tab_closed",
    "tab_activated": "browser_tab_switched",
    "tab_switched": "browser_tab_switched",
    "tab_updated": "browser_url_changed",
    "url_changed": "browser_url_changed",
    "navigation_started": "browser_url_changed",
    "navigation_committed": "browser_url_changed",
    "history_state_updated": "browser_url_changed",
    "title_changed": "browser_title_changed",
    "page_title_changed": "browser_title_changed",
    "reloaded": "browser_reloaded",
    "reload": "browser_reloaded",
    "back": "browser_back",
    "forward": "browser_forward",
    "window_created": "browser_window_opened",
    "window_opened": "browser_window_opened",
    "window_removed": "browser_window_closed",
    "window_closed": "browser_window_closed",
    "window_focused": "browser_window_focused",
    "window_minimized": "browser_window_minimized",
    "fullscreen_entered": "browser_window_fullscreen_entered",
    "fullscreen_exited": "browser_window_fullscreen_exited",
    "session_restored": "browser_session_restored",
    "recently_closed_window_reopened": "recently_closed_window_reopened",
    "profile_switched": "browser_profile_switched",
    "profile_created": "browser_profile_created",
    "profile_signed_in": "browser_profile_signed_in",
    "profile_signed_out": "browser_profile_signed_out",
    "sync_enabled": "browser_sync_enabled",
    "sync_disabled": "browser_sync_disabled",
    "guest_profile_opened": "guest_profile_opened",
    "private_window_opened": "private_window_opened",
    "tab_group_created": "tab_group_created",
    "tab_group_renamed": "tab_group_renamed",
    "tab_group_color_changed": "tab_group_color_changed",
    "tab_group_collapsed": "tab_group_collapsed",
    "tab_group_expanded": "tab_group_expanded",
    "tab_group_saved": "tab_group_saved",
    "tab_group_restored": "tab_group_restored",
    "tab_moved_to_group": "tab_moved_to_group",
    "tab_removed_from_group": "tab_removed_from_group",
    "extension_action_clicked": "extension_action_clicked",
    "extension_clicked": "extension_action_clicked",
    "extension_popup_opened": "extension_popup_opened",
    "extension_installed": "extension_installed",
    "extension_removed": "extension_removed",
    "extension_enabled": "extension_enabled",
    "extension_disabled": "extension_disabled",
    "extension_permission_requested": "extension_permission_requested",
    "extension_error": "extension_error_reported",
    "extension_error_reported": "extension_error_reported",
    "web_app_installed": "web_app_installed",
    "pwa_installed": "web_app_installed",
    "web_app_uninstalled": "web_app_uninstalled",
    "web_app_opened": "web_app_opened",
    "web_app_closed": "web_app_closed",
    "web_app_windowed": "web_app_windowed",
    "web_app_offline_ready": "web_app_offline_ready",
    "web_app_notification_permission_requested": "web_app_notification_permission_requested",
    "web_app_badge_changed": "web_app_badge_changed",
    "reader_mode_enabled": "reader_mode_enabled",
    "reader_mode_disabled": "reader_mode_disabled",
    "find_in_page": "find_in_page_performed",
    "find_in_page_performed": "find_in_page_performed",
    "zoom_changed": "page_zoom_changed",
    "page_zoom_changed": "page_zoom_changed",
    "page_muted": "page_muted",
    "page_unmuted": "page_unmuted",
    "picture_in_picture_started": "picture_in_picture_started",
    "pip_started": "picture_in_picture_started",
    "picture_in_picture_stopped": "picture_in_picture_stopped",
    "pip_stopped": "picture_in_picture_stopped",
    "translation_offered": "page_translation_offered",
    "page_translation_offered": "page_translation_offered",
    "translation_accepted": "page_translation_accepted",
    "page_translation_accepted": "page_translation_accepted",
    "link_clicked": "link_clicked",
    "form_changed": "form_changed",
    "form_submitted": "form_submitted",
    "file_uploaded": "file_uploaded",
    "upload_started": "file_uploaded",
    "download_started": "download_started",
    "download_finished": "download_finished",
    "download_completed": "download_finished",
    "page_error": "page_error",
    "console_error": "console_error",
    "selected_page_text_changed": "selected_page_text_changed",
    "bookmark_added": "bookmark_added",
    "bookmark_removed": "bookmark_removed",
    "reading_list_added": "reading_list_added",
    "history_item_opened": "history_item_opened",
    "history_search_performed": "history_search_performed",
    "saved_tab_group_changed": "saved_tab_group_changed",
    "autofill_suggestion_shown": "autofill_suggestion_shown",
    "autofill_suggestion_accepted": "autofill_suggestion_accepted",
    "autofill_suggestion_dismissed": "autofill_suggestion_dismissed",
    "payment_autofill_prompt_shown": "payment_autofill_prompt_shown",
    "address_autofill_prompt_shown": "address_autofill_prompt_shown",
    "form_autofill_failed": "form_autofill_failed",
    "dns_error": "dns_error",
    "api_request_failed": "api_request_failed",
    "api_rate_limited": "api_rate_limited",
}

_MAPPINGS: tuple[BrowserEventMapping, ...] = (
    BrowserEventMapping("browser_tab_observed", "browser_lifecycle", "browser_tab_observed", "Browser tab metadata was observed"),
    BrowserEventMapping("browser_url_changed", "browser_lifecycle", "browser_url_changed", "Browser URL changed"),
    BrowserEventMapping("browser_title_changed", "browser_lifecycle", "browser_title_changed", "Browser page title changed"),
    BrowserEventMapping("browser_tab_opened", "browser_lifecycle", "browser_tab_opened", "Browser tab opened"),
    BrowserEventMapping("browser_tab_closed", "browser_lifecycle", "browser_tab_closed", "Browser tab closed"),
    BrowserEventMapping("browser_tab_switched", "browser_lifecycle", "browser_tab_switched", "Browser tab switched"),
    BrowserEventMapping("browser_reloaded", "browser_lifecycle", "browser_reloaded", "Browser page reloaded"),
    BrowserEventMapping("browser_back", "browser_lifecycle", "browser_back", "Browser navigated back"),
    BrowserEventMapping("browser_forward", "browser_lifecycle", "browser_forward", "Browser navigated forward"),
    BrowserEventMapping("browser_window_opened", "browser_window_activity", "browser_window_opened", "Browser window opened"),
    BrowserEventMapping("browser_window_closed", "browser_window_activity", "browser_window_closed", "Browser window closed"),
    BrowserEventMapping("browser_window_focused", "browser_window_activity", "browser_window_focused", "Browser window focused"),
    BrowserEventMapping("browser_window_minimized", "browser_window_activity", "browser_window_minimized", "Browser window minimized"),
    BrowserEventMapping("browser_window_fullscreen_entered", "browser_window_activity", "browser_window_fullscreen_entered", "Browser window entered fullscreen"),
    BrowserEventMapping("browser_window_fullscreen_exited", "browser_window_activity", "browser_window_fullscreen_exited", "Browser window exited fullscreen"),
    BrowserEventMapping("browser_session_restored", "browser_window_activity", "browser_session_restored", "Browser session restored"),
    BrowserEventMapping("recently_closed_window_reopened", "browser_window_activity", "recently_closed_window_reopened", "Recently closed browser window reopened"),
    BrowserEventMapping("browser_profile_switched", "browser_profile_activity", "browser_profile_switched", "Browser profile switched"),
    BrowserEventMapping("browser_profile_created", "browser_profile_activity", "browser_profile_created", "Browser profile created"),
    BrowserEventMapping("browser_profile_signed_in", "browser_profile_activity", "browser_profile_signed_in", "Browser profile signed in"),
    BrowserEventMapping("browser_profile_signed_out", "browser_profile_activity", "browser_profile_signed_out", "Browser profile signed out"),
    BrowserEventMapping("browser_sync_enabled", "browser_profile_activity", "browser_sync_enabled", "Browser sync enabled"),
    BrowserEventMapping("browser_sync_disabled", "browser_profile_activity", "browser_sync_disabled", "Browser sync disabled"),
    BrowserEventMapping("guest_profile_opened", "browser_profile_activity", "guest_profile_opened", "Browser guest profile opened"),
    BrowserEventMapping("private_window_opened", "browser_profile_activity", "private_window_opened", "Private browser window opened"),
    BrowserEventMapping("tab_group_created", "browser_tab_group_activity", "tab_group_created", "Browser tab group created"),
    BrowserEventMapping("tab_group_renamed", "browser_tab_group_activity", "tab_group_renamed", "Browser tab group renamed"),
    BrowserEventMapping("tab_group_color_changed", "browser_tab_group_activity", "tab_group_color_changed", "Browser tab group color changed"),
    BrowserEventMapping("tab_group_collapsed", "browser_tab_group_activity", "tab_group_collapsed", "Browser tab group collapsed"),
    BrowserEventMapping("tab_group_expanded", "browser_tab_group_activity", "tab_group_expanded", "Browser tab group expanded"),
    BrowserEventMapping("tab_group_saved", "browser_tab_group_activity", "tab_group_saved", "Browser tab group saved"),
    BrowserEventMapping("tab_group_restored", "browser_tab_group_activity", "tab_group_restored", "Browser tab group restored"),
    BrowserEventMapping("tab_moved_to_group", "browser_tab_group_activity", "tab_moved_to_group", "Browser tab moved to group"),
    BrowserEventMapping("tab_removed_from_group", "browser_tab_group_activity", "tab_removed_from_group", "Browser tab removed from group"),
    BrowserEventMapping("extension_action_clicked", "browser_extension_activity", "extension_action_clicked", "Browser extension action clicked"),
    BrowserEventMapping("extension_popup_opened", "browser_extension_activity", "extension_popup_opened", "Browser extension popup opened"),
    BrowserEventMapping("extension_installed", "browser_extension_activity", "extension_installed", "Browser extension installed"),
    BrowserEventMapping("extension_removed", "browser_extension_activity", "extension_removed", "Browser extension removed"),
    BrowserEventMapping("extension_enabled", "browser_extension_activity", "extension_enabled", "Browser extension enabled"),
    BrowserEventMapping("extension_disabled", "browser_extension_activity", "extension_disabled", "Browser extension disabled"),
    BrowserEventMapping("extension_permission_requested", "browser_extension_activity", "extension_permission_requested", "Browser extension permission requested"),
    BrowserEventMapping("extension_error_reported", "browser_extension_activity", "extension_error_reported", "Browser extension error reported"),
    BrowserEventMapping("web_app_installed", "browser_web_app_activity", "web_app_installed", "Browser web app installed"),
    BrowserEventMapping("web_app_uninstalled", "browser_web_app_activity", "web_app_uninstalled", "Browser web app uninstalled"),
    BrowserEventMapping("web_app_opened", "browser_web_app_activity", "web_app_opened", "Browser web app opened"),
    BrowserEventMapping("web_app_closed", "browser_web_app_activity", "web_app_closed", "Browser web app closed"),
    BrowserEventMapping("web_app_windowed", "browser_web_app_activity", "web_app_windowed", "Browser web app opened in window mode"),
    BrowserEventMapping("web_app_offline_ready", "browser_web_app_activity", "web_app_offline_ready", "Browser web app became offline ready"),
    BrowserEventMapping("web_app_notification_permission_requested", "browser_web_app_activity", "web_app_notification_permission_requested", "Browser web app requested notification permission"),
    BrowserEventMapping("web_app_badge_changed", "browser_web_app_activity", "web_app_badge_changed", "Browser web app badge changed"),
    BrowserEventMapping("reader_mode_enabled", "browser_view_mode_activity", "reader_mode_enabled", "Browser reader mode enabled"),
    BrowserEventMapping("reader_mode_disabled", "browser_view_mode_activity", "reader_mode_disabled", "Browser reader mode disabled"),
    BrowserEventMapping("find_in_page_performed", "browser_view_mode_activity", "find_in_page_performed", "Browser find-in-page used"),
    BrowserEventMapping("page_zoom_changed", "browser_view_mode_activity", "page_zoom_changed", "Browser page zoom changed"),
    BrowserEventMapping("page_muted", "browser_view_mode_activity", "page_muted", "Browser page muted"),
    BrowserEventMapping("page_unmuted", "browser_view_mode_activity", "page_unmuted", "Browser page unmuted"),
    BrowserEventMapping("picture_in_picture_started", "browser_view_mode_activity", "picture_in_picture_started", "Browser picture-in-picture started"),
    BrowserEventMapping("picture_in_picture_stopped", "browser_view_mode_activity", "picture_in_picture_stopped", "Browser picture-in-picture stopped"),
    BrowserEventMapping("page_translation_offered", "browser_view_mode_activity", "page_translation_offered", "Browser page translation offered"),
    BrowserEventMapping("page_translation_accepted", "browser_view_mode_activity", "page_translation_accepted", "Browser page translation accepted"),
    BrowserEventMapping("link_clicked", "browser_page_activity", "link_clicked", "Browser page link clicked"),
    BrowserEventMapping("form_changed", "browser_page_activity", "form_changed", "Browser form changed"),
    BrowserEventMapping("form_submitted", "browser_page_activity", "form_submitted", "Browser form submitted"),
    BrowserEventMapping("file_uploaded", "browser_page_activity", "file_uploaded", "Browser file upload used"),
    BrowserEventMapping("download_started", "browser_page_activity", "download_started", "Browser download started"),
    BrowserEventMapping("download_finished", "browser_page_activity", "download_finished", "Browser download finished"),
    BrowserEventMapping("page_error", "browser_page_activity", "page_error", "Browser page error occurred"),
    BrowserEventMapping("console_error", "browser_page_activity", "console_error", "Browser console error occurred"),
    BrowserEventMapping("selected_page_text_changed", "browser_page_activity", "selected_page_text_changed", "Browser page selection changed"),
    BrowserEventMapping("bookmark_added", "bookmark_history_activity", "bookmark_added", "Browser bookmark added"),
    BrowserEventMapping("bookmark_removed", "bookmark_history_activity", "bookmark_removed", "Browser bookmark removed"),
    BrowserEventMapping("reading_list_added", "bookmark_history_activity", "reading_list_added", "Browser reading-list item added"),
    BrowserEventMapping("history_item_opened", "bookmark_history_activity", "history_item_opened", "Browser history item opened"),
    BrowserEventMapping("history_search_performed", "bookmark_history_activity", "history_search_performed", "Browser history search performed"),
    BrowserEventMapping("saved_tab_group_changed", "bookmark_history_activity", "saved_tab_group_changed", "Browser saved tab group changed"),
    BrowserEventMapping("autofill_suggestion_shown", "autofill_activity", "autofill_suggestion_shown", "Browser autofill suggestion shown"),
    BrowserEventMapping("autofill_suggestion_accepted", "autofill_activity", "autofill_suggestion_accepted", "Browser autofill suggestion accepted"),
    BrowserEventMapping("autofill_suggestion_dismissed", "autofill_activity", "autofill_suggestion_dismissed", "Browser autofill suggestion dismissed"),
    BrowserEventMapping("payment_autofill_prompt_shown", "autofill_activity", "payment_autofill_prompt_shown", "Browser payment autofill prompt shown"),
    BrowserEventMapping("address_autofill_prompt_shown", "autofill_activity", "address_autofill_prompt_shown", "Browser address autofill prompt shown"),
    BrowserEventMapping("form_autofill_failed", "autofill_activity", "form_autofill_failed", "Browser autofill failed"),
    BrowserEventMapping("dns_error", "network_activity", "dns_error", "Browser DNS error observed", privacy_tier="metadata"),
    BrowserEventMapping("api_request_failed", "network_activity", "api_request_failed", "Browser API request failed", privacy_tier="metadata"),
    BrowserEventMapping("api_rate_limited", "network_activity", "api_rate_limited", "Browser API rate limit observed", privacy_tier="metadata"),
)

_MAPPING_BY_SOURCE_EVENT = {mapping.source_event: mapping for mapping in _MAPPINGS}


def append_browser_event(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        source_event = _source_event(payload)
        mapping = _MAPPING_BY_SOURCE_EVENT[source_event]
        _validate_mapping(mapping)
        metadata = _metadata_from_payload(payload, source_event)
        signature = _signature(payload, mapping, metadata)
        envelope = CollectorEventEnvelope(
            event_id=f"browser-{signature[:24]}",
            collector=mapping.collector,
            source=BROWSER_SOURCE_ID,
            platform=platform.system(),
            stimulus_type=mapping.stimulus_type,
            privacy_tier=mapping.privacy_tier,
            occurred_at=str(payload.get("occurred_at") or payload.get("timestamp") or utc_now()),
            received_at=utc_now(),
            signature=f"{BROWSER_SOURCE_ID}:{source_event}:{signature}",
            text=mapping.text,
            metadata=metadata,
            payload=_payload_from_browser_event(payload),
            redaction={
                "privacy_tier": mapping.privacy_tier,
                "raw_content_included": False,
                "attention_safe": True,
                "paths_redacted": True,
                "urls_redacted": True,
                "titles_redacted": True,
                "payload_compacted_before_llm": True,
                "browser_content_redacted": True,
            },
        )
        from humungousaur.collectors.source_gate import append_source_envelope

        gate = append_source_envelope(config, envelope)
        if not gate.accepted:
            return {
                "accepted": False,
                "source": BROWSER_SOURCE_ID,
                "source_event": source_event,
                "collector": mapping.collector,
                "stimulus_type": mapping.stimulus_type,
                "reason": gate.reason,
            }
        appended = gate.appended or {}
        return {
            "accepted": True,
            "source": BROWSER_SOURCE_ID,
            "source_event": source_event,
            "collector": mapping.collector,
            "stimulus_type": mapping.stimulus_type,
            **appended,
        }
    except (KeyError, ValueError) as exc:
        _append_dead_letter(config, payload, str(exc))
        raise ValueError(str(exc)) from exc


def append_browser_health(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "running").strip()
    if status not in {"starting", "running", "degraded", "permission_denied", "stopped", "failed"}:
        raise ValueError(f"unsupported browser source health status: {status or '<empty>'}")
    browser = _normalize_browser(payload.get("browser") or payload.get("app"))
    collector = str(payload.get("collector") or "browser_lifecycle").strip()
    if collector not in DEFINITIONS_BY_NAME:
        raise ValueError(f"unknown collector: {collector or '<empty>'}")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    CollectorEventLog(config.normalized().collector_events_db_path).record_helper_health(
        helper_id=f"browser-source-{browser or 'unknown'}-{collector}",
        collector=collector,
        platform=platform.system(),
        status=status,
        version="0.1",
        permission_state=str(payload.get("permission_state") or status),
        message=str(payload.get("message") or ""),
        metadata={
            "source": BROWSER_SOURCE_ID,
            "browser": browser,
            "display_name": _display_browser(browser),
            "source_channel": str(payload.get("source_channel") or "browser_extension"),
            **_safe_metadata_values(metadata),
        },
    )
    return {"accepted": True, "source": BROWSER_SOURCE_ID, "browser": browser, "status": status, "collector_count": 1}


def browser_source_status(config: AgentConfig) -> dict[str, Any]:
    from .registry import browser_collector_status_records

    normalized = config.normalized()
    log = CollectorEventLog(normalized.collector_events_db_path)
    health = [
        item
        for item in log.helper_health(limit=500)
        if str((item.get("metadata") or {}).get("source") or "") == BROWSER_SOURCE_ID
    ]
    pending_event_count = sum(1 for event in log.query(limit=1000) if event.get("source") == BROWSER_SOURCE_ID)
    return {
        "source": BROWSER_SOURCE_ID,
        "display_name": "Browsers",
        "source_type": "browser_extension_or_native_messaging",
        "auth_method": "local_extension_permission",
        "status": _health_status(health),
        "implementation_level": "real_webextension_emitter",
        "emitter_package": "browser_extensions/humungousaur_collector",
        "emitter_build_script": "browser_extensions/humungousaur_collector/scripts/build.py",
        "emitter_channels": ["webextension_background", "webextension_content_script"],
        "pending_event_count": pending_event_count,
        "dead_letter_count": _line_count(_dead_letters_path(normalized)),
        "dead_letters_path": str(_dead_letters_path(normalized)),
        "browser_collectors": browser_collector_status_records(),
        "supported_browsers": ["brave", "chrome", "edge", "firefox", "safari"],
        "collector_mappings": [mapping.to_record() for mapping in _MAPPINGS],
        "mapping_count": len(_MAPPINGS),
        "helper_health": health,
        "health_count": len(health),
        "privacy_contract": {
            "default_privacy_tier": BROWSER_PRIVACY_TIER,
            "raw_content_included": False,
            "urls_redacted": True,
            "titles_redacted": True,
            "form_values_redacted": True,
        },
    }


def _source_event(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("source_event") or "").strip()
    if explicit:
        return explicit
    event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    source_event = _EVENT_ALIASES.get(event_type)
    if not source_event:
        raise ValueError(f"unsupported browser event mapping: {event_type or '<event_type>'}")
    return source_event


def _metadata_from_payload(payload: dict[str, Any], source_event: str) -> dict[str, Any]:
    browser = _normalize_browser(payload.get("browser") or payload.get("app") or payload.get("application"))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    clean: dict[str, Any] = {
        "source_event": source_event,
        "source_integration_type": "browser_extension",
        "source_owner": "collectors",
        "privacy_contract": "metadata_first",
        "raw_content_included": False,
        "browser": browser,
        "browser_display_name": _display_browser(browser),
        "title_redacted": True,
        "url_redacted": True,
        "query_redacted": True,
        "form_values_redacted": True,
        "page_text_redacted": True,
    }
    provider_event_type = clean_token(payload.get("event_type") or payload.get("action") or payload.get("native_event_type"))
    if provider_event_type:
        clean["provider_event_type"] = provider_event_type
    for url_key in ("url", "document_url", "page_url", "target_url", "referrer_url", "download_url"):
        if url_key in payload:
            clean.update(safe_url_metadata(payload.get(url_key), prefix=url_key))
    for key in (
        "frame_id",
        "incognito",
        "is_private",
        "is_pinned",
        "muted",
        "active",
        "audible",
        "window_type",
        "tab_count",
        "error_code",
        "http_status",
        "zoom_level",
        "download_state",
        "file_size_bytes",
        "uploaded_file_count",
        "form_field_count",
        "extension_permission_count",
    ):
        if key in payload:
            clean[clean_token(key)] = _safe_scalar(payload[key])
    for id_key in (
        "tab_id",
        "window_id",
        "profile_id",
        "group_id",
        "extension_id",
        "web_app_id",
        "download_id",
        "form_id",
        "document_id",
        "session_id",
    ):
        if id_key in payload:
            value_hash = hash_value(payload[id_key])
            if value_hash:
                clean[f"{clean_token(id_key)}_hash"] = value_hash
    clean.update(_safe_metadata_values(metadata))
    return clean


def _payload_from_browser_event(payload: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in ("provider_event_id", "event_id", "source_channel", "browser_version", "extension_version"):
        if key in payload:
            safe_key = clean_token(key)
            if safe_key.endswith("_id"):
                safe[f"{safe_key}_hash"] = hash_value(payload[key])
            else:
                safe[safe_key] = str(payload[key])[:120]
    return safe


def _safe_metadata_values(metadata: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        token = clean_token(key)
        if not token:
            continue
        if token == "id" or token.endswith("_id"):
            value_hash = hash_value(value)
            if value_hash:
                clean[f"{token}_hash"] = value_hash
            continue
        if token.endswith(("_url", "_uri")):
            clean.update(safe_url_metadata(value, prefix=token))
            continue
        if token in {
            "title",
            "name",
            "body",
            "text",
            "content",
            "message",
            "subject",
            "query",
            "search",
            "url",
            "path",
            "filename",
            "file_name",
            "email",
            "username",
            "account",
            "profile",
            "form_value",
            "field_value",
            "selected_text",
            "console_message",
            "stack",
        }:
            clean[f"{token}_redacted"] = True
            continue
        if isinstance(value, bool):
            clean[token] = value
        elif isinstance(value, int | float):
            clean[token] = value
        elif isinstance(value, str):
            if token in {"browser", "engine", "source_channel", "window_type", "download_state", "error_code"}:
                clean[token] = clean_token(value)[:120]
            else:
                clean[f"{token}_redacted"] = True
        elif isinstance(value, list):
            clean[f"{token}_count"] = len(value)
        elif isinstance(value, dict):
            clean[f"{token}_keys"] = sorted(clean_token(item) for item in value)[:20]
    return clean


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value
    return clean_token(value)[:120]


def _validate_mapping(mapping: BrowserEventMapping) -> None:
    definition = DEFINITIONS_BY_NAME.get(mapping.collector)
    if definition is None:
        raise ValueError(f"Unknown collector mapping: {mapping.collector}")
    if mapping.stimulus_type not in definition.stimulus_types:
        raise ValueError(f"Unsupported collector stimulus mapping: {mapping.collector}/{mapping.stimulus_type}")


def _signature(payload: dict[str, Any], mapping: BrowserEventMapping, metadata: dict[str, Any]) -> str:
    body = json.dumps(
        {
            "source": BROWSER_SOURCE_ID,
            "source_event": mapping.source_event,
            "collector": mapping.collector,
            "stimulus_type": mapping.stimulus_type,
            "metadata": metadata,
            "occurred_at": payload.get("occurred_at") or payload.get("timestamp"),
            "provider_event_id": payload.get("provider_event_id") or payload.get("event_id"),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    import hashlib

    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _normalize_browser(value: Any) -> str:
    token = clean_token(value)
    return _BROWSER_ALIASES.get(token, token or "unknown")


def _display_browser(browser: str) -> str:
    return {
        "chrome": "Google Chrome",
        "edge": "Microsoft Edge",
        "brave": "Brave",
        "firefox": "Firefox",
        "safari": "Safari",
    }.get(browser, browser.replace("_", " ").title())


def _append_dead_letter(config: AgentConfig, payload: dict[str, Any], reason: str) -> None:
    path = _dead_letters_path(config.normalized())
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "reason": str(reason)[:500],
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "source": BROWSER_SOURCE_ID,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _dead_letters_path(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "collector_sources" / BROWSER_SOURCE_ID / "dead_letters.jsonl"


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


def _health_status(health: Any) -> str:
    if not isinstance(health, list) or not health:
        return "not_configured"
    return str(health[0].get("status") or "unknown")


__all__ = [
    "BrowserEventMapping",
    "append_browser_event",
    "append_browser_health",
    "browser_source_status",
]
