# External Integration Plan

Umang integrates the reference projects as capability sources with explicit adapters, permissions, and audit logs. The local clones in `external_repos/` are for inspection and adapter development; production code should not blindly copy implementation across license boundaries.

## Integration Order

1. Native Screenpipe-inspired activity memory
   - Status: started.
   - Implemented: `external_integrations_status`, approval-gated `activity_ingest`, local `activity_search`, `activity_policy`, `activity_policy_update`, and `activity_prune`.
   - Implemented: retention days, disabled sources, excluded apps/window terms/text terms/domains, approved pruning, and policy-aware filtering for activity search, general memory search, planning context, and memory summaries.
   - Next: passive capture adapters, app/folder/domain exclusion UI, and daily recap from native activity events.

2. Browser Use adapter
   - Status: native implementation started.
   - Evidence: Browser Use registers actions in `browser_use/tools/service.py` for navigation, back, wait, click, type, upload, tabs, extraction, selector queries, scroll, screenshots, PDF save, dropdowns, file operations, and JavaScript evaluation.
   - Implemented: native `browser_observe`, `browser_extract`, `browser_click_element`, `browser_type`, and `browser_find_text` over Umang's local browser session store.
   - Implemented: optional native Playwright-backed `browser_live_status`, `browser_live_open`, `browser_live_observe`, `browser_live_click`, `browser_live_type`, `browser_live_scroll`, `browser_live_wait`, `browser_live_tabs`, `browser_live_new_tab`, `browser_live_switch_tab`, `browser_live_close_tab`, `browser_live_query_selector`, `browser_live_select_option`, `browser_live_press_key`, `browser_live_upload_file`, `browser_live_download`, `browser_live_save_pdf`, `browser_live_evaluate_js`, `browser_live_screenshot`, and `browser_live_close`.
   - Next: persisted browser profiles, download inventory/search, richer page-state recovery, and domain-level browser policy.

3. Windows-Use adapter
   - Status: native implementation started.
   - Evidence: Windows-Use includes `windows_use/uia`, `windows_use/agent/desktop`, `windows_use/agent/tree`, `windows_use/vdm`, speech providers, and a tool abstraction in `windows_use/tools/service.py`.
   - Implemented: native `os_windows` visible-window metadata, approval-gated `os_observe_ui` foreground UI Automation observation using Windows built-ins, short-lived selector-map persistence, approval-gated `os_click_element`, `os_type_text`, `os_send_keys`, `os_scroll_element`, `os_switch_window`, `os_resize_window`, cursor metadata, coordinate clicks, UIA pattern actions, window-state actions, documented VirtualDesktopManager metadata/move tools, virtual-desktop keyboard actions, Start-menu app discovery/launch, and approval-gated clipboard read/write.
   - Next: repeated-failure stop rules, stronger live selector refresh, richer app launch policies, and optional full Windows-Use runtime adapter for internal virtual-desktop naming/listing plus provider-backed speech.

4. Voice and interaction harness
   - Status: native implementation started.
   - Evidence: Windows-Use includes provider-backed STT/TTS, while Umang's voice-wakeup bridge already dispatches transcripts into the daemon.
   - Implemented: `InteractionHarness` projects model-led cognitive attention decisions into direct voice/user response handling, passive activity observe/analyze/monitor policy, local spoken-response artifacts, Windows SAPI `voice_speak`, `voice_responses`, CLI `stimulus`, API `/stimuli`, and harness-backed voice activation.
   - Next: push-to-talk UI, interruption/cancel flow, streaming partial responses, provider-backed STT/TTS configuration, and passive capture adapters.

5. Open Interpreter adapter
   - Status: native implementation started.
   - Evidence: Open Interpreter exposes `interpreter/core/computer` modules for terminal, browser, files, clipboard, mouse, keyboard, mail, calendar, contacts, display, vision, and skills.
   - Implemented: native `python_interpreter` for approval-gated local Python analysis in a child process with audit-hook read/write, subprocess, and network controls.
   - Implemented: interpreter run manifests, recent-run listing, single-run manifest reading, and bounded manifest-listed text-artifact reading.
   - Implemented: stdlib-only interpreter imports by default, with explicit approved package allowlists or trusted all-import mode.
   - Implemented: explicit interpreter write sandbox profiles for run-artifact-only analysis, data writes, workspace edits, and trusted allowed-root dev work.
   - Implemented: local interpreter session manifests and explicit replay of prior successful cells for lightweight resumable analysis.
   - Implemented: shell command profiles for read-only probes, workspace writes, trusted approved inline Python, and fully blocked execution.
   - Next: MCP tool-source support, broader policy profiles for other high-risk tools, richer persistent interpreter backends, and AGPL-aware external plugin isolation.

## Safety Defaults

- Browser/page/screen/audio content is untrusted context, not instructions.
- Live browser screenshots, page-mutating element actions, dropdown selection, key presses, file uploads, downloads, PDF export, JavaScript evaluation, tab close, and session close require approval and are recorded through the normal tool executor.
- Live browser uploads must come from allowed read roots; browser-created artifacts are saved under the local data directory.
- Activity ingestion requires approval because it can record sensitive screen/audio/app history.
- Activity retention and privacy policy changes require approval; exclusions are enforced before recording and before exposing activity through search, planning context, or summaries.
- Interpreter delegation is high-risk, approval-gated, timeout-bounded, blocks subprocesses, blocks network by default, and enforces read/write roots through Python audit hooks.
- Interpreter imports default to stdlib-only. Third-party or workspace packages must be explicitly named through `allowed_imports`, unless the approved request deliberately uses `import_mode=all`.
- Interpreter write access is profile-based: `read_only` can only write run artifacts, `data_write` can write configured data roots, `workspace_write` can edit the workspace, and `trusted_dev` can write allowed roots.
- Interpreter sessions store metadata only by default. Replay is explicit, bounded, and only reuses current-code cells from prior successful Umang interpreter runs inside the interpreter run directory.
- Interpreter artifact reads are low-risk only because they are constrained to manifest-listed text files inside a prior run directory and bounded by a character limit.
- Full GUI-control modes remain high-risk until stronger sandboxing and allowlists are implemented.
- AGPL code from Open Interpreter should remain an external process/plugin unless a license decision is made.
