# Humungousaur Collector Architecture

Humungousaur collectors make the desktop agent active without turning it into a 24/7 recorder.

The rule is:

```text
Always available -> cheaply sense -> locally filter -> compact attention batch -> model attention decision -> optional agent action.
```

Raw telemetry must not be streamed to the LLM. Collectors emit structured local events. The runtime applies privacy policy, opt-in checks, dwell, dedupe, rate limits, batching, and redaction before a compact attention batch reaches the interaction harness.

## Current Runtime Contract

Collector code lives under `humungousaur/collectors`.

- `definitions.py`: source of truth for collector names, families, defaults, sensitivity, rate limits, and stimulus types.
- `models.py`: `CollectorProfile`, `CollectorEvent`, and `CollectorTickResult`.
- `bridge.py`: shared JSONL bridge ingestion for native helpers, browser extensions, shell integrations, and IDE extensions.
- `manager.py`: profile persistence, ticks, filters, local recording, attention batching, semantic event recording, and harness submission.
- `lifecycle.py`: lifecycle/input collector adapters that can use best-effort OS snapshots or native bridge spool files.
- `activity_adapters.py`: bridge-backed browser page, terminal, and IDE activity adapters.
- `productivity_adapters.py`: bridge-backed accessibility, notification, calendar, communication, mail, document, creative, security, and agent-runtime adapters.

The manager records local `collector_stimulus` events and sends only compact `attention_batch` stimuli to the LLM boundary.

## Privacy Tiers

| Tier | Default | Examples | Rule |
|---|---:|---|---|
| Metadata | on where safe | active app, window title, URL title | Can be collected after dwell/dedupe/policy. |
| Sensitive metadata | off unless useful | clipboard changed, audio activity | Requires explicit collector enablement and/or rich opt-in. |
| Rich capture | off | screenshot, OCR, video keyframe, transcript | Requires explicit rich-capture opt-in and strict rate limits. |
| Bridge events | off unless bridge installed | mouse forward, tab closed, app-specific action | Native helper writes structured JSONL events; no raw keylogging. |

Never collect raw passwords, OTPs, secret manager contents, private browsing, or keystroke text.

## Exhaustive Collector Catalog

| Family | Collector | Stimulus Types |
|---|---|---|
| Direct intent | `direct_user` | `user_text_submitted`, `global_hotkey_pressed`, `approval_accepted`, `approval_rejected` |
| Voice | `voice_wakeup`, `audio_activity`, `meeting_audio` | `voice_activity_detected`, `wake_word_detected`, `voice_transcript_final`, `meeting_transcript_chunk`, `speaker_changed`, `call_started`, `call_ended` |
| Device/session | `device_state` | `user_idle_state_changed`, `screen_locked`, `screen_unlocked`, `sleep_started`, `wake_started`, `battery_low`, `charger_connected`, `network_changed`, `vpn_changed`, `focus_mode_enabled` |
| Input device | `input_device` | `mouse_clicked`, `mouse_double_clicked`, `mouse_right_clicked`, `mouse_forward`, `mouse_back`, `mouse_scroll_burst`, `mouse_drag_started`, `mouse_drag_dropped`, `trackpad_gesture`, `keyboard_shortcut_pressed` |
| App lifecycle | `app_lifecycle` | `app_opened`, `app_closed`, `app_focused`, `app_hidden`, `app_crashed`, `app_not_responding`, `permission_prompt_shown` |
| Window lifecycle | `active_window`, `window_lifecycle` | `active_window_changed`, `window_opened`, `window_closed`, `window_focused`, `window_moved`, `window_resized`, `window_minimized`, `window_title_changed` |
| Screen/vision | `screenshot`, `screen_ocr`, `video_frame`, `visual_state` | `screenshot_captured`, `screen_text_changed`, `video_keyframe_captured`, `error_banner_visible`, `toast_visible`, `modal_visible`, `loading_spinner_stuck` |
| Accessibility | `accessibility_context` | `focused_control_changed`, `selected_text_changed`, `button_available`, `form_field_focused`, `menu_opened`, `table_row_selected`, `checkbox_toggled` |
| Browser lifecycle | `browser`, `browser_lifecycle` | `browser_tab_changed`, `browser_tab_opened`, `browser_tab_closed`, `browser_tab_switched`, `browser_url_changed`, `browser_title_changed`, `browser_reloaded`, `browser_back`, `browser_forward` |
| Browser page | `browser_page_activity` | `link_clicked`, `form_changed`, `form_submitted`, `file_uploaded`, `download_started`, `download_finished`, `page_error`, `console_error`, `selected_page_text_changed` |
| Clipboard/share | `clipboard`, `share_activity` | `clipboard_changed`, `clipboard_file_changed`, `clipboard_image_changed`, `clipboard_url_changed`, `share_sheet_opened`, `drag_drop_file`, `drag_drop_text` |
| Filesystem | `filesystem`, `downloads` | `file_created`, `file_opened`, `file_modified`, `file_saved`, `file_deleted`, `file_renamed`, `file_moved`, `folder_changed`, `downloaded_file`, `exported_file`, `mounted_volume_changed` |
| Notifications | `notification_activity` | `notification_received`, `notification_clicked`, `notification_dismissed`, `critical_alert_received`, `reminder_fired` |
| Calendar/time | `calendar_activity`, `wakeups` | `meeting_starting`, `meeting_started`, `meeting_ended`, `deadline_near`, `scheduled_wakeup_due`, `followup_due` |
| Communication | `channel_activity` | `message_received`, `mention_received`, `dm_received`, `thread_reply_received`, `reaction_added`, `message_sent`, `draft_created`, `call_invite_received`, `channel_unread_changed` |
| Terminal/dev | `terminal_activity` | `terminal_command_started`, `terminal_command_finished`, `terminal_command_failed`, `build_started`, `build_failed`, `tests_started`, `tests_failed`, `server_started`, `server_crashed` |
| IDE/code | `ide_activity` | `file_opened_in_ide`, `diagnostic_added`, `diagnostic_resolved`, `breakpoint_hit`, `debug_session_started`, `git_branch_changed`, `commit_created`, `merge_conflict_detected` |
| Git/GitHub | `git_activity`, `github_activity` | `pr_opened`, `pr_review_requested`, `ci_failed`, `ci_passed`, `issue_assigned`, `comment_received`, `merge_ready` |
| Documents | `document_activity` | `doc_opened`, `doc_edited`, `comment_added`, `suggestion_received`, `export_pdf_created`, `spreadsheet_formula_error`, `slide_deck_presented` |
| Creative apps | `creative_activity` | `canvas_selection_changed`, `frame_exported`, `asset_imported`, `render_started`, `render_finished`, `timeline_marker_changed` |
| Mail | `mail_activity` | `email_received`, `important_email_received`, `email_opened`, `draft_started`, `attachment_downloaded`, `send_failed` |
| Security | `security_context` | `password_field_focused`, `secret_manager_opened`, `private_browsing_detected`, `sensitive_app_focused`, `camera_enabled`, `microphone_enabled` |
| Agent internal | `agent_runtime` | `agent_run_started`, `tool_started`, `tool_failed`, `approval_requested`, `run_cancelled`, `run_stuck`, `memory_updated`, `autonomous_cycle_started` |

## Building A Collector Correctly

1. Add a `CollectorDefinition` in `humungousaur/collectors/definitions.py`.
2. Prefer metadata-only collection first. Mark rich collectors as `sensitive=True` and `rich_capture_required=True`.
3. Implement the adapter in a domain module such as `lifecycle.py`, `browser_activity.py`, `ide_activity.py`, or `channels_activity.py`.
4. Return `CollectorEvent` objects only. Do not call the LLM or tools directly from a collector.
5. Put raw or sensitive details in local payload only when policy allows it; compact attention events must redact raw clipboard, OCR, audio, video, and typed text.
6. Wire the adapter into the manager registry.
7. Add semantic-event mapping if the event should affect durable current context.
8. Add tests for profile defaults, privacy blocking, dedupe/rate limits, compact attention text, and at least one real or bridge-fed event.

## Bridge Event Contract

Some events cannot be collected reliably from Python without OS permissions or browser extensions. Native helpers should write JSONL to:

```text
data_dir/collector_spool/<collector>.jsonl
```

Each line:

```json
{
  "event_id": "stable-native-event-id",
  "stimulus_type": "mouse_forward",
  "text": "Mouse forward button pressed.",
  "occurred_at": "2026-06-10T10:00:00Z",
  "metadata": {
    "app_name": "Google Chrome"
  },
  "payload": {
    "button": 4
  }
}
```

Allowed bridge examples:

- `input_device`: mouse buttons, scroll bursts, drag/drop, trackpad gestures, keyboard shortcuts.
- `browser_lifecycle`: tab opened, tab closed, tab switched, download finished.
- `app_lifecycle`: app crashed, app not responding, permission prompt shown.

Disallowed bridge examples:

- raw key text
- password-field contents
- full clipboard contents in attention batches
- raw microphone audio without explicit mode
- screenshots from private apps or private browser windows

## Build Order

1. Lifecycle/input: `input_device`, `app_lifecycle`, `window_lifecycle`, `browser_lifecycle`. Implemented as opt-in collectors with best-effort snapshots and bridge support.
2. Browser page, terminal, and IDE activity: downloads, uploads, form submit, page errors, command exit, build/test failure, active file, diagnostics. Implemented as opt-in bridge collectors.
3. Accessibility, notification, calendar, communication, mail, document, creative, security, and agent-runtime activity. Implemented as opt-in bridge collectors; accessibility and security require rich-capture opt-in.
4. Native helper implementations for each platform/app: macOS Accessibility/System Events helpers, Windows UIA/WinEvent hooks, browser extensions, shell integrations, IDE extensions, calendar/mail adapters, and creative-app plugins.
5. Deep app-specific enrichment: stable element IDs, safe selected-text summaries, thread metadata, document references, render/export statuses, and structured recovery hints.
