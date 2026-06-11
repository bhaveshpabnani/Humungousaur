# Humungousaur Collector Architecture

Humungousaur collectors make the desktop agent active without turning it into a 24/7 recorder.

App, SaaS, browser-extension, IDE-plugin, and webhook source integrations are documented in
`docs/APP_COLLECTOR_ARCHITECTURE.md`. They should emit this same event envelope instead of
creating a parallel app-event pipeline.

The active-agent interpretation layer that turns collector events into reflexes,
task context, muted scopes, deep-dive requests, UI state, and main-agent
activation is documented in `docs/ACTIVE_AGENT_COLLECTOR_WORKFLOW.md`.
The deeper Reflex LLM, context-memory, event-handling, research, and desktop UI
design is documented in `docs/ACTIVE_AGENT_REFLEX_ARCHITECTURE.md`.

The rule is:

```text
Native/app source -> collector event envelope -> local SQLite WAL bus -> local consumers -> compact attention batch -> model attention decision -> optional agent action.
```

Raw telemetry must not be streamed to the LLM. Collectors emit structured local events. The runtime applies privacy policy, opt-in checks, dwell, dedupe, rate limits, durable event logging, batching, and redaction before a compact attention batch reaches the interaction harness.

## Current Runtime Contract

Collector code lives under `humungousaur/collectors`.

- `definitions.py`: source of truth for collector names, families, defaults, sensitivity, rate limits, and stimulus types.
- `envelope.py`: normalized `CollectorEventEnvelope` contract shared by Python adapters, native collectors, browser extensions, and helper bridges.
- `event_log.py`: durable SQLite WAL collector bus with accepted events, independent consumer offsets, retry state, consumer state, and dead letters.
- `schema.py`: dependency-free validation for the shared collector event envelope before events enter the durable log.
- `registry.py`: explicit collector registration layer. Every `CollectorDefinition` must have a registered runtime collector function before the registry is complete.
- `manifests.py`: source manifest layer that states each collector's source level, native helper plan, required permissions, local fallbacks, and helper health.
- `source_gate.py`: shared gate for direct app/SaaS/browser source ingestion. Once a collector profile exists, direct source events must pass collector enablement, dedupe, rate-limit, and activity-policy checks before entering the SQLite event log.
- `models.py`: `CollectorProfile`, `CollectorEvent`, and `CollectorTickResult`.
- `bridge.py`: validated compatibility ingress for native helpers, browser extensions, shell integrations, and IDE extensions. JSONL spool files are ingress only; accepted events are normalized into the SQLite collector event log before local consumers process them.
- `attention_compaction.py`: redacts collector events into compact attention payloads and generates LLM-safe batch text.
- `consumers/`: independent local consumers for attention batches, memory mirroring, UI streams, and autonomous trigger observation.
- `policies/`: reusable privacy, activity-policy payload, dwell, dedupe, and rate-limit logic applied before durable event logging.
- `adapters/app_surface_adapters.py`: bridge-backed inside-app surface collectors for AI assistants, PDFs, spreadsheets, presentations, file dialogs, and system settings.
- `adapters/browser_organization_adapters.py`: bridge-backed browser organization collectors for windows/session restore, tab groups, profiles, extensions, installed web apps, and view modes.
- `adapters/chat_collaboration_adapters.py`: bridge-backed chat collaboration workflow collectors for chat composition, threads, channel/workspace navigation, and presence/status state.
- `adapters/business_operations_adapters.py`: bridge-backed business/operations collectors for CRM, support desks, analytics dashboards, database clients, cloud consoles, and incident/on-call tools.
- `adapters/composition_adapters.py`: bridge-backed composition collectors for drafts, dictation, writing assistance, and translation.
- `adapters/content_exchange_adapters.py`: bridge-backed content exchange collectors for transfers, archives, camera/photo capture, and cross-device continuity.
- `adapters/credential_adapters.py`: bridge-backed credential workflow collectors for password managers, passkeys, autofill, and verification codes.
- `adapters/developer_tooling_adapters.py`: bridge-backed developer tooling collectors for package managers, build tools, test runners, local services, and debugger sessions.
- `adapters/document_workflow_adapters.py`: bridge-backed document workflow collectors for composition/editing, review/comments, structure/navigation, and export/publish/share.
- `manager.py`: profile persistence, ticks, source adapter orchestration, deterministic filters, event-log recording, and consumer dispatch.
- `adapters/filesystem_adapters.py`: stateful filesystem metadata polling, secret-path exclusions, create/modify/delete classification, and path-safe event signatures.
- `adapters/local_context_adapters.py`: privacy-sensitive local context collectors for clipboard, screenshots, screen OCR, video keyframes, and audio activity.
- `lifecycle.py`: lifecycle/input collector adapters with best-effort OS snapshots plus native bridge events for input, app, window, and browser lifecycle.
- `adapters/activity_adapters.py`: bridge-backed browser page, terminal, and IDE activity adapters.
- `adapters/environment_adapters.py`: bridge-backed device/session, visual state, share/drag-drop, GitHub adapters plus native best-effort downloads and Git polling.
- `adapters/file_activity_adapters.py`: file manager collectors for file operations, folder navigation, previews, and trash/recycle-bin actions; file save/rename/move and folder create/change/rename/move have best-effort local fallbacks plus the macOS `HumungousaurFileEvents` FSEvents bridge helper.
- `adapters/interaction_adapters.py`: bridge-backed direct intent, voice wakeup, meeting audio, scheduled wakeup, and channel activity adapters.
- `adapters/input_services_adapters.py`: bridge-backed input service collectors for keyboard/input-source state, IME composition, text-entry surfaces, and pasteboard workflows.
- `adapters/mail_calendar_workflow_adapters.py`: bridge-backed mail/calendar workflow collectors for composition, mailbox organization, scheduling/invites, and reminders/to-dos.
- `adapters/os_activity_adapters.py`: bridge-backed OS activity collectors for installs/updates, print/scan, launcher/search, peripherals, media, and focus/task context.
- `adapters/platform_context_adapters.py`: bridge-backed platform context collectors for permissions, location, resource pressure, storage/backup, wellbeing limits, and managed-device policy.
- `adapters/personal_workflow_adapters.py`: bridge-backed personal workflow collectors for notes, bookmarks/history, contacts, commerce, finance/wallet, and social feeds.
- `adapters/planning_collaboration_adapters.py`: bridge-backed structured work collectors for task managers, issue trackers, knowledge bases, whiteboards, forms/surveys, and learning tools.
- `adapters/presentation_workflow_adapters.py`: bridge-backed presentation workflow collectors for authoring, design, delivery, and export/share/publish.
- `adapters/productivity_adapters.py`: bridge-backed accessibility, notification, calendar, communication, mail, document, creative, security, and agent-runtime adapters.
- `adapters/realtime_collaboration_adapters.py`: bridge-backed live meeting/call collectors for meeting app state, call controls, screen-share/presentation state, and post-meeting artifacts.
- `adapters/spreadsheet_workflow_adapters.py`: bridge-backed spreadsheet workflow collectors for editing, formulas/calculation, data analysis, and import/export/share.
- `adapters/system_surface_adapters.py`: bridge-backed system UI collectors for Dock/taskbar, menu bar/tray, quick settings, and widgets.
- `adapters/ui_operation_adapters.py`: bridge-backed generic in-app operation collectors for commands, selections, navigation, and edit history.
- `adapters/workflow_environment_adapters.py`: bridge-backed connected-work collectors for cloud sync, auth/MFA, network/API issues, automations, containers/VMs, and remote sessions.
- `adapters/workspace_layout_adapters.py`: bridge-backed desktop/workspace layout collectors for Spaces, Stage Manager, window tiling, display arrangement, and app workspaces.

The manager records accepted collector envelopes into `data_dir/collector_events.sqlite3`. Local consumers then mirror safe event payloads into existing memory surfaces, build compact `attention_batch` stimuli, expose UI streams, and observe autonomy triggers. Only compact attention batches cross the LLM boundary.

The event log is also the operational surface for collector durability:

- Consumer offsets include lag against the latest sequence.
- Retry state uses delayed retry timestamps before a failed event is re-read.
- Dead letters preserve the failed event payload after repeated consumer failures.
- Retention pruning deletes only events acknowledged by known consumers, then applies age/count limits.
- Native helpers can publish health records with `helper_id`, collector, platform, status, permission state, restart count, and last-event metadata.
- `/collectors/events` and `collectors-events` query the durable stream by collector, stimulus type, and sequence.

This matches the important osquery lesson: native publishers and local subscribers should be independently registered and observable, while the event store remains durable and queryable.

## Native Collector Organization

Native collectors live outside the Python package under `native_collectors/` so each OS can use the platform-native language and packaging model while sharing one event contract.

- `native_collectors/shared/event-envelope.schema.json`: shared envelope schema.
- `native_collectors/shared/privacy-tiers.md`: native-side redaction and privacy-tier guidance.
- `native_collectors/macos`: Swift collector host and event writer for NSWorkspace, FSEvents, Finder/Quick Look metadata, browser/window/profile-store metadata, Accessibility/CoreGraphics/NSEvent system UI metadata, IOKit, SystemConfiguration, input sources, pasteboard metadata, and future media/logging collectors.
- `native_collectors/windows`: C#/.NET collector host and event writer skeleton for WMI, UI Automation, WinEvent, `ReadDirectoryChangesW`, browser profile-store metadata watches, ETW/auditing, device notifications, and media-session collectors.
- `native_collectors/linux`: Rust collector host and event writer skeleton for inotify, fanotify, DBus/AT-SPI, desktop, and device collectors.

Native helpers should emit periodic helper-health records before they emit high-volume events. A helper that lacks a required OS permission should report `permission_denied` instead of silently disappearing.

## Source Implementation Levels

Collector definitions are contracts, not proof that every stimulus has a native emitter. Each collector must state which source levels are implemented:

| Level | Meaning | Current examples |
|---|---|---|
| Local polling | Python collector derives events from local metadata snapshots. | `filesystem` emits `file_created`, `file_modified`, `file_deleted`; `downloads` polls download/export metadata; `git_activity` polls local Git state. |
| Local OS state | Python collector derives events from OS-visible state without a separate helper. | `file_operation_activity` emits best-effort `file_saved`, `file_renamed`, `file_moved`, `file_opened`, and `file_closed`; `folder_navigation_activity` emits folder create/change/rename/move; `trash_activity` emits file/folder trash moves, item delete, and bulk empty signals. |
| Native bridge | A platform/app helper emits structured JSONL/API events into the bridge. | macOS `HumungousaurFileEvents` emits FSEvents-backed file/folder operations; app-specific commands, meeting controls, chat workflow events, spreadsheet/deck workflow events. |
| Browser/IDE/app extension | An extension/plugin emits app-native events into the bridge. | browser lifecycle/page events, IDE diagnostics, Slack-like channel activity, Docs/Sheets/Slides activity. |
| Contract only | Stimulus is listed and validated but still needs a source emitter. | Any bridge-supported stimulus without a local/native helper for that platform/app yet. |

When adding a stimulus type, add or identify its source emitter in the same change whenever possible. If the source is not implemented yet, document it as bridge-only and avoid describing it as fully collected.

Required build rule: a collector change is incomplete until each new stimulus type has one of these explicitly documented source paths:

- a local polling or local OS-state implementation in its adapter
- a native helper/browser extension/app plugin that emits the bridge event
- a clear bridge-only placeholder note naming the missing emitter

## File Family Native Source Plan

The file collectors use Python polling as the safe local fallback, but the correct production source is a small native helper per OS that emits bridge events into the same collector contracts.

Recommended native lanes:

- macOS directory/file-change lane: implemented in `native_collectors/macos` as `HumungousaurMacCollectorHost`, a SwiftPM executable using File System Events for watched directory changes and shared-envelope JSONL output.
- macOS open/close lane: `macos_endpoint_security_helper` using Endpoint Security `ES_EVENT_TYPE_NOTIFY_OPEN` / `ES_EVENT_TYPE_NOTIFY_CLOSE`; this requires the Endpoint Security entitlement and should remain opt-in/privileged.
- macOS file-manager UI lane: partly implemented in `HumungousaurMacCollectorHost` using NSWorkspace/CoreGraphics metadata for Finder folder focus and Quick Look focus; richer tags, share sheet, path bar, restore, and privileged open/close still need dedicated opt-in helpers.
- Windows directory/file-change lane: `windows_read_directory_changes_helper` using `ReadDirectoryChangesW` with subtree watching and name/size/write-time filters.
- Windows open/close lane: `windows_file_audit_or_etw_helper` using file auditing or ETW where the user/admin has opted in.
- Windows file-manager UI lane: `windows_explorer_uia_helper` using UI Automation/Shell notifications for Explorer-only actions.
- Linux directory/file-change lane: `linux_inotify_helper` using `inotify` for create/modify/delete/move/open/close signals in watched trees.
- Linux broader access lane: `linux_fanotify_helper` where privileged, policy-driven access notifications are required.
- Linux file-manager UI lane: `linux_file_manager_extension_or_accessibility_helper` for Nautilus/Dolphin/Thunar-style UI actions that kernel file events cannot express.

Current implementation in `adapters/file_activity_adapters.py`:

- Bridge events remain the highest-fidelity source when a native/helper/app emitter exists.
- `script/run_macos_file_events.sh --workspace <path> --data-dir <path> --watch <path>` starts the macOS native collector host and writes shared-envelope JSONL into `data_dir/collector_spool/`.
- Local fallback detects `file_saved`, `file_renamed`, and `file_moved` from watched file signatures and filesystem identity.
- Local fallback detects `file_opened` and `file_closed` from open-handle transitions when `lsof` is available.
- Local fallback detects `folder_created`, `folder_changed`, `folder_renamed`, and `folder_moved` from watched directory metadata and filesystem identity.
- Local fallback detects `file_moved_to_trash`, `folder_moved_to_trash`, `trash_item_deleted`, and `trash_emptied` from user trash folder polling.
- `collector_status(...).capabilities.collectors.*.source_status` exposes the current fallback availability, recommended native emitters, and bridge-only gaps.

## Source Implementation Backlog

The adapter package is organized under `humungousaur/collectors/adapters/`. Core runtime files remain at `humungousaur/collectors/`.

Current real local sources:

- `active_window`, `browser`: core best-effort foreground app/browser snapshots.
- `clipboard`, `screenshot`, `screen_ocr`, `video_frame`, `audio_activity`: local context adapters with opt-in rich capture.
- `filesystem`: local polling for create/modify/delete.
- `downloads`, `git_activity`: bridge plus local polling.
- `file_operation_activity`: bridge plus macOS FSEvents helper and best-effort local `file_saved`, `file_renamed`, `file_moved`, `file_opened`, and `file_closed`.
- `folder_navigation_activity`: bridge plus macOS FSEvents helper and best-effort local `folder_created`, `folder_changed`, `folder_renamed`, and `folder_moved` from watched directory metadata.
- `trash_activity`: bridge plus best-effort local `file_moved_to_trash`, `folder_moved_to_trash`, `trash_item_deleted`, and `trash_emptied` from trash-folder polling.
- `app_lifecycle`, `window_lifecycle`, `browser_lifecycle`, `input_device`: lifecycle best-effort snapshots plus bridge enrichment; native helpers emit redacted browser foreground/navigation observations where available.
- `browser`, `browser_window_activity`, `browser_tab_group_activity`, `browser_profile_activity`, `browser_extension_activity`, `browser_web_app_activity`, `browser_view_mode_activity`, `browser_page_activity`, `bookmark_history_activity`: native helpers emit redacted browser foreground/window metadata, safe browser shortcut metadata where supported, and browser profile-store change metadata for browser profile folders; `browser_extensions/humungousaur_collector` now provides the high-fidelity WebExtension source for explicit tab, URL, form, page, extension action, download/upload, web-app, and view-mode semantics, with native messaging still reserved for browser surfaces not exposed by WebExtension APIs.
- `workspace_layout_activity`, `window_arrangement_activity`, `display_arrangement_activity`, `app_workspace_activity`: Windows and macOS native helpers emit redacted monitor topology, display-change, foreground-window geometry, Task View/virtual-desktop or Space metadata where available, and foreground app workspace transition metadata; app/desktop extensions remain the high-fidelity source for named workspaces, virtual-desktop lifecycle, app profile names, and exact layout presets.
- `terminal_activity`, `ide_activity`, `git_activity`, `github_activity`, `package_manager_activity`, `build_tool_activity`, `test_runner_activity`, `local_service_activity`, `debugger_activity`, `database_activity`, `cloud_console_activity`: macOS native helper emits redacted foreground app, process-name, local listener, Git metadata, package/build/test config, database-client, cloud-tool, and GitHub workflow metadata; shell integrations, IDE extensions, app bridges, and API connectors remain responsible for command output, logs, SQL/results, test names, stack frames, cloud resource IDs, and GitHub issue/PR content.
- `calendar_activity`, `wakeups`, `calendar_scheduling_activity`, `reminder_todo_activity`, `mail_activity`, `mail_composition_activity`, `mail_organization_activity`: macOS native helper emits redacted Mail/Calendar/Reminders foreground app, process, Mail store, and EventKit count/timing metadata; MailKit/EventKit app bridges remain responsible for exact message subjects/bodies, sender/recipient names, attendees, calendar titles, locations, notes, reminder titles, mailbox names, invites, sends, attachments, and rule/search actions.
- `voice_wakeup`, `meeting_audio`, `meeting_app_activity`, `call_control_activity`, `meeting_presentation_activity`, `meeting_artifact_activity`, `channel_activity`, `communication_activity`, `chat_composition_activity`, `chat_thread_activity`, `chat_channel_navigation_activity`, `chat_presence_activity`: Windows and macOS native helpers emit app-specific process, foreground-window, meeting-surface, and shortcut metadata for Teams, Zoom, Slack, Discord, WhatsApp, Telegram, Signal, Outlook, Skype, Webex, FaceTime, Messages, RingCentral, browser collaboration surfaces, Humungousaur voice, and Windows Voice Access; app/browser/audio/notification bridges remain the high-fidelity source for transcripts, message bodies, participants, channels, meeting titles, exact notification contents, and app-specific artifacts.
- `accessibility_context`, `selection_activity`: bridge plus macOS Accessibility focused-control metadata where permission is granted; the helper emits role/subrole, app bundle, role-path hashes, selected child counts, selected-role hashes, selected range length buckets, and control-state buckets without raw labels, values, or selected text.
- `command_activity`, `navigation_activity`, `edit_history_activity`: bridge plus macOS `NSEvent` shortcut/context-menu metadata using key codes and modifier categories only; app extensions remain the high-fidelity source for exact command names, menu item names, toolbar buttons, and in-app history checkpoints.
- `dock_taskbar_activity`, `menu_bar_tray_activity`, `quick_settings_activity`, `widget_activity`: bridge plus macOS `CGWindowListCopyWindowInfo`/`NSRunningApplication` system-surface observations for Dock, menu bar/SystemUIServer, Control Center, and Notification Center/widget windows with only hashes, buckets, and surface categories.
- `notification_activity`, `search_activity`, `media_activity`, and `wellbeing_activity`: bridge plus macOS visible-system-surface metadata for Notification Center alerts, Spotlight/search surfaces, screen-recording UI, and Screen Time/wellbeing surfaces; notification contents, query text, media contents, and limit details are omitted.
- `permission_activity`, `location_activity`, `resource_activity`, `storage_activity`, `software_activity`, `print_scan_activity`, `peripheral_activity`, `focus_task_activity`, and `policy_activity`: bridge plus macOS permission-state, time-zone/region, ProcessInfo thermal/power, disk/volume capacity, app-bundle inventory, CUPS print job, USB/display/mount, Space transition, and managed-profile metadata with protected content redacted.

Bridge-only collectors must be treated as contracts until the listed emitter exists:

| Collector family | Bridge-only collectors | Missing emitter |
|---|---|---|
| File manager enrichment | `file_preview_activity`, richer `folder_navigation_activity` actions such as opened/view/path-bar, richer `trash_activity` actions such as opened/restored, and non-local `file_operation_activity` actions such as duplicate/tag/share | macOS Endpoint Security + Finder Accessibility/NSWorkspace helpers, Windows ReadDirectoryChangesW + Explorer UIA/ETW helpers, and Linux inotify/fanotify + file-manager extension helpers emitting folder navigation, preview, trash, and rich file-operation events. |
| Browser organization/page | extension popup internals, exact tab titles, tab-group names, profile account names, and browser/store-specific runtime web-app actions beyond WebExtension APIs | Native profile-store/window helpers emit redacted metadata for browser foreground/window/profile/extension/web-app/tab-group/bookmark/history changes. `browser_extensions/humungousaur_collector` emits P0 tab, URL, page, form/upload/download, extension action, tab group, profile-context, web-app, and view-mode metadata when the user opts in; optional Chrome/Edge/Firefox native messaging hosts remain the path for browser surfaces WebExtensions cannot observe directly. |
| Workspace/layout enrichment | named Spaces/virtual desktops, desktop create/delete, exact app workspace/project/profile names, app-specific layout preset save/apply, display profile names, and visible window lists | Windows/macOS native metadata helpers emit redacted display topology, foreground window geometry, workspace shortcuts or Space metadata where available, and foreground app workspace transitions. App-specific extensions or OS desktop integrations should emit richer named workspace/layout events when the user opts in. |
| Developer workflow enrichment | command lines, terminal output, exact IDE files, diagnostics, package names, registry URLs, build targets, logs, test names, assertion text, stack frames, variable values, endpoint paths, SQL/results, cloud resource IDs, and GitHub/GitLab/Bitbucket/Azure DevOps issue/PR content | macOS helper emits redacted foreground app/window metadata, process names/categories, listener port buckets, Git metadata signatures, GitHub workflow-directory metadata, and package/build/test file-attribute signatures. Shell integration, VS Code/JetBrains/Xcode extensions, package-manager hooks, test-runner plugins, dev-server watcher, debugger adapter hooks, database-client bridges, cloud-provider/API connectors, and GitHub/GitLab/Bitbucket/Azure DevOps connectors emit richer app-native events when the user opts in. |
| Mail/calendar enrichment | exact message subjects/bodies, sender and recipient names, attachment filenames, mailbox names, calendar titles, attendees, locations, notes, reminder titles, list names, invite responses, sends, searches, labels, and rules | macOS helper emits redacted Mail/Calendar/Reminders app and process metadata, Mail store file-attribute signatures, EventKit event/reminder count buckets, and due/timing buckets. MailKit extensions, EventKit-authorized app bridges, mail-provider APIs, and calendar-provider APIs should emit richer app-native events when the user opts in. |
| OS/system-surface enrichment | exact notification text/actions, Spotlight/search queries and result paths, media track metadata, scan contents, Bluetooth names, Screen Time limit details, exact policy payloads, installer/package receipts, and privileged process/resource diagnostics | macOS helper now emits redacted public/native metadata for these collectors. App extensions, notification listeners, CUPS/native print hooks, Bluetooth-specific helpers, Screen Time/MDM connectors, and privileged diagnostics helpers are still needed for richer opt-in semantics. |
| Connected runtime/platform | cloud sync, auth/MFA, network/API, automation, containers/VMs, remote sessions | OS settings helper plus provider-specific helpers for iCloud/OneDrive/Google Drive, auth prompts, network monitors, Shortcuts/Task Scheduler, Docker/VMs, and remote desktop sources. |
| Credential workflows | credential, passkey, autofill, verification code | Password manager/browser autofill extension and OS credential/passkey prompt observer emitting redacted prompt/action metadata only. |
| Personal workflow | notes, bookmarks/history, contacts, commerce, finance/wallet, social feed | App-specific helpers/extensions for Notes/Keep/Notion, browser history/bookmark APIs, Contacts, commerce/payment surfaces, wallet apps, and social apps. |
| Structured work | task manager, issue tracker, knowledge base, whiteboard, forms/surveys, learning | App/API connectors or browser/app extensions for Jira/Linear/Trello/Asana, Confluence/Notion/Docs, Miro/FigJam, forms, and LMS/course tools. |
| Business/operations | CRM, support desk, analytics, database, cloud console, incident/on-call | Browser/app/API connectors for Salesforce/HubSpot, Zendesk/Intercom, analytics tools, DB clients, cloud consoles, PagerDuty/Opsgenie/incident tools. |
| App surfaces | AI assistant, PDF, spreadsheet, presentation, file dialog, system settings | App-specific browser/native extensions for AI tools, PDF apps, office apps, open/save panels, and settings surfaces. |
| Office workflows | document, spreadsheet, and presentation workflow collectors | Google Docs/Sheets/Slides extensions, Microsoft Office add-ins, Apple iWork helpers, LibreOffice hooks, and browser-app instrumentation emitting redacted workflow events. |
| Composition/content exchange | text composition, dictation, writing assist, translation, file transfer, archive, camera capture, continuity | Accessibility/text-service helper, dictation provider hook, writing-assist integration, translation helper, transfer/archive helpers, camera/QR helper, Handoff/continuity observer. |
| Communication/collaboration enrichment | exact transcripts, message bodies, mentions, participant names, channel/workspace names, meeting titles, notification contents, exact app artifact contents, and provider-specific call state beyond foreground/process/shortcut metadata | Windows communication app helper emits redacted app-specific process, foreground, and shortcut metadata for common communication apps. Voice listener, app/browser extensions, Calendar/Reminders/Mail adapters, notification listeners, and audio-session helpers should emit richer app-native events when the user opts in. |
| UI operations | exact command/menu/toolbar names, exact selected text, app-specific navigation semantics, autosave/revert/version checkpoints | macOS helper now emits redacted Accessibility/NSEvent metadata for focused controls, selection buckets, shortcut-driven command/navigation/edit-history events, and system surfaces. App extensions or app-specific accessibility lanes are still needed for exact in-app semantics without raw content. |
| Security/runtime | security context and agent runtime bridge enrichment | OS/browser security-surface observer and internal runtime event emitter for tool/run/approval/autonomous events. |

## Privacy Tiers

| Tier | Default | Examples | Rule |
|---|---:|---|---|
| Metadata | on where safe | active app, window title, URL title | Can be collected after dwell/dedupe/policy. |
| Sensitive metadata | off unless useful | clipboard changed, audio activity | Requires explicit collector enablement and/or rich opt-in. |
| Rich capture | off | screenshot, OCR, video keyframe, transcript | Requires explicit rich-capture opt-in and strict rate limits. |
| Bridge events | off unless bridge installed | mouse forward, tab closed, app-specific action | Native helper submits validated structured events; no raw keylogging. |

Never collect raw passwords, OTPs, secret manager contents, private browsing, or keystroke text.

## Exhaustive Collector Catalog

| Family | Collector | Stimulus Types |
|---|---|---|
| Direct intent | `direct_user` | `user_text_submitted`, `global_hotkey_pressed`, `approval_accepted`, `approval_rejected` |
| Voice | `voice_wakeup`, `audio_activity`, `meeting_audio` | `voice_activity_detected`, `wake_word_detected`, `voice_transcript_final`, `meeting_transcript_chunk`, `speaker_changed`, `call_started`, `call_ended` |
| Meeting apps | `meeting_app_activity` | `meeting_joined`, `meeting_left`, `waiting_room_joined`, `waiting_room_admitted`, `participant_joined`, `participant_left`, `breakout_room_joined`, `breakout_room_left`, `meeting_recording_started`, `meeting_recording_stopped` |
| Call controls | `call_control_activity` | `microphone_muted`, `microphone_unmuted`, `camera_enabled`, `camera_disabled`, `hand_raised`, `hand_lowered`, `reaction_sent`, `captions_enabled`, `captions_disabled`, `meeting_chat_opened` |
| Meeting presentation/share | `meeting_presentation_activity` | `screen_share_started`, `screen_share_stopped`, `window_share_started`, `window_share_stopped`, `presentation_started`, `presentation_stopped`, `presenter_changed`, `remote_control_requested`, `remote_control_granted`, `remote_control_revoked` |
| Meeting artifacts | `meeting_artifact_activity` | `meeting_recording_available`, `meeting_transcript_available`, `meeting_summary_generated`, `meeting_action_items_detected`, `meeting_notes_shared`, `meeting_whiteboard_exported`, `meeting_followup_created` |
| Device/session | `device_state` | `user_idle_state_changed`, `screen_locked`, `screen_unlocked`, `sleep_started`, `wake_started`, `battery_low`, `charger_connected`, `network_changed`, `vpn_changed`, `focus_mode_enabled` |
| Software lifecycle | `software_activity` | `installer_started`, `installer_failed`, `app_installed`, `app_uninstalled`, `app_updated`, `package_installed`, `extension_installed` |
| Print/scan | `print_scan_activity` | `print_job_started`, `print_job_completed`, `print_job_failed`, `scan_started`, `scan_completed`, `printer_selected` |
| Search/launcher | `search_activity` | `spotlight_opened`, `launcher_query_submitted`, `system_search_performed`, `app_launched_from_search`, `file_opened_from_search` |
| Peripherals | `peripheral_activity` | `external_display_connected`, `external_display_disconnected`, `usb_device_connected`, `usb_device_disconnected`, `bluetooth_device_connected`, `bluetooth_device_disconnected`, `storage_device_mounted`, `storage_device_ejected` |
| Media | `media_activity` | `media_playback_started`, `media_playback_paused`, `media_playback_stopped`, `media_track_changed`, `screen_recording_started`, `screen_recording_stopped` |
| Focus/task context | `focus_task_activity` | `focus_mode_enabled`, `focus_mode_disabled`, `task_started`, `task_completed`, `workspace_switched`, `desktop_space_changed`, `mode_changed` |
| Workspace layout | `workspace_layout_activity` | `mission_control_opened`, `workspace_overview_opened`, `desktop_space_created`, `desktop_space_deleted`, `desktop_space_switched`, `stage_manager_enabled`, `stage_manager_disabled` |
| Window arrangement | `window_arrangement_activity` | `window_tiled`, `window_snapped`, `split_view_started`, `split_view_ended`, `window_fullscreen_entered`, `window_fullscreen_exited`, `window_moved_to_display`, `window_moved_to_space` |
| Display arrangement | `display_arrangement_activity` | `display_arrangement_changed`, `display_resolution_changed`, `display_scaling_changed`, `display_rotation_changed`, `primary_display_changed`, `display_profile_changed` |
| App workspaces | `app_workspace_activity` | `app_workspace_opened`, `app_workspace_switched`, `app_workspace_restored`, `app_workspace_saved`, `layout_preset_applied`, `profile_switched` |
| Cloud sync | `cloud_sync_activity` | `sync_started`, `sync_completed`, `sync_failed`, `sync_conflict_detected`, `remote_file_changed`, `cloud_file_created`, `cloud_folder_created`, `cloud_file_renamed`, `cloud_folder_renamed`, `cloud_file_moved`, `cloud_folder_moved`, `cloud_file_deleted`, `cloud_folder_deleted`, `cloud_file_shared`, `cloud_permission_changed`, `cloud_file_restored`, `cloud_file_version_event`, `cloud_quota_warning` |
| Auth/account | `auth_activity` | `login_prompt_shown`, `oauth_flow_started`, `oauth_flow_completed`, `oauth_flow_failed`, `mfa_prompt_shown`, `sign_in_failed`, `account_switched` |
| Credentials | `credential_activity` | `password_manager_opened`, `credential_selected`, `credential_copied`, `credential_filled`, `credential_save_prompt_shown`, `credential_update_prompt_shown`, `credential_fill_failed` |
| Passkeys/security keys | `passkey_activity` | `passkey_prompt_shown`, `passkey_created`, `passkey_used`, `passkey_failed`, `biometric_auth_requested`, `security_key_requested` |
| Autofill | `autofill_activity` | `autofill_suggestion_shown`, `autofill_suggestion_accepted`, `autofill_suggestion_dismissed`, `payment_autofill_prompt_shown`, `address_autofill_prompt_shown`, `form_autofill_failed` |
| Verification codes | `verification_code_activity` | `otp_code_detected`, `otp_autofill_suggested`, `otp_autofill_accepted`, `verification_code_prompt_shown`, `verification_code_failed`, `backup_code_prompt_shown` |
| Network/API | `network_activity` | `offline_mode_detected`, `captive_portal_detected`, `dns_error`, `api_request_failed`, `api_rate_limited`, `bandwidth_spike`, `proxy_changed` |
| Automation | `automation_activity` | `shortcut_triggered`, `workflow_started`, `workflow_completed`, `workflow_failed`, `automation_prompt_shown`, `scheduled_job_started`, `scheduled_job_failed` |
| Containers/VMs | `virtual_runtime_activity` | `container_started`, `container_stopped`, `container_failed`, `image_build_started`, `image_build_failed`, `vm_started`, `vm_stopped`, `emulator_started`, `emulator_failed` |
| Remote sessions | `remote_session_activity` | `remote_session_started`, `remote_session_ended`, `screen_share_started`, `screen_share_stopped`, `remote_control_requested`, `remote_control_granted`, `remote_control_revoked` |
| Permissions/privacy | `permission_activity` | `permission_requested`, `permission_granted`, `permission_denied`, `permission_revoked`, `privacy_indicator_enabled`, `privacy_indicator_disabled` |
| Location/region | `location_activity` | `location_requested`, `location_access_started`, `location_access_stopped`, `region_changed`, `timezone_changed` |
| Resource pressure | `resource_activity` | `cpu_pressure_high`, `memory_pressure_high`, `thermal_pressure_high`, `process_hung`, `process_high_cpu`, `disk_io_pressure_high` |
| Storage/backup | `storage_activity` | `disk_space_low`, `volume_space_low`, `trash_emptied`, `cache_cleanup_started`, `cache_cleanup_completed`, `backup_started`, `backup_completed`, `backup_failed` |
| Wellbeing/app limits | `wellbeing_activity` | `break_reminder_fired`, `screen_time_limit_reached`, `app_limit_reached`, `wellbeing_nudge_shown`, `wellbeing_nudge_dismissed` |
| Policy/compliance | `policy_activity` | `device_compliance_warning`, `managed_profile_changed`, `policy_blocked_action`, `dlp_warning_shown`, `certificate_warning_shown`, `update_required` |
| Notes/checklists | `notes_activity` | `note_created`, `note_edited`, `note_deleted`, `note_pinned`, `note_shared`, `checklist_item_completed` |
| Bookmarks/history | `bookmark_history_activity` | `bookmark_added`, `bookmark_removed`, `reading_list_added`, `history_item_opened`, `history_search_performed`, `saved_tab_group_changed` |
| Contacts | `contact_activity` | `contact_opened`, `contact_created`, `contact_updated`, `contact_shared`, `address_copied`, `phone_number_clicked` |
| Commerce | `commerce_activity` | `cart_updated`, `checkout_started`, `checkout_completed`, `order_confirmation_seen`, `order_created`, `order_updated`, `order_paid`, `order_fulfilled`, `order_cancelled`, `customer_created`, `customer_updated`, `subscription_changed`, `return_started`, `refund_status_changed` |
| Finance/wallet | `finance_activity` | `payment_prompt_shown`, `payment_completed`, `payment_failed`, `wallet_opened`, `bank_transfer_started`, `invoice_opened`, `invoice_created`, `invoice_updated`, `invoice_paid`, `invoice_payment_failed`, `customer_created`, `customer_updated`, `refund_created`, `receipt_captured` |
| Social feeds | `social_feed_activity` | `feed_opened`, `post_composed`, `post_published`, `comment_received`, `follow_request_received`, `saved_post_added`, `social_notification_received` |
| Task managers | `task_manager_activity` | `task_created`, `task_updated`, `task_completed`, `task_reopened`, `task_assigned`, `task_moved`, `task_priority_changed`, `task_due_date_changed`, `task_comment_added`, `project_opened`, `project_changed` |
| Issue trackers | `issue_tracker_activity` | `issue_created`, `issue_assigned`, `issue_status_changed`, `issue_comment_received`, `issue_blocker_added`, `issue_moved`, `issue_priority_changed`, `issue_due_date_changed`, `sprint_started`, `sprint_changed`, `project_opened`, `project_changed` |
| Knowledge bases | `knowledge_base_activity` | `page_opened`, `page_created`, `page_edited`, `database_changed`, `table_changed`, `page_commented`, `page_shared`, `link_created`, `backlink_created`, `vault_opened`, `workspace_opened`, `wiki_search_performed`, `doc_link_copied` |
| Whiteboards | `whiteboard_activity` | `board_opened`, `board_edited`, `sticky_created`, `diagram_exported`, `collaborator_joined`, `whiteboard_comment_added` |
| Forms/surveys | `form_survey_activity` | `form_opened`, `form_draft_saved`, `form_submitted`, `form_validation_error`, `survey_response_received`, `approval_form_submitted` |
| Learning/courses | `learning_activity` | `lesson_started`, `lesson_completed`, `quiz_started`, `quiz_submitted`, `course_progress_changed`, `certificate_earned` |
| CRM | `crm_activity` | `record_opened`, `record_updated`, `lead_created`, `deal_stage_changed`, `customer_note_added`, `followup_scheduled` |
| Support desk | `support_desk_activity` | `ticket_opened`, `ticket_assigned`, `ticket_updated`, `ticket_replied`, `ticket_resolved`, `ticket_escalated`, `sla_breach_warning` |
| Analytics | `analytics_activity` | `dashboard_opened`, `dashboard_filter_changed`, `report_exported`, `metric_threshold_crossed`, `query_result_viewed`, `chart_drilled_down` |
| Database clients | `database_activity` | `database_connected`, `database_disconnected`, `query_started`, `query_completed`, `query_failed`, `schema_changed`, `migration_started`, `migration_failed` |
| Cloud consoles | `cloud_console_activity` | `cloud_resource_opened`, `cloud_resource_changed`, `deployment_started`, `deployment_failed`, `secret_view_attempted`, `billing_alert_seen`, `permission_error_seen` |
| Incident/on-call | `incident_activity` | `incident_declared`, `incident_acknowledged`, `incident_escalated`, `incident_resolved`, `on_call_alert_received`, `runbook_opened`, `status_page_updated` |
| File operations | `file_operation_activity` | `file_opened`, `file_closed`, `file_saved`, `file_renamed`, `file_moved`, `file_duplicated`, `file_tagged`, `file_shared_from_manager` |
| Folder navigation | `folder_navigation_activity` | `folder_opened`, `folder_changed`, `folder_created`, `folder_renamed`, `folder_moved`, `folder_view_changed`, `path_bar_used` |
| File preview | `file_preview_activity` | `quick_look_opened`, `preview_pane_opened`, `preview_next_file`, `preview_previous_file`, `file_metadata_inspected`, `file_info_panel_opened` |
| Trash/recycle bin | `trash_activity` | `file_moved_to_trash`, `folder_moved_to_trash`, `trash_opened`, `trash_item_restored`, `trash_item_deleted`, `trash_emptied` |
| AI assistants | `ai_assistant_activity` | `ai_chat_opened`, `ai_prompt_submitted`, `ai_response_received`, `ai_file_context_attached`, `ai_tool_call_started`, `ai_tool_call_failed`, `ai_code_suggestion_accepted`, `ai_code_suggestion_rejected`, `ai_suggestion_accepted`, `ai_model_error`, `ai_tool_error`, `ai_conversation_exported` |
| PDFs | `pdf_activity` | `pdf_opened`, `pdf_annotated`, `pdf_search_performed`, `pdf_form_filled`, `pdf_signature_requested`, `pdf_signed`, `pdf_exported` |
| Spreadsheets | `spreadsheet_activity` | `workbook_opened`, `cell_range_edited`, `formula_error_detected`, `pivot_table_changed`, `chart_updated`, `csv_imported`, `workbook_exported` |
| Spreadsheet editing | `spreadsheet_editing_activity` | `cell_range_selected`, `cell_range_edited`, `cell_range_filled`, `row_inserted`, `row_deleted`, `column_inserted`, `column_deleted`, `sheet_created`, `sheet_renamed`, `sheet_deleted` |
| Spreadsheet formulas | `spreadsheet_formula_activity` | `formula_entered`, `formula_edited`, `formula_error_detected`, `formula_error_resolved`, `named_range_created`, `named_range_updated`, `calculation_started`, `calculation_completed`, `calculation_failed` |
| Spreadsheet analysis | `spreadsheet_data_analysis_activity` | `sort_applied`, `filter_applied`, `filter_cleared`, `pivot_table_created`, `pivot_table_changed`, `chart_created`, `chart_updated`, `data_validation_changed`, `conditional_format_changed` |
| Spreadsheet import/export | `spreadsheet_import_export_activity` | `csv_imported`, `data_connection_refreshed`, `data_connection_failed`, `workbook_export_started`, `workbook_exported`, `workbook_export_failed`, `sheet_shared`, `permissions_changed`, `workbook_submitted` |
| Presentations | `presentation_activity` | `deck_opened`, `slide_edited`, `slideshow_started`, `slideshow_ended`, `speaker_notes_edited`, `deck_exported` |
| Presentation authoring | `presentation_authoring_activity` | `slide_created`, `slide_edited`, `slide_deleted`, `slide_duplicated`, `slide_reordered`, `speaker_notes_edited`, `outline_edited`, `object_inserted`, `object_edited` |
| Presentation design | `presentation_design_activity` | `theme_applied`, `layout_changed`, `master_slide_edited`, `transition_changed`, `animation_added`, `animation_removed`, `media_inserted`, `chart_inserted`, `accessibility_check_run` |
| Presentation delivery | `presentation_delivery_activity` | `slideshow_started`, `slideshow_ended`, `presenter_view_opened`, `presenter_view_closed`, `slide_advanced`, `slide_rewound`, `laser_pointer_used`, `rehearsal_started`, `rehearsal_completed` |
| Presentation export/share | `presentation_export_activity` | `deck_export_started`, `deck_exported`, `deck_export_failed`, `deck_shared`, `deck_permissions_changed`, `deck_publish_started`, `deck_publish_completed`, `handout_created`, `recording_exported` |
| File dialogs | `file_dialog_activity` | `open_panel_shown`, `save_panel_shown`, `file_selected`, `folder_selected`, `save_confirmed`, `import_started`, `export_started` |
| System settings | `system_settings_activity` | `settings_pane_opened`, `setting_changed`, `display_setting_changed`, `sound_setting_changed`, `keyboard_shortcut_changed`, `default_app_changed`, `accessibility_setting_changed` |
| Text composition | `text_composition_activity` | `composition_started`, `composition_submitted`, `composition_abandoned`, `draft_autosaved`, `snippet_inserted`, `template_inserted`, `text_expansion_used` |
| Dictation | `dictation_activity` | `dictation_started`, `dictation_stopped`, `dictation_transcript_ready`, `dictation_error`, `voice_typing_started`, `voice_typing_stopped` |
| Writing assist | `writing_assist_activity` | `spellcheck_suggestion_shown`, `spellcheck_suggestion_accepted`, `grammar_suggestion_shown`, `grammar_suggestion_accepted`, `autocorrect_applied`, `predictive_text_accepted`, `rewrite_suggestion_accepted` |
| Translation | `translation_activity` | `translation_offered`, `translation_requested`, `translation_completed`, `translation_failed`, `language_detected`, `translated_text_inserted` |
| File transfer | `file_transfer_activity` | `upload_started`, `upload_completed`, `upload_failed`, `file_transfer_started`, `file_transfer_completed`, `file_transfer_failed`, `airdrop_sent`, `airdrop_received`, `nearby_share_sent`, `nearby_share_received`, `network_share_connected`, `network_share_disconnected` |
| Archives | `archive_activity` | `archive_created`, `archive_extracted`, `compression_started`, `compression_failed`, `extraction_started`, `extraction_failed`, `archive_encrypted`, `archive_password_requested` |
| Camera/photo capture | `camera_capture_activity` | `camera_capture_started`, `camera_capture_stopped`, `photo_captured`, `photo_imported`, `video_recording_started`, `video_recording_stopped`, `qr_code_scanned` |
| Continuity | `continuity_activity` | `handoff_started`, `handoff_completed`, `universal_clipboard_received`, `phone_call_relay_started`, `phone_call_relay_ended`, `sms_relay_received`, `mobile_hotspot_connected`, `mobile_hotspot_disconnected` |
| Commands | `command_activity` | `command_palette_opened`, `command_executed`, `menu_item_selected`, `context_menu_opened`, `context_menu_item_selected`, `toolbar_button_pressed`, `shortcut_action_triggered` |
| Selection | `selection_activity` | `item_selected`, `multi_selection_changed`, `text_selection_changed`, `list_row_selected`, `table_cell_selected`, `canvas_object_selected`, `inspector_selection_changed` |
| In-app navigation | `navigation_activity` | `sidebar_item_selected`, `breadcrumb_clicked`, `in_app_tab_switched`, `pane_switched`, `in_app_back`, `in_app_forward`, `search_result_opened` |
| Edit history | `edit_history_activity` | `undo_performed`, `redo_performed`, `autosave_completed`, `manual_save_completed`, `revert_performed`, `version_restored`, `history_checkpoint_created` |
| Dock/taskbar | `dock_taskbar_activity` | `dock_item_clicked`, `taskbar_item_clicked`, `dock_item_pinned`, `dock_item_unpinned`, `taskbar_item_pinned`, `taskbar_item_unpinned`, `dock_badge_changed`, `taskbar_badge_changed`, `jump_list_opened` |
| Menu bar/tray | `menu_bar_tray_activity` | `menu_bar_item_clicked`, `system_tray_item_clicked`, `status_item_opened`, `tray_menu_opened`, `tray_notification_clicked`, `background_app_menu_opened`, `status_indicator_changed` |
| Quick settings | `quick_settings_activity` | `control_center_opened`, `quick_settings_opened`, `wifi_toggle_changed`, `bluetooth_toggle_changed`, `do_not_disturb_changed`, `brightness_changed`, `volume_changed`, `screen_mirroring_changed` |
| Widgets | `widget_activity` | `widget_panel_opened`, `widget_clicked`, `widget_added`, `widget_removed`, `widget_refreshed`, `widget_alert_seen` |
| Input device | `input_device` | `mouse_clicked`, `mouse_double_clicked`, `mouse_right_clicked`, `mouse_forward`, `mouse_back`, `mouse_scroll_burst`, `mouse_drag_started`, `mouse_drag_dropped`, `trackpad_gesture`, `keyboard_shortcut_pressed` |
| Keyboard/input source | `keyboard_input_activity` | `input_source_changed`, `keyboard_layout_changed`, `keyboard_shortcut_conflict_detected`, `modifier_key_remapped`, `key_repeat_changed`, `caps_lock_toggled`, `function_key_mode_changed`, `hardware_keyboard_connected`, `hardware_keyboard_disconnected` |
| IME/composition | `ime_activity` | `ime_composition_started`, `ime_candidate_window_shown`, `ime_candidate_selected`, `ime_composition_committed`, `ime_composition_cancelled`, `ime_conversion_failed`, `language_input_switched` |
| Text input surfaces | `text_input_surface_activity` | `text_field_focused`, `secure_text_field_focused`, `multiline_editor_focused`, `search_field_focused`, `form_field_autofocused`, `input_validation_error`, `input_submit_attempted` |
| Pasteboard workflows | `pasteboard_workflow_activity` | `copy_performed`, `cut_performed`, `paste_performed`, `paste_and_match_style_performed`, `clipboard_manager_opened`, `clipboard_history_item_selected`, `clipboard_cleared` |
| App lifecycle | `app_lifecycle` | `app_opened`, `app_closed`, `app_focused`, `app_hidden`, `app_crashed`, `app_not_responding`, `permission_prompt_shown` |
| Window lifecycle | `active_window`, `window_lifecycle` | `active_window_changed`, `window_opened`, `window_closed`, `window_focused`, `window_moved`, `window_resized`, `window_minimized`, `window_title_changed` |
| Screen/vision | `screenshot`, `screen_ocr`, `video_frame`, `visual_state` | `screenshot_captured`, `screen_text_changed`, `video_keyframe_captured`, `error_banner_visible`, `toast_visible`, `modal_visible`, `loading_spinner_stuck` |
| Accessibility | `accessibility_context` | `focused_control_changed`, `selected_text_changed`, `button_available`, `form_field_focused`, `menu_opened`, `table_row_selected`, `checkbox_toggled` |
| Browser lifecycle | `browser`, `browser_lifecycle` | `browser_tab_changed`, `browser_tab_opened`, `browser_tab_closed`, `browser_tab_switched`, `browser_url_changed`, `browser_title_changed`, `browser_reloaded`, `browser_back`, `browser_forward` |
| Browser windows/session | `browser_window_activity` | `browser_window_opened`, `browser_window_closed`, `browser_window_focused`, `browser_window_minimized`, `browser_window_fullscreen_entered`, `browser_window_fullscreen_exited`, `browser_session_restored`, `recently_closed_window_reopened` |
| Browser tab groups | `browser_tab_group_activity` | `tab_group_created`, `tab_group_renamed`, `tab_group_color_changed`, `tab_group_collapsed`, `tab_group_expanded`, `tab_group_saved`, `tab_group_restored`, `tab_moved_to_group`, `tab_removed_from_group` |
| Browser profiles | `browser_profile_activity` | `browser_profile_switched`, `browser_profile_created`, `browser_profile_signed_in`, `browser_profile_signed_out`, `browser_sync_enabled`, `browser_sync_disabled`, `guest_profile_opened`, `private_window_opened` |
| Browser extensions | `browser_extension_activity` | `extension_action_clicked`, `extension_popup_opened`, `extension_installed`, `extension_removed`, `extension_enabled`, `extension_disabled`, `extension_permission_requested`, `extension_error_reported` |
| Browser web apps | `browser_web_app_activity` | `web_app_installed`, `web_app_uninstalled`, `web_app_opened`, `web_app_closed`, `web_app_windowed`, `web_app_offline_ready`, `web_app_notification_permission_requested`, `web_app_badge_changed` |
| Browser view modes | `browser_view_mode_activity` | `reader_mode_enabled`, `reader_mode_disabled`, `find_in_page_performed`, `page_zoom_changed`, `page_muted`, `page_unmuted`, `picture_in_picture_started`, `picture_in_picture_stopped`, `page_translation_offered`, `page_translation_accepted` |
| Browser page | `browser_page_activity` | `link_clicked`, `form_changed`, `form_submitted`, `file_uploaded`, `download_started`, `download_finished`, `page_error`, `console_error`, `selected_page_text_changed` |
| Clipboard/share | `clipboard`, `share_activity` | `clipboard_changed`, `clipboard_file_changed`, `clipboard_image_changed`, `clipboard_url_changed`, `share_sheet_opened`, `drag_drop_file`, `drag_drop_text` |
| Filesystem | `filesystem`, `downloads` | `file_created`, `file_modified`, `file_deleted`, `downloaded_file`, `exported_file`, `mounted_volume_changed` |
| Notifications | `notification_activity` | `notification_received`, `notification_clicked`, `notification_dismissed`, `critical_alert_received`, `reminder_fired` |
| Calendar/time | `calendar_activity`, `wakeups` | `meeting_starting`, `meeting_started`, `meeting_ended`, `deadline_near`, `scheduled_wakeup_due`, `followup_due` |
| Calendar scheduling | `calendar_scheduling_activity` | `calendar_event_created`, `calendar_event_updated`, `calendar_event_deleted`, `calendar_event_rescheduled`, `calendar_invite_received`, `calendar_invite_accepted`, `calendar_invite_declined`, `calendar_invite_tentative`, `calendar_availability_checked` |
| Reminders/to-dos | `reminder_todo_activity` | `reminder_created`, `reminder_updated`, `reminder_completed`, `reminder_snoozed`, `reminder_deleted`, `todo_created`, `todo_completed`, `todo_due_date_changed`, `todo_list_changed` |
| Communication | `channel_activity` | `message_received`, `mention_received`, `dm_received`, `thread_reply_received`, `reaction_added`, `message_sent`, `draft_created`, `call_invite_received`, `channel_unread_changed` |
| Chat composition | `chat_composition_activity` | `chat_draft_started`, `chat_draft_updated`, `chat_message_sent`, `chat_message_edited`, `chat_message_deleted`, `chat_attachment_added`, `chat_attachment_removed`, `slash_command_used`, `emoji_picker_opened` |
| Chat threads | `chat_thread_activity` | `thread_opened`, `thread_followed`, `thread_muted`, `thread_reply_started`, `thread_reply_sent`, `thread_resolved`, `thread_saved`, `thread_unread_changed` |
| Chat channel navigation | `chat_channel_navigation_activity` | `chat_workspace_switched`, `chat_channel_opened`, `chat_channel_joined`, `chat_channel_left`, `chat_channel_muted`, `chat_channel_pinned`, `chat_channel_search_performed`, `chat_saved_item_opened` |
| Chat presence/status | `chat_presence_activity` | `chat_status_changed`, `chat_status_cleared`, `presence_changed`, `do_not_disturb_scheduled`, `do_not_disturb_enabled`, `do_not_disturb_disabled`, `availability_set`, `notification_preference_changed` |
| Terminal/dev | `terminal_activity` | `terminal_command_started`, `terminal_command_finished`, `terminal_command_failed`, `build_started`, `build_failed`, `tests_started`, `tests_failed`, `server_started`, `server_crashed` |
| IDE/code | `ide_activity` | `file_opened_in_ide`, `diagnostic_added`, `diagnostic_resolved`, `breakpoint_hit`, `debug_session_started`, `git_branch_changed`, `commit_created`, `merge_conflict_detected` |
| Package managers | `package_manager_activity` | `dependency_install_started`, `dependency_install_completed`, `dependency_install_failed`, `dependency_update_available`, `dependency_audit_warning`, `dependency_conflict_detected`, `lockfile_changed`, `environment_setup_failed` |
| Build tools | `build_tool_activity` | `build_task_started`, `build_task_completed`, `build_task_failed`, `compile_warning_detected`, `compile_error_detected`, `build_cache_cleared`, `build_config_changed`, `artifact_generated` |
| Test runners | `test_runner_activity` | `test_suite_started`, `test_suite_completed`, `test_suite_failed`, `test_case_failed`, `test_flake_detected`, `coverage_report_generated`, `coverage_threshold_failed`, `snapshot_test_updated` |
| Local services | `local_service_activity` | `dev_server_started`, `dev_server_stopped`, `dev_server_crashed`, `port_conflict_detected`, `service_health_changed`, `local_endpoint_opened`, `log_error_seen`, `hot_reload_failed` |
| Debuggers | `debugger_activity` | `debugger_attached`, `debugger_detached`, `debugger_paused`, `debugger_resumed`, `breakpoint_added`, `breakpoint_removed`, `exception_breakpoint_hit`, `watch_expression_failed` |
| Git/code hosting | `git_activity`, `github_activity`, `code_hosting_activity` | `git_branch_changed`, `commit_created`, `pr_opened`, `pr_updated`, `review_requested`, `review_submitted`, `review_approved`, `review_changes_requested`, `pr_merged`, `merge_ready`, `branch_created`, `branch_deleted`, `commit_pushed`, `ci_started`, `ci_failed`, `ci_passed`, `ci_canceled`, `issue_assigned`, `comment_received` |
| Documents | `document_activity` | `doc_opened`, `doc_edited`, `comment_added`, `suggestion_received`, `export_pdf_created`, `spreadsheet_formula_error`, `slide_deck_presented` |
| Document composition | `document_composition_activity` | `document_draft_started`, `document_edited`, `document_section_edited`, `document_outline_updated`, `document_style_applied`, `document_template_applied`, `document_citation_inserted`, `document_media_inserted`, `document_saved` |
| Document review | `document_review_activity` | `document_comment_added`, `document_comment_replied`, `document_comment_resolved`, `document_suggestion_received`, `document_suggestion_accepted`, `document_suggestion_rejected`, `tracked_changes_enabled`, `tracked_changes_disabled`, `document_review_requested`, `document_mention_added` |
| Document structure | `document_structure_activity` | `document_heading_changed`, `document_section_added`, `document_section_moved`, `document_page_break_inserted`, `document_toc_updated`, `document_footnote_added`, `document_header_footer_edited`, `document_outline_opened`, `document_navigation_pane_used` |
| Document export/publish | `document_export_publish_activity` | `document_export_started`, `document_export_completed`, `document_export_failed`, `document_print_preview_opened`, `document_publish_started`, `document_publish_completed`, `document_share_link_created`, `document_permissions_changed`, `document_submitted` |
| Creative apps | `creative_activity` | `canvas_selection_changed`, `frame_exported`, `asset_imported`, `render_started`, `render_finished`, `timeline_marker_changed` |
| Mail | `mail_activity` | `email_received`, `important_email_received`, `email_opened`, `draft_started`, `attachment_downloaded`, `send_failed` |
| Mail composition | `mail_composition_activity` | `email_draft_started`, `email_draft_updated`, `email_reply_started`, `email_forward_started`, `email_sent`, `email_send_scheduled`, `email_send_cancelled`, `email_attachment_added`, `email_attachment_removed` |
| Mail organization | `mail_organization_activity` | `email_archived`, `email_deleted`, `email_moved`, `email_labeled`, `email_flagged`, `email_unread_marked`, `email_search_performed`, `mailbox_filter_changed`, `mail_rule_applied` |
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

Some events cannot be collected reliably from Python without OS permissions or browser extensions. Native helpers, browser extensions, IDE extensions, and shell integrations should prefer the validated bridge endpoint or CLI helper:

```bash
python -m humungousaur collectors-bridge-event \
  --collector terminal_activity \
  --stimulus-type tests_failed \
  --text "Tests failed in backend suite." \
  --metadata-json '{"app_name":"Terminal"}'
```

```http
POST /collectors/bridge
Content-Type: application/json

{
  "collector": "terminal_activity",
  "stimulus_type": "tests_failed",
  "text": "Tests failed in backend suite.",
  "metadata": {
    "app_name": "Terminal"
  },
  "payload": {
    "summary": "2 tests failed"
  }
}
```

The bridge validates collector names and allowed stimulus types before appending. The response is an acknowledgement only; it does not echo raw payload details.

The durable underlying format remains JSONL at:

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
- `keyboard_input_activity`, `ime_activity`, `text_input_surface_activity`, and `pasteboard_workflow_activity`: input source/layout changes, IME candidate workflows, focused text-entry surfaces, secure field focus, copy/cut/paste, clipboard manager, and clipboard history selection with typed text and clipboard values blocked.
- `browser_lifecycle`: tab opened, tab closed, tab switched, reload, back, and forward.
- `browser_window_activity`, `browser_tab_group_activity`, `browser_profile_activity`, `browser_extension_activity`, `browser_web_app_activity`, and `browser_view_mode_activity`: browser windows/session restore, tab groups, profile/private-window/sync state, extension actions/permissions/errors, installed web apps/PWAs, reader/find/zoom/mute/PiP/translation view modes.
- `app_lifecycle`: app opened, closed, focused, hidden, crashed, not responding, and permission prompt shown.
- `window_lifecycle`: window opened, closed, focused, moved, resized, minimized, and title changed.
- `workspace_layout_activity`, `window_arrangement_activity`, `display_arrangement_activity`, and `app_workspace_activity`: desktop Spaces, Mission Control/overview, Stage Manager, tiling/snapping/split-view/fullscreen, display layout changes, and app workspace/profile switches.
- `device_state`: lock, unlock, sleep, wake, network, VPN, focus-mode, and battery changes.
- `software_activity`, `print_scan_activity`, `search_activity`, `peripheral_activity`, `media_activity`, and `focus_task_activity`: app install/update, print/scan, launcher/search, external-device, playback/recording, and task/focus transitions.
- `cloud_sync_activity`, `auth_activity`, `network_activity`, `automation_activity`, `virtual_runtime_activity`, and `remote_session_activity`: cloud-drive state, login/MFA, network/API issues, shortcuts/jobs, containers/VMs, and remote/screen-share sessions.
- `credential_activity`, `passkey_activity`, `autofill_activity`, and `verification_code_activity`: password managers, passkeys, security keys, browser/app autofill, OTP prompts, and backup-code flows with values blocked.
- `permission_activity`, `location_activity`, `resource_activity`, `storage_activity`, `wellbeing_activity`, and `policy_activity`: permission/privacy prompts, location/region, CPU/memory/thermal pressure, storage/backup, screen-time/app-limit, and managed-device policy context.
- `notes_activity`, `bookmark_history_activity`, `contact_activity`, `commerce_activity`, `finance_activity`, and `social_feed_activity`: personal notes/checklists, bookmarks/history, contacts, shopping/subscriptions, payment/wallet flows, and social feed events.
- `task_manager_activity`, `issue_tracker_activity`, `knowledge_base_activity`, `whiteboard_activity`, `form_survey_activity`, and `learning_activity`: structured task/project planning, issue trackers, wikis, whiteboards, forms/surveys, and learning/course tools.
- `crm_activity`, `support_desk_activity`, `analytics_activity`, `database_activity`, `cloud_console_activity`, and `incident_activity`: CRM/customer work, support tickets, dashboards, database clients, cloud consoles, and incident/on-call operations. Non-browser app source packages now expose metadata-first `/collectors/data-analytics` and `/collectors/operations` ingress for these domains.
- `creative_activity` and `whiteboard_activity`: design files, prototypes, components, exports, boards, stickies, collaborators, and comments. The `/collectors/design` source package maps Figma, FigJam, Miro, Canva, Sketch, and Adobe XD metadata into these collectors.
- `file_operation_activity`, `folder_navigation_activity`, `file_preview_activity`, and `trash_activity`: file manager intent for opening/closing/saving/renaming/moving files, browsing folders, Quick Look/preview, info panels, and trash/recycle-bin actions. The macOS `HumungousaurFileEvents` helper emits FSEvents-backed file save/rename/move and folder create/change/rename/move bridge events; Python fallbacks also derive those events from metadata snapshots and derive open/close from OS open-handle transitions when supported. `trash_activity` locally emits file/folder moved-to-trash, item delete, and empty-trash signals. Duplicate/tag/share, precise folder-open/navigation, preview, restore, and privileged open/close still require Finder/Accessibility, Endpoint Security, Windows Explorer/UIA/ETW, or Linux file-manager/fanotify helpers.
- `ai_assistant_activity`, `pdf_activity`, `spreadsheet_activity`, `presentation_activity`, `file_dialog_activity`, and `system_settings_activity`: inside-app work surfaces for AI tools, PDFs, spreadsheets, slide decks, open/save panels, and settings.
- `spreadsheet_editing_activity`, `spreadsheet_formula_activity`, `spreadsheet_data_analysis_activity`, and `spreadsheet_import_export_activity`: workbook editing, formulas/calculation, sorts/filters/pivots/charts/validation/formatting, imports/exports/data connections/sharing with workbook names, sheet names, ranges, formulas, cell values, labels, filenames, links, recipients, destinations, and connection details blocked.
- `presentation_authoring_activity`, `presentation_design_activity`, `presentation_delivery_activity`, and `presentation_export_activity`: slide authoring, speaker notes, outlines, themes/layouts/animations/media, slideshow/presenter/rehearsal, and deck export/share/publish with deck titles, slide text, speaker notes, asset names, filenames, links, recipients, handouts, and recordings blocked.
- `text_composition_activity`, `dictation_activity`, `writing_assist_activity`, and `translation_activity`: drafts, snippets, templates, text expansion, dictation/voice typing, spelling/grammar/autocorrect, predictive text, rewrites, and translation flows.
- `file_transfer_activity`, `archive_activity`, `camera_capture_activity`, and `continuity_activity`: uploads/transfers, archives, camera/photo capture, QR scans, Handoff, universal clipboard, phone/SMS relay, and mobile hotspot changes.
- `command_activity`, `selection_activity`, `navigation_activity`, and `edit_history_activity`: generic in-app operations emitted by accessibility/native helpers, covering menus, command palettes, toolbar buttons, selections, panes, tabs, undo/redo, saves, and version restores.
- `dock_taskbar_activity`, `menu_bar_tray_activity`, `quick_settings_activity`, and `widget_activity`: system UI surfaces for app launching/switching, pinned items, badges, tray/status menus, quick toggles, screen mirroring, and widgets.
- `visual_state`: error banners, toasts, modals, and stuck loaders summarized by a trusted UI helper.
- `downloads`: downloaded files, exported files, and mounted-volume changes; native polling baselines configured watch paths or `~/Downloads`.
- `filesystem`: native polling baselines configured watch paths, then emits create, modify, and delete events without reading file contents.
- `package_manager_activity`, `build_tool_activity`, `test_runner_activity`, `local_service_activity`, and `debugger_activity`: dependency installs/conflicts/audits, build tasks/errors/artifacts, test failures/flakes/coverage/snapshots, dev-server/port/log/hot-reload state, and debugger pause/exception/watch events with package names, paths, logs, test names, stack frames, and variable values blocked.
- `git_activity`, `github_activity`, and `code_hosting_activity`: local branch, conflict, commit, stash, rebase, merge, PR/MR, review, issue, CI, and merge-ready changes; local Git also polls branch, HEAD, dirty, clean, and conflict transitions.
- `calendar_scheduling_activity`, `reminder_todo_activity`, `mail_composition_activity`, and `mail_organization_activity`: calendar creation/update/reschedule/invites/availability, reminders/to-dos, mail drafts/replies/sends/attachments, and mailbox archive/move/label/search/rules with subjects, recipients, bodies, attendees, locations, notes, reminder titles, queries, and labels blocked.
- `chat_composition_activity`, `chat_thread_activity`, `chat_channel_navigation_activity`, and `chat_presence_activity`: chat drafts/sends/edits/attachments/slash commands, thread opens/replies/saves/unreads, workspace/channel navigation/searches, and status/presence/DND changes with message bodies, recipients, thread titles, participants, channel/workspace names, search terms, and custom status text blocked.
- `document_composition_activity`, `document_review_activity`, `document_structure_activity`, and `document_export_publish_activity`: document drafting/editing/styling/citations/media, comments/suggestions/review requests, headings/sections/outlines, and exports/publishing/sharing with document text, titles, paths, comments, reviewer names, selected text, filenames, links, recipients, and permission details blocked.
- `direct_user`, `voice_wakeup`, `meeting_audio`, `meeting_app_activity`, `call_control_activity`, `meeting_presentation_activity`, `meeting_artifact_activity`, `wakeups`, and `channel_activity`: explicit hotkeys/submissions, voice activation, meeting/call summaries, meeting app/control/share/artifact events, due wakeups, and channel-native message events.

Allowed bridge examples:

- mouse forward/back and scroll burst events with no coordinates unless needed for accessibility recovery
- browser tab opened, closed, switched, grouped, or muted events with URLs redacted by policy when sensitive
- chat draft started, thread opened, channel search performed, and status changed events with bodies, names, queries, and custom status text omitted
- document comment added, suggestion received, section moved, and export completed events with document text, titles, file paths, links, and reviewer identities omitted
- spreadsheet formula error, pivot changed, chart updated, data connection failed, and workbook exported events with formulas, cell values, labels, filenames, and connection details omitted
- presentation slideshow started, speaker notes edited, animation added, accessibility check run, and deck shared events with slide contents, notes, asset names, filenames, and links omitted
- app-specific save/export/share/command events with file contents and selected values omitted
- meeting mute, camera, hand raise, screen-share state, and artifact availability events with participant names and transcript text omitted

Disallowed bridge examples:

- raw key text
- password-field contents
- full clipboard contents in attention batches
- raw microphone audio without explicit mode
- screenshots from private apps or private browser windows

## Build Order

1. Lifecycle/input: `input_device`, `keyboard_input_activity`, `ime_activity`, `text_input_surface_activity`, `pasteboard_workflow_activity`, `app_lifecycle`, `window_lifecycle`, `browser_lifecycle`. Implemented as opt-in collectors with best-effort snapshots and bridge support for richer native events; IME, text-entry, and pasteboard workflows require rich-capture opt-in because candidate text, field values, and clipboard values can expose private content.
2. Browser organization: windows/session restore, tab groups, profile/private-window/sync state, extension actions/permissions/errors, installed web apps/PWAs, and reader/find/zoom/mute/PiP/translation view modes. Implemented as opt-in bridge collectors with native metadata helpers for foreground/window/profile-store changes where available; most require rich-capture opt-in because labels, accounts, extension names, origins, find queries, and page contents can expose private context.
3. Browser page, terminal, IDE, and developer tooling activity: downloads, uploads, form submit, page errors, command exit, coarse build/test/server failures, active files, diagnostics, package managers, build tools, test runners, local dev services, and debugger sessions. Implemented as opt-in bridge collectors; developer-tooling collectors require rich-capture opt-in because package names, target names, failing test names, logs, endpoint paths, stack frames, and variable values can expose private project internals.
4. Accessibility, notification, calendar, mail/calendar workflow, communication, chat collaboration workflow, mail, document workflow, document, creative, security, and agent-runtime activity. Implemented as opt-in bridge collectors; accessibility, security, and workflow-level mail/calendar/chat collaboration/document collectors require rich-capture opt-in because UI values, subjects, recipients, bodies, attendees, locations, notes, reminder text, labels, channel/thread names, searches, status text, document text, comments, titles, paths, links, and queries can expose private content.
5. Device/session, visual state, share/drag-drop, downloads, Git, and GitHub activity. Implemented as opt-in bridge collectors; downloads and local Git now also have native polling baselines, while visual and share collectors require rich-capture opt-in.
6. OS activity: software installs/updates, print/scan, search/launcher, peripherals, media, and focus/task context. Implemented as opt-in bridge collectors; search activity requires rich-capture opt-in because queries can expose intent.
7. Workspace layout and multitasking: Mission Control/overview, Spaces/virtual desktops, Stage Manager, window tiling/snapping/split-view/fullscreen, display arrangement, and app workspaces/profiles. Implemented as opt-in bridge collectors; most require rich-capture opt-in because workspace names, visible windows, window titles, and restored contents can expose private context.
8. Connected work/runtime activity: cloud sync, auth/MFA, network/API failures, automations, containers/VMs, and remote sessions. Implemented as opt-in bridge collectors; auth and remote-session activity require rich-capture opt-in because they can expose credentials, codes, or shared-screen context.
9. Credential workflows: password managers, credential fill/copy/save/update prompts, passkeys, biometrics, security keys, autofill, OTP prompts, and backup-code flows. Implemented as opt-in bridge collectors with rich-capture opt-in; values, vault items, key material, OTPs, and message contents must never enter attention batches.
10. Platform context: permissions/privacy indicators, location/region, resource pressure, storage/backup, wellbeing/app limits, and policy/compliance. Implemented as opt-in bridge collectors; permission and location activity require rich-capture opt-in because prompts and coordinates can expose sensitive context.
11. Personal workflow: notes, bookmarks/history, contacts, commerce, finance/wallet, and social feeds. Implemented as opt-in bridge collectors with rich-capture opt-in because these surfaces expose private intent, relationships, addresses, purchases, payments, and social content.
12. Structured work collaboration: task managers, issue trackers, knowledge bases, whiteboards, forms/surveys, and learning/course tools. Implemented as opt-in bridge collectors; most require rich-capture opt-in because titles, comments, wiki pages, forms, and boards expose private work content.
13. Business/operations: CRM, support desks, analytics dashboards, database clients, cloud consoles, and incident/on-call tools. Implemented as opt-in bridge collectors with app-source ingress for `business_operations`, `data_analytics`, and `operations`; rich-capture opt-in remains required because these surfaces expose customer data, SQL/results, cloud identifiers, logs, and incident details.
14. File manager activity: open/close/save/rename/move/duplicate/tag/share file operations, folder navigation, Quick Look/preview, info panels, and trash/recycle-bin actions. `file_operation_activity` and `folder_navigation_activity` now have a macOS FSEvents bridge helper plus local fallbacks for save/rename/move and folder create/change/rename/move; open/close remains best-effort from open-handle state until a privileged helper is installed. All file activity requires rich-capture opt-in because paths, filenames, tags, preview contents, and item details can expose private content.
15. Inside-app surfaces and office workflows: AI assistants, PDFs, spreadsheets, spreadsheet workflows, presentations, presentation workflows, file dialogs, and system settings. Implemented as opt-in bridge collectors; most require rich-capture opt-in because prompts, document text, sheet values, formulas, workbook names, slide text, slide notes, deck titles, share links, and selected file paths can expose private content.
16. Text composition: drafts, snippets, templates, text expansion, dictation/voice typing, spelling/grammar/autocorrect, predictive text, rewrites, and translation. Implemented as opt-in bridge collectors with rich-capture opt-in because body text, transcripts, suggestions, and translated text can expose private content.
17. Content exchange: uploads/transfers, archive/compression/extraction, camera/photo capture, QR scans, Handoff, universal clipboard, phone/SMS relay, and mobile hotspot changes. Implemented as opt-in bridge collectors with rich-capture opt-in because filenames, recipients, archive passwords, media, QR payloads, device names, and message bodies can expose private content.
18. Generic UI operations: command palettes, menus, context menus, toolbar buttons, selection changes, in-app navigation, undo/redo, saves, reverts, and version restores. Implemented as opt-in bridge collectors with rich-capture opt-in because command labels, selected values, route labels, and version details can expose private content.
19. System UI surfaces: Dock/taskbar, menu bar/system tray, Control Center/quick settings, and widgets. Implemented as opt-in bridge collectors; most require rich-capture opt-in because labels, badges, tray payloads, widget content, and screen-mirroring state can expose private context.
20. Real-time collaboration: meeting app lifecycle, call controls, screen-share/presentation state, post-meeting recordings/transcripts/summaries/action items, direct intent, voice wakeup, meeting audio, scheduled wakeups, channel-native activity, and chat collaboration workflows. Implemented as opt-in bridge collectors with rich-capture opt-in because participant names, meeting titles, transcripts, shared screens, notes, whiteboards, followups, message bodies, thread titles, channel/workspace names, searches, and status text can expose private content.
21. Native helper implementations for each platform/app: macOS Accessibility/System Events helpers, Windows UIA/WinEvent hooks, browser extensions, shell integrations, IDE extensions, calendar/mail adapters, Git/GitHub watchers, voice/meeting helpers, and creative-app plugins.
22. Deep app-specific enrichment: stable element IDs, safe selected-text summaries, thread metadata, document references, render/export statuses, and structured recovery hints.
