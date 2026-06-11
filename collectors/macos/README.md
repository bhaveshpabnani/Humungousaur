# Humungousaur macOS Collectors

The macOS platform collector host is a SwiftPM helper that emits privacy-first
collector event envelopes into Humungousaur's JSONL bridge spool. The Python
runtime still owns durable SQLite storage, batching, memory, consumers, and LLM
boundaries.

## Implemented Collectors

`HumungousaurMacCollectorHost` implements the macOS helper for core OS context,
browser context, filesystem/file-manager, OS system surfaces, Screen/UI
metadata, developer workflow metadata, mail/calendar metadata, and
communication/meeting metadata collector families.

Core OS context:

- `active_window`
- `window_lifecycle`
- `app_lifecycle`
- `device_state`
- `input_device`
- `keyboard_input_activity`
- `ime_activity`
- `text_input_surface_activity`
- `pasteboard_workflow_activity`

Browser context:

- `browser`
- `browser_lifecycle`
- `browser_window_activity`
- `browser_tab_group_activity`
- `browser_profile_activity`
- `browser_extension_activity`
- `browser_web_app_activity`
- `browser_view_mode_activity`
- `browser_page_activity`
- `bookmark_history_activity`

Filesystem and file manager:

- `filesystem`
- `downloads`
- `file_operation_activity`
- `folder_navigation_activity`
- `file_preview_activity`
- `trash_activity`

OS system surfaces:

- `notification_activity`
- `permission_activity`
- `location_activity`
- `resource_activity`
- `storage_activity`
- `software_activity`
- `print_scan_activity`
- `search_activity`
- `peripheral_activity`
- `media_activity`
- `focus_task_activity`
- `policy_activity`
- `wellbeing_activity`

Screen/UI metadata:

- `accessibility_context`
- `command_activity`
- `selection_activity`
- `navigation_activity`
- `edit_history_activity`
- `workspace_layout_activity`
- `window_arrangement_activity`
- `display_arrangement_activity`
- `app_workspace_activity`
- `dock_taskbar_activity`
- `menu_bar_tray_activity`
- `quick_settings_activity`
- `widget_activity`

Developer workflow:

- `terminal_activity`
- `ide_activity`
- `git_activity`
- `github_activity`
- `package_manager_activity`
- `build_tool_activity`
- `test_runner_activity`
- `local_service_activity`
- `debugger_activity`
- `database_activity`
- `cloud_console_activity`

Mail and calendar:

- `calendar_activity`
- `wakeups`
- `calendar_scheduling_activity`
- `reminder_todo_activity`
- `mail_activity`
- `mail_composition_activity`
- `mail_organization_activity`

Apple apps and iWork workflows:

- `notes_activity`
- `share_activity`
- `document_activity`
- `document_composition_activity`
- `document_review_activity`
- `document_structure_activity`
- `document_export_publish_activity`
- `pdf_activity`
- `spreadsheet_activity`
- `spreadsheet_editing_activity`
- `spreadsheet_formula_activity`
- `spreadsheet_data_analysis_activity`
- `spreadsheet_import_export_activity`
- `presentation_activity`
- `presentation_authoring_activity`
- `presentation_design_activity`
- `presentation_delivery_activity`
- `presentation_export_activity`
- `camera_capture_activity`
- `media_activity`
- `communication_activity`
- `chat_composition_activity`
- `chat_thread_activity`

Communication and meetings:

- `voice_wakeup`
- `meeting_audio`
- `meeting_app_activity`
- `call_control_activity`
- `meeting_presentation_activity`
- `meeting_artifact_activity`
- `channel_activity`
- `communication_activity`
- `chat_composition_activity`
- `chat_thread_activity`
- `chat_channel_navigation_activity`
- `chat_presence_activity`

Source layout:

- `Sources/CollectorHost/main.swift`: process entrypoint only.
- `Sources/CollectorHost/Runtime/`: host options, helper constants, and runtime orchestration.
- `Sources/CollectorHost/Bridge/`: JSONL spool writing and helper-health reporting.
- `Sources/CollectorHost/CoreOSContext/`: one focused file per collector category.
- `Sources/CollectorHost/BrowserContext/`: browser foreground-window and profile-store metadata collectors.
- `Sources/CollectorHost/FileSystemContext/`: FSEvents, downloads, Finder/Quick Look, and trash metadata collectors.
- `Sources/CollectorHost/OSSystemSurfaces/`: permissions, location/region, storage/resource, software, print, peripheral, policy, notification/search/media/wellbeing, and focus-task metadata collectors.
- `Sources/CollectorHost/ScreenUIMetadata/`: Accessibility, keyboard shortcut, workspace/layout, and system-surface metadata collectors.
- `Sources/CollectorHost/DeveloperWorkflow/`: developer app, process, listener, Git, package, build, test, database, cloud-tool, and GitHub workflow metadata collectors.
- `Sources/CollectorHost/MailCalendarWorkflow/`: Calendar, Reminders, Mail app/process/store, and EventKit metadata collectors.
- `Sources/CollectorHost/AppleAppsWorkflow/`: Finder, Messages, Notes, Pages, Numbers, Keynote, Preview, and Photos workflow metadata collectors.
- `Sources/CollectorHost/CommunicationMeetings/`: communication app, meeting app, foreground window, process, and shortcut metadata collectors.
- `Sources/CollectorHost/MacOSSupport/`: small native API readers and privacy formatting helpers.
- `Sources/EventWriter/`: shared event envelope and JSONL writer aligned to `../shared/event-envelope.schema.json`.

Native APIs used:

- `NSWorkspace` for app focus/open/close/hide and sleep/wake notifications.
- `CGWindowListCopyWindowInfo` for foreground window metadata.
- `IOKit` for idle and power-source metadata.
- `SystemConfiguration` for coarse reachability changes.
- Text Input Sources (`TISCopyCurrentKeyboardInputSource`) for keyboard/IME source changes.
- `NSEvent` global monitors for mouse, scroll, shortcut, and paste-command activity.
- Accessibility (`AXUIElement`) for focused text-entry surface metadata when permission is granted.
- `NSPasteboard.changeCount` and pasteboard type categories for copy/clear detection without reading values.
- `NSWorkspace` and `CGWindowListCopyWindowInfo` for foreground browser/window metadata.
- `FileManager.contentsOfDirectory` and file resource metadata for browser profile, extension, web app, bookmark, history, and tab-group store diffs.
- `NSScreen`, `CGWindowListCopyWindowInfo`, `CGDisplayRotation`, and `UserDefaults` for display layout, foreground window placement, active app workspace signatures, and Stage Manager state where available.
- File System Events (`FSEventStreamCreate`) for watched directory/file changes.
- `FileManager` search directories for Downloads and the user Trash root.
- Finder/Quick Look foreground window metadata for folder and preview workflow signals.
- `AVCaptureDevice.authorizationStatus`, `CLLocationManager.authorizationStatus`,
  `AXIsProcessTrusted`, and `CGPreflightScreenCaptureAccess` for permission
  state metadata without requesting protected content.
- `TimeZone`, `Locale`, and `NSSystemTimeZoneDidChange` for region/time-zone
  metadata with coordinates omitted.
- `ProcessInfo` for thermal and low-power-mode metadata.
- `FileManager.URLResourceValues` for disk and mounted-volume capacity buckets.
- `NSWorkspace` notifications and application-bundle file signatures for
  installer/software lifecycle and mounted-storage activity.
- IOKit USB registry snapshots for USB connect/disconnect signatures without
  device serials or names.
- CUPS `lpstat` output reduced to hashes for active print jobs and default
  printer changes; document and printer names are omitted.
- `CGWindowListCopyWindowInfo` for Notification Center, Spotlight,
  Screen Time, device-management, and screen-recording surface metadata without
  screen pixels or raw titles.
- `NSWorkspace.activeSpaceDidChangeNotification` for focus/task desktop-Space
  transitions.
- Accessibility (`AXUIElement`) focused element attributes for role/subrole,
  selected range length buckets, selected child counts, and control-state buckets.
- `NSEvent.addGlobalMonitorForEvents` for privacy-safe shortcut and context-menu
  activity metadata, using key codes/modifier categories only.
- `CGWindowListCopyWindowInfo` plus `NSRunningApplication` for Dock, menu bar,
  Control Center, and Notification Center/widget surface window metadata.
- `NSWorkspace.runningApplications`, bounded `ps`, bounded `lsof`, and
  `FileManager` file-attribute signatures for developer workflow metadata.
- EventKit (`EKEventStore`) for calendar/reminder count, due, and timing
  metadata when the user has already granted access.
- `NSWorkspace`, `CGWindowListCopyWindowInfo`, bounded `ps`, and `FileManager`
  file-attribute signatures for Mail, Calendar, and Reminders app/process/store
  metadata.
- `NSWorkspace`, `CGWindowListCopyWindowInfo`, and `FileManager`
  file-attribute signatures for Finder, Messages, Notes, Pages, Numbers,
  Keynote, Preview, Photos, iCloud iWork folders, user document folders, and the
  Photos library metadata. The helper emits foreground-window hashes, app-family
  categories, extension buckets, count buckets, size buckets, and store/library
  signatures only.
- `NSWorkspace.runningApplications`, app launch/terminate/activate
  notifications, `CGWindowListCopyWindowInfo`, and `NSEvent` global shortcut
  monitors for Teams, Zoom, Slack, Discord, WhatsApp, Telegram, Signal,
  Outlook, Skype, Webex, FaceTime, Messages, RingCentral, and browser
  collaboration surface metadata.
- `NSStatusBar`, WidgetKit Control Center, and Notification Center documentation
  inform the system-surface classifications; the helper observes only redacted
  visible-window metadata.

The helper does not capture screen pixels, audio, typed text, selected text,
window-title text, field labels, field values, IME candidates, committed IME
text, clipboard contents, pasteboard history values, file contents, raw file
names, raw paths, browser URLs, browser titles, history rows, bookmark names,
extension names, web-app names, profile names, or browser account details.
Window titles are represented only as presence, length bucket, and SHA-256 hash.
File paths and browser profile-store locations are represented by digests,
counts, buckets, and store signatures.
Display names, exact workspace names, project/profile names, visible window
contents, and raw layout presets are omitted; display and workspace state are
represented by counts, hashes, size buckets, and coarse placement signatures.
UI collector events do not include control labels, menu item titles, selected
text, typed keys, widget content, notification content, status-item names, or
screen pixels.
OS system-surface events do not include notification content, raw search query
text, precise coordinates, permission prompt text, print document names, printer
names, USB serial numbers, device names, managed-profile payloads, screen pixels,
media content, or Screen Time/app-limit contents. They emit authorization states,
hashes, buckets, booleans, counts, and coarse visible-surface categories.
Developer workflow events do not include command lines, terminal output, working
directories, file paths, package names, registry URLs, build targets, logs, test
names, assertion text, stack frames, variable values, SQL, database rows,
credentials, cloud resource IDs, account IDs, or GitHub issue/PR content. They
emit process names/categories, hashed process identifiers, port buckets,
workspace digests, file-attribute signatures, and redacted foreground app/window
metadata only.
Mail/calendar workflow events do not include message bodies, subjects, sender or
recipient names, attachment filenames, mailbox names, calendar titles, attendee
names, locations, notes, reminder titles, list names, or raw event/reminder
identifiers. They emit app/process categories, window title hashes/buckets,
EventKit count and timing buckets, Mail store signatures, and explicit omitted
flags only.
Apple app workflow events do not include Finder paths, file names, document
titles, document text, selected text, message bodies, participant names, note
contents, PDF contents, spreadsheet formulas or values, slide text, media pixels,
EXIF values, location values, people/faces metadata, or Photos asset filenames.
They emit app-family categories, window hashes/buckets, extension buckets, count
buckets, size buckets, and redacted store/library signatures only.
Communication and meeting events do not include raw audio, transcript text,
speaker names, message bodies, recipients, participant names, meeting titles,
channel/workspace names, thread titles, notification contents, custom status
text, attachment names, slash-command payloads, shared window names, or screen
contents. The helper emits app categories, foreground/process/window
signatures, title hashes/length buckets, public app lifecycle metadata, and
shortcut key codes/modifier categories only.

Browser view-mode and page-action events such as reader mode, find-in-page,
link clicks, form changes, uploads, and console errors remain extension/native
messaging responsibilities. The macOS helper reports support/health for those
collectors but does not read page contents or browser databases to synthesize
them.

## Build

```sh
cd collectors/macos
swift build
```

## Run

One-shot validation:

```sh
swift run HumungousaurMacCollectorHost --data-dir ../../artifacts --once
```

Long-running helper:

```sh
swift run HumungousaurMacCollectorHost \
  --workspace ../.. \
  --data-dir ../../artifacts \
  --watch ../.. \
  --poll-seconds 2 \
  --latency 0.35
```

The helper writes full envelopes to:

```text
<data-dir>/collector_spool/<collector>.jsonl
```

When the local Humungousaur API is running, pass `--api-url` to report helper
health through the existing `/collectors/helper-health` contract:

```sh
swift run HumungousaurMacCollectorHost \
  --data-dir ../../artifacts \
  --api-url http://127.0.0.1:8765
```

Without `--api-url`, the helper still emits a metadata-only `agent_runtime`
health heartbeat envelope into the JSONL spool for local diagnostics.

## Permissions

Accessibility permission improves `text_input_surface_activity`,
`accessibility_context`, and `selection_activity` fidelity. Input Monitoring may
be required by macOS for global keyboard shortcut signals. If a permission is
missing, the helper keeps raw capture off, reports degraded helper health, and
continues emitting the collectors that remain available.

File System Events can observe watched directories that the current user can
read. Broader paths may require Full Disk Access. Endpoint Security is not used
by this helper; privileged open/close auditing remains a separate opt-in lane.
