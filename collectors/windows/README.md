# Humungousaur Windows Collectors

Windows collectors should use C#/.NET for the host and ordinary OS integrations,
with small C++ helpers only where ETW, low-level hooks, or COM surfaces require
it. Every collector must emit the shared event envelope.

## Core OS Context Helper

`CollectorHost` contains the Windows-native core OS context helper. It is a
single C#/.NET host that emits shared collector event envelopes to
`<data-dir>/collector_spool/<collector>.jsonl` for:

- `active_window`
- `browser`
- `window_lifecycle`
- `app_lifecycle`
- `browser_lifecycle`
- `browser_window_activity`
- `browser_tab_group_activity`
- `browser_profile_activity`
- `browser_extension_activity`
- `browser_web_app_activity`
- `browser_view_mode_activity`
- `browser_page_activity`
- `bookmark_history_activity`
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
- `device_state`
- `input_device`
- `keyboard_input_activity`
- `ime_activity`
- `text_input_surface_activity`
- `pasteboard_workflow_activity`
- `filesystem`
- `downloads`
- `file_operation_activity`
- `folder_navigation_activity`
- `file_preview_activity`
- `trash_activity`
- `accessibility_context`
- `command_activity`
- `selection_activity`
- `navigation_activity`
- `edit_history_activity`
- `dock_taskbar_activity`
- `menu_bar_tray_activity`
- `quick_settings_activity`
- `widget_activity`
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
- `workspace_layout_activity`
- `window_arrangement_activity`
- `display_arrangement_activity`
- `app_workspace_activity`
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
- `calendar_activity`
- `wakeups`
- `calendar_scheduling_activity`
- `reminder_todo_activity`
- `mail_activity`
- `mail_composition_activity`
- `mail_organization_activity`

The helper uses Win32 foreground/window event hooks, low-level keyboard and mouse
hooks, process snapshots, power/network/idle APIs, keyboard layout state, IME
state, focused edit-control metadata, `FileSystemWatcher`/Windows directory
change notifications, Explorer foreground/shortcut metadata, browser profile
store metadata watchers for Chrome, Edge, Brave, Vivaldi, Opera, and Firefox,
app-specific communication and meeting profiles for Teams, Zoom, Slack,
Discord, WhatsApp, Telegram, Signal, Outlook, Skype, Webex, RingCentral,
browser collaboration surfaces, Humungousaur voice, and Windows Voice Access,
monitor topology snapshots and foreground-window geometry observers,
WinEvents for accessibility/menu/selection/control metadata, a hidden native
message window for OS broadcasts such as `WM_DEVICECHANGE`,
`WM_POWERBROADCAST`, display changes, session lock/unlock, and setting-change
notifications, plus diff-based snapshots for coarse storage, resource,
installer, print-spool, media-key, search, system-surface, developer process,
local listener, and project metadata activity. It is
intentionally metadata-only: window titles are omitted and represented only by
length/hash, typed characters are not stored, clipboard contents are never read,
file paths and filenames are hashed or omitted, notification bodies, permission
prompt text, precise location, media titles, printer names, policy text, command
labels, and selected text are omitted, browser URLs, tab titles, profile names,
extension names, saved tab-group names, bookmark titles, history queries, and
page contents are omitted, workspace names, project paths, display labels,
window titles, visible workspace contents, meeting titles, participant names,
speaker names, transcripts, message bodies, channel names, thread titles,
custom status text, attachment names, and shared-window contents are omitted,
shell command text,
command-line arguments, terminal output, build logs, test names, assertions, SQL,
database results, cloud URLs/resource identifiers, package names, branch names,
commit messages, repository paths, command lines, executable paths, email
subjects, senders, recipients, message bodies, mailbox labels, attachment
names, calendar titles, attendees, locations, notes, reminder titles, and task
notes are not collected, and screen/audio/text/file/UI payloads are not
captured.

Run once for a local smoke event:

```powershell
dotnet run --project collectors/windows/CollectorHost -- --data-dir artifacts --once
```

Add explicit watched roots with repeated `--watch-path` flags:

```powershell
dotnet run --project collectors/windows/CollectorHost -- --data-dir artifacts --watch-path C:\work\downloads --watch-path C:\work\project
```

Run as a long-lived helper and report helper health to the Humungousaur API when
available:

```powershell
dotnet run --project collectors/windows/CollectorHost -- --data-dir artifacts --helper-health-url http://127.0.0.1:8765/collectors/helper-health
```

Helper health is reported per collector with `helper_id=windows-core-os-context`
using the existing `/collectors/helper-health` contract. Event JSONL remains
ingress only; Python owns durable SQLite storage, batching, memory, and the LLM
boundary.

Current helper layout:

- `CollectorHost/Program.cs`: minimal entrypoint.
- `CollectorHost/Core`: host lifecycle, event sink, options, and helper-health
  reporting.
- `CollectorHost/Contracts`: collector names and the native event shape used
  before shared-envelope serialization.
- `CollectorHost/Collectors/Application`: process/app lifecycle collectors.
- `CollectorHost/Collectors/Browser`: browser foreground, window, lifecycle,
  profile, extension, web-app, tab-group, view-mode, page/download, and
  bookmark/history metadata collectors.
- `CollectorHost/Collectors/Communication`: app-specific communication and
  meeting metadata collectors for voice wakeups, meeting audio state,
  meeting lifecycle, call controls, presentation/share shortcuts, meeting
  artifacts, channels, communication, chat composition, threads, navigation,
  and presence.
- `CollectorHost/Collectors/Device`: power, network, and idle/session state.
- `CollectorHost/Collectors/DeveloperWorkflow`: terminal, IDE, git/GitHub,
  package-manager, build-tool, test-runner, local-service, debugger, database,
  and cloud-console metadata collectors.
- `CollectorHost/Collectors/Input`: input-device, keyboard-layout, IME,
  text-input-surface, and pasteboard-workflow collectors.
- `CollectorHost/Collectors/MailCalendar`: mail, mail-composition,
  mail-organization, calendar, scheduled wakeup, scheduling, and reminder/to-do
  metadata collectors.
- `CollectorHost/Collectors/FileSystem`: filesystem, downloads, file operation,
  folder navigation, file preview, and trash/recycle-bin collectors.
- `CollectorHost/Collectors/ScreenUi`: accessibility context, command,
  selection, navigation, edit-history, taskbar/tray, quick-settings, and widget
  metadata collectors.
- `CollectorHost/Collectors/SystemSurfaces`: notification, permission,
  location, resource, storage, software, print/scan, search, peripheral, media,
  focus-task, policy, and wellbeing metadata collectors.
- `CollectorHost/Collectors/Workspace`: workspace overview, virtual-desktop
  shortcut, foreground-window arrangement, monitor topology, display-change,
  and app workspace foreground metadata collectors.
- `CollectorHost/Collectors/Window`: active-window and window-lifecycle
  collectors plus redacted window snapshots.
- `CollectorHost/Win32`: P/Invoke, low-level hooks, message loop, and small
  Windows interop helpers.

When adding more Windows collectors, add domain-owned files under
`CollectorHost/Collectors/<Domain>` and keep only shared plumbing in `Core` or
`Win32`. Do not add Python durable-storage, batching, memory, or LLM-boundary
logic to native helpers.

Suggested future collector folders:

- `FileAccess`: ETW or auditing for opt-in privileged access semantics.
- `Media`: Windows media/session state.

Browser source notes:

- Foreground browser/window lifecycle comes from WinEvent foreground/create/destroy
  hooks and never emits raw window titles or URLs.
- Profile, extension, installed web-app, saved tab-group, bookmark, and history
  changes come from local profile-store metadata watches only; the helper does
  not parse or emit stored URLs, titles, names, accounts, queries, or page
  contents.
- High-fidelity tab group, tab URL, page error, form, extension popup/action,
  reader mode, mute, picture-in-picture, and translation semantics still belong
  in an explicit browser extension/native-messaging bridge.

Communication/meeting source notes:

- App-specific profiles currently cover Teams, Zoom, Slack, Discord, WhatsApp,
  Telegram, Signal, Outlook, Skype, Webex, RingCentral, browser collaboration
  surfaces, Humungousaur voice, and Windows Voice Access.
- Foreground/process observations emit app IDs, process names, title hashes, and
  explicit omitted flags only. They do not read meeting titles, participants,
  channel names, message bodies, transcripts, or custom status text.
- Keyboard shortcuts emit metadata-only call-control, chat-navigation,
  compose/send, screen-share, captions, recording, and presence events. Toggle
  state is inferred from repeated shortcuts and marked as such.
- Exact messages, mentions, participant events, transcripts, notification
  contents, and app-specific meeting artifacts require explicit app, browser,
  notification-listener, or audio-session bridges with user permission.

Mail/calendar source notes:

- Windows exposes appointment, email, task, and notification APIs, but those
  can reveal rich user content or require explicit user/API access. The current
  helper therefore uses process snapshots, foreground WinEvents, keyboard
  shortcut intent, and watched-file metadata only.
- Foreground/process observations emit app IDs, process names, title hashes, and
  explicit omitted flags. They do not read email subjects, senders, recipients,
  message bodies, mailbox labels, attachment filenames, calendar titles,
  attendees, locations, notes, reminder titles, or task notes.
- Keyboard shortcuts emit metadata-only compose/reply/forward/send/search,
  delete/unread/flag, calendar create/update/delete/availability, and
  reminder/to-do create/update/snooze/complete/delete events. Shortcut-derived
  semantics are coarse workflow observations, not content capture.
- Watched `.ics`, `.eml`, `.msg`, `.oft`, and reminder/to-do-like files emit
  extension, hashed path/root metadata, change kind, and content-omitted flags
  only. Rich mail/calendar store access belongs in a future explicit opt-in app
  or notification bridge with helper-health permission reporting.

Workspace/layout source notes:

- Display arrangement uses monitor topology snapshots plus `WM_DISPLAYCHANGE`.
  It emits monitor counts, primary-display hashes, and size buckets only.
- Window arrangement uses foreground-window geometry relative to the monitor work
  area and Windows snap/desktop keyboard shortcuts. Window titles and visible
  contents are omitted.
- App workspace events are foreground-app transitions only. Workspace/project
  names, paths, restored contents, and profile names are omitted.
- Windows virtual-desktop creation/deletion and named workspace enumeration are
  not exposed through the public API used here; those remain bridge/extension
  enrichment points.
