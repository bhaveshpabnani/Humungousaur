# Reference Feature Matrix

Date: 2026-06-01

Local source clones for implementation inspection live under `external_repos/` and are ignored by git. Current cloned package/code roots:

- Browser Use: `external_repos/browser-use/browser_use`
- Screenpipe: `external_repos/screenpipe`
- Windows-Use: `external_repos/windows-use/windows_use`
- Open Interpreter: `external_repos/open-interpreter/interpreter`

This file tracks the external agent projects referenced in `task.md` and turns them into concrete Umang implementation targets. It is license-aware: use these projects as architecture references first, and only copy code after confirming license compatibility and preserving attribution.

## License Notes

| Project | License signal checked | Use in Umang |
| --- | --- | --- |
| Open Interpreter | GitHub search result reports AGPL-3.0 | Prefer architectural reference or subprocess/plugin integration. Do not paste AGPL implementation code into core without an explicit license decision. |
| Browser Use | Docs/repo state MIT | Safe to study and adapt patterns with attribution; direct code copy still requires preserving license notices. |
| Screenpipe | Repo/docs state MIT | Safe to study and adapt patterns with attribution; likely best as optional local service integration. |
| Windows-Use | Repo states MIT | Safe to study and adapt patterns with attribution; use Windows UI Automation concepts as the main OS-control direction. |

## Feature Comparison

| Capability | Open Interpreter | Browser Use | Screenpipe | Windows-Use | Current Umang | Next Umang work |
| --- | --- | --- | --- | --- | --- | --- |
| Local code/shell execution | Runs local code/shell through LLM-controlled interpreter with approval | Limited file/tool actions around browser tasks | Not primary | Can run PowerShell | Constrained shell tool with approval, allowlist, and explicit command profiles; approval-gated `python_interpreter` child process with audit-hook file/network/subprocess/import controls; explicit write sandbox profiles; interpreter run manifests, resumable session metadata/replay, and bounded text-artifact reading | Extend policy profiles to other high-risk tools and add richer persistent interpreter backends. |
| Tool approval model | Approval/sandbox configuration and MCP tool approval modes | Human-in-the-loop custom tools | Local permissions/config focus | Warns OS control is dangerous; recommends VM/sandbox | Policy engine, approval queue, replay, audit trail | Add approval interrupts/edit-before-run for medium/high risk actions. |
| Structured tool registry | Interpreter tools plus MCP servers | `Tools`/`@tools.action`, typed params, action results; local code in `browser_use/tools/service.py` and registry modules | API/pipes/connectors | `Tool` abstraction in `windows_use/tools/service.py` plus agent registry | `Tool` dataclass with risk, schema, validation; external integration status tool; local plugin manifest discovery with blocked declared-tool placeholders | Add trusted plugin runtimes and MCP server support. |
| Browser control | Chrome browser research/control | Rich Playwright/browser session actions: navigate, search, back, wait, click/coordinate click, type, upload, tabs, extract, page search, selector query, scroll, scroll-to-text, send keys, screenshot, PDF save, dropdown options/selection, JS eval | Browser URL capture for memory | Browser accessibility-tree scraping | HTTP fetch, session store, metadata list, observe, extract, observed link click, field typing, text find, links, local history/back, images, forms, approval-gated submit; optional Playwright-backed live status/open/observe/search/click/coordinate-click/type/scroll/scroll-to-text/wait/tabs/selector/dropdown-options/dropdown-select/key/upload/download/PDF/JS/screenshot/close | Add persisted browser profiles, domain allowlists, download inventory/search, richer BrowserStateSummary fields, and page-state recovery. |
| Screen/activity memory | Session/memory SQLite config | Long-term memory in action result pattern | 24/7 screen/audio capture, OCR/accessibility, local DB, REST API, pipes, vault/encryption code | Persistent memory across steps | SQLite event memory plus memory tools and planning context; native activity ingest/search/policy/update/prune with retention and privacy exclusions | Add passive activity ingestion interface, app/folder/domain exclusion UI, daily summaries, deeper Screenpipe-inspired capture pipeline. |
| OS control | General local computer interface with computer modules for browser/files/terminal/keyboard/mouse/mail/calendar/etc. | Browser-focused | Observes screen/audio, not primary OS control | Windows UI Automation package plus desktop state, click/type/scroll/shortcut/app/window/virtual desktop/STT/TTS | Active-window observe, visible-window metadata, cursor metadata, approval-gated foreground UIA observe, short-lived selector maps, approval-gated click/type/scroll/shortcut/window resize/switch/state, coordinate clicks, UIA pattern actions, app discovery/launch, clipboard read/write, virtual-desktop metadata/move/keyboard actions | Add repeated-failure stop rules, live selector refresh, richer app launch policies, and optional speech/provider adapters. |
| Voice | Example voice interface / desktop voice | Not core | Audio transcription and meeting memory | STT/TTS voice input/output | Wake-word bridge, interaction harness, local spoken-response artifacts, Windows SAPI TTS tool, and stimulus API/CLI are implemented | Add push-to-talk UI, interruption/cancel flow, streaming partial responses, and provider-backed STT/TTS adapters. |
| Background automation | Hooks/config and sessions | Agent tasks can be scripted | Pipes for schedules/summaries/workflows | Multi-step agent loop | Async daemon runs and cancellation | Add trigger store: schedules, file events, meeting-ended hooks. |
| Telemetry/privacy | Configurable local state | Anonymous telemetry opt-out | Local-first capture, local data store | Telemetry opt-out | Local-first runtime, loopback API | Add explicit telemetry-none policy and privacy panel. |

## Implementation Backlog

### P0: Harden Existing Core

- Add approval interrupt flow for live runs; edit-before-approve is implemented for pending approvals.
- Python interpreter write profiles are implemented for `read_only`, `data_write`, `workspace_write`, and `trusted_dev`; shell command profiles are implemented for `read_only`, `workspace_write`, `trusted_dev`, and `blocked`; add broader policy profiles for other high-risk tools.
- Tool capability groups in permissions: files, shell, browser, memory, plugins, OS, voice, and system are implemented.
- External integration capability group is implemented for reference-project adapters.
- Add benchmark thresholds and regression alerts for planner context, memory, browser, OS, and index operations.

### P1: Browser Use Inspired Adapter

- Native static-session `browser_observe`, `browser_extract`, `browser_click_element`, `browser_type`, `browser_find_text`, and `browser_back` are implemented over stored HTTP browser sessions.
- Optional Playwright-backed `browser_live_status`, `browser_live_open`, `browser_live_observe`, `browser_live_search`, `browser_live_click`, `browser_live_click_coordinates`, `browser_live_type`, `browser_live_scroll`, `browser_live_scroll_to_text`, `browser_live_wait`, `browser_live_tabs`, `browser_live_new_tab`, `browser_live_switch_tab`, `browser_live_close_tab`, `browser_live_query_selector`, `browser_live_dropdown_options`, `browser_live_select_option`, `browser_live_press_key`, `browser_live_upload_file`, `browser_live_download`, `browser_live_save_pdf`, `browser_live_evaluate_js`, `browser_live_screenshot`, and `browser_live_close` are implemented as native Umang tools.
- Add persisted browser profiles, download inventory/search, domain-level browser policy, and richer page-state recovery.
- Add domain allowlists/denylists per browser tool.
- Keep form submit and file upload high risk with approval.
- Treat extracted page content, DOM, screenshots, and LLM page summaries as untrusted data.

### P1: Screenpipe Inspired Memory

- Add an ingestion interface for external activity sources:
  - screen OCR/accessibility text
  - active app/window title
  - browser URL/title
  - audio transcript/meeting note
- Native `activity_policy`, `activity_policy_update`, and `activity_prune` add retention days, disabled sources, excluded apps/window terms/text terms/domains, and approved pruning.
- Add daily summary and "what was I doing yesterday" workflows.
- Add optional Screenpipe local API connector once the core memory schema is stable.
- Implemented native primitives: approval-gated `activity_ingest`, local `activity_search`, policy inspection/update, retention pruning, and policy-aware filtering for activity search, memory search, planning context, and memory summaries.

### P1: Windows-Use Inspired OS Control

- Add Windows UI Automation element tree observation with stable element ids.
- Add safe `os_click_element`, `os_type_text`, `os_send_keys`, `os_scroll_element`, `os_switch_window`, `os_resize_window`, cursor/coordinate, UIA pattern, window-state, app, clipboard, and virtual-desktop tools.
- Require approval for text entry, shortcuts, shell, and any cross-app state change.
- Add failure counters and stop after repeated failed actions.
- Add VM/sandbox warning for full GUI control mode.
- Native `os_windows`, approval-gated `os_observe_ui`, short-lived selector maps, `os_click_element`, `os_type_text`, `os_send_keys`, `os_scroll_element`, `os_switch_window`, `os_resize_window`, `os_cursor`, `os_click_coordinates`, `os_uia_pattern_action`, `os_window_state`, `os_virtual_desktops`, `os_move_window_to_desktop`, `os_virtual_desktop_action`, `os_apps`, `os_launch_app`, `os_clipboard_read`, and `os_clipboard_write` are implemented; repeated-failure stop rules and live selector refresh remain next.

### P2: Open Interpreter Inspired Local Computer Interface

- Native `python_interpreter` is implemented as a high-risk approval-gated Python analysis tool with:
  - allowed read roots and allowed write roots enforced through child-process audit hooks
  - timeout
  - network blocked by default unless explicitly requested
  - subprocess blocked
  - stdlib-only imports by default, with explicit allowlisted packages or all-import mode available through approved tool input
  - explicit write sandbox profiles for read-only run artifacts, data writes, workspace edits, and trusted allowed-root dev work
  - local interpreter session manifests plus explicit replay of prior successful cells for lightweight continuity
  - captured stdout/stderr
  - run manifests and artifact metadata saved under the local data directory
  - `python_interpreter_runs`, `python_interpreter_run`, and `python_interpreter_artifact` for bounded manifest/text-artifact inspection
- Add broader policy profiles for high-risk tools, persistent interpreter backends, and richer notebook-style session UX.
- Add MCP server support as a tool source with per-tool approval modes.

### P2: Product UI

- Add provider selection and model status to dashboard.
- Add tool capability toggles by group.
- Add benchmark panel with recent averages and slow-operation warnings.
- Add memory timeline filters by source/kind/app/domain.
- Add live plan/act/observe view with approval edit controls.

### P2: Interaction Harness And Voice Response

- Native `InteractionHarness` accepts direct user text, voice transcripts, passive activity, accessibility, OCR, audio, browser, and system stimuli.
- Harness decisions are explicit: `respond`, `analyze`, `observe`, or `ignore`.
- Direct user and voice stimuli run the agent immediately; passive stimuli are recorded and only trigger an agent run when upstream structured metadata marks them as actionable.
- Response modes are `text`, `voice_prepare`, `voice_speak`, and `silent`.
- Native voice tools are implemented: `voice_response_prepare`, `voice_speak`, and `voice_responses`.
- Add streaming partial responses, barge-in/cancel support, and richer voice provider configuration.

## Current Umang Coverage Snapshot

- Implemented: local daemon, CLI, dashboard, audit, approval queue, policy engine, tool schemas, schema validation, file/PDF/web/browser basics, optional live Playwright browser tools, memory tools, active-window/window/UIA observation, approval-gated OS click/type/scroll/shortcut/window actions, app-open approval, interaction harness, TTS response artifacts, Windows local speech, planning context, benchmarks.
- Missing: passive screen/audio capture adapters, streaming response UI, barge-in/cancel voice flow, plugin/MCP loading, semantic/vector memory, advanced approvals.

## Source Links

- Open Interpreter: https://github.com/OpenInterpreter/open-interpreter
- Open Interpreter config/approvals/MCP docs: https://www.openinterpreter.com/docs/terminal/config
- Browser Use: https://github.com/browser-use/browser-use
- Browser Use tools docs index in `AGENTS.md`: https://github.com/browser-use/browser-use/blob/main/AGENTS.md
- Screenpipe: https://github.com/screenpipe/screenpipe
- Screenpipe docs: https://docs.screenpi.pe/home
- Windows-Use: https://github.com/CursorTouch/Windows-Use
