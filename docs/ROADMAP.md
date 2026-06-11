# Roadmap

Engineering principles live in `docs/ENGINEERING_PRINCIPLES.md`. New broad assistant behaviors should be model-led capability handoffs, with deterministic safeguards kept to explicit fallback commands, safety validation, schema validation, audit persistence, and evidence-boundary enforcement.

Collector task rule: do not treat a stimulus type as implemented just because it is listed in a collector definition. Every collector task must also add or identify the source emitter: local polling, local OS-state inspection, native helper bridge, browser/IDE/app extension, or an explicit bridge-only placeholder naming the missing emitter. Adapter implementations live under `humungousaur/collectors/adapters/`; core runtime files such as `manager.py`, `definitions.py`, `bridge.py`, and `attention_compaction.py` stay at the collector package root.

## Milestone 1: Safe Local Runtime

Status: implemented as first slice.

- CLI command intake
- model-led structured planner with explicit fallback
- file tools
- policy engine
- SQLite audit log
- note persistence
- voice-wakeup activation adapter

## Milestone 2: Real Memory

Status: started.

- SQLite event tables instead of JSONL-only memory
- workspace index
- local memory search/write tools
- recent memory in planning context
- daily and weekly summaries via local memory recap service, API, CLI, dashboard, and tool
- queryable recent runs
- user preference store projected from explicit local memory into planning context, API, CLI, dashboard, and tool

## Milestone 3: LLM Planner

Status: started.

- planner provider interface
- strict structured JSON plan parser
- optional OpenAI Responses model client
- OpenAI-compatible chat provider path for OpenAI, Grok/xAI, and local endpoints
- `.env` loading with secret redaction
- model-backed structured planner with explicit command fallback
- compact local planning context
- persisted plan traces
- plan trace CLI
- provider-error secret redaction
- high-risk approval request workflow
- durable approval queue
- approval edit-before-approve workflow
- approval replay from CLI
- constrained shell tool
- prompt-injection regression fixture

## Milestone 3.5: Local API Daemon

Status: started.

- loopback-only stdlib HTTP server
- run/audit/plans/memory/approval endpoints
- async run endpoint with durable task timeline
- cooperative run cancellation API and dashboard stop control
- approval decisions attached to the original run timeline
- permissions API and dashboard policy view
- persistent editable extra read roots
- local performance benchmark CLI and API
- local SQLite file index with rebuild/status controls
- automatic file-index rebuild after read-root permission edits
- dashboard provider/model/base-URL/API-key-env/dry-run selection for queued runs
- CLI `serve` command
- API integration tests

Remaining:

- approval interrupts
- fallback explicit command planner

## Milestone 4: Browser Agent

Status: started.

- HTTP(S) fetch and research tools
- local browser session store
- metadata-only browser session listing tool
- link navigation
- local browser history and back navigation
- form extraction and draft filling
- approval-gated form submit
- approval-gated session forgetting for local page state and drafts

Remaining:

- Playwright or Browser Use adapter
- richer tab/session controls
- element-level click/type/scroll tools
- screenshot and visual confirmation
- file upload and download handling
- broader browser task benchmarks

## Milestone 5: OS Perception

Status: started.

- active-window tracker
- approval-gated allowlisted app opening
- approval-gated screenshot capture stored locally under the data directory
- metadata-only screenshot registry visible through API, CLI, dashboard, and planning context
- approval-gated screenshot deletion constrained to local registry filenames

Remaining:

- Windows UI Automation exploration
- current-screen summary
- element-tree click/type/scroll/shortcut tools
- virtual desktop and window management

## Milestone 6: Voice Product Loop

- voice-wakeup dispatches saved activations to Humungousaur API
- live wake-word listener can dispatch transcripts to daemon with `--agent-api-url`
- voice-wakeup logic tests run without ML/audio dependencies installed
- wake-word transcript routing directly into Humungousaur
- cooperative cancellation for daemon runs
- spoken response
- push-to-talk fallback
- interruption and cancellation

## Milestone 7: Desktop UI

- local dashboard served from daemon
- command input
- recent runs view
- pending approvals view
- plan trace view
- memory search view
- live task timeline
- approvals panel
- memory search
- permissions dashboard
- activity replay

## Milestone 8: End-to-End Collector Sources

Status: started.

- Collector runtime now has a durable SQLite WAL event bus, normalized event envelopes, independent consumer offsets/state, retry tracking, and dead-letter handling.
- `collectors/` now defines the cross-platform platform collector kit: Swift for macOS, C#/.NET for Windows, and Rust for Linux, all targeting one shared event envelope schema.
- Adapter modules live under `humungousaur/collectors/adapters/`.
- Source implementation levels are documented in `docs/COLLECTOR_ARCHITECTURE.md`.
- App, SaaS, browser-extension, IDE-plugin, and webhook source integrations are organized in `docs/APP_COLLECTOR_ARCHITECTURE.md`.
- Janus collector interpretation, reflex LLM routing, task context, muted scopes, deep-dive requests, and UI posture are designed in `docs/JANUS_COLLECTOR_WORKFLOW.md`.
- Detailed janus Reflex architecture, human-task research basis, event families, context memory, Activity Skill Packs, agent bridge, desktop UI surfaces, and implementation phases are documented in `docs/JANUS_REFLEX_ARCHITECTURE.md`.
- First janus runtime slice is implemented with `humungousaur/janus/`, an independent `janus` collector consumer, Reflex LLM schema/parser, cognition prompt-template integration, task-context/muted-scope/deep-dive stores, muted-scope cancellation, deep-dive approve/reject transitions, user-declared task focus projection, generalized rolling/collector/source/entity context windows, sustained/return-after-gap boundaries, resume capsules, UI-safe explanation artifacts, durable user corrections, durable Agent Bridge activation records with status, `response_mode`, `stimulus_id`, evidence refs, and harness results, API/CLI status and write surfaces, schema-validated Activity Skill Packs with relevance selection, macOS/Windows Janus desktop panels for posture/explanations/corrections/task repair/scoped mutes/deep-dive decisions/collector health, and focused tests.
- Direct app/SaaS/browser source ingestion now passes through a shared source gate before durable event-log writes, so configured profiles can reject disabled collectors, duplicates, rate-limit overflow, and local activity-policy matches.
- `file_operation_activity` now has best-effort local `file_saved`, `file_renamed`, `file_moved`, `file_opened`, and `file_closed` sources plus macOS FSEvents bridge enrichment.
- `folder_navigation_activity` now has best-effort local `folder_created`, `folder_changed`, `folder_renamed`, and `folder_moved` sources plus macOS FSEvents bridge enrichment.
- `trash_activity` now has best-effort local `file_moved_to_trash`, `folder_moved_to_trash`, `trash_item_deleted`, and `trash_emptied` sources.
- `apps/macos` now includes `HumungousaurFileEvents`; `script/run_macos_file_events.sh` starts it and writes bridge JSONL into `data_dir/collector_spool/`.
- `filesystem`, `downloads`, local context, active window, browser context, lifecycle snapshots, Git polling, and selected environment collectors have local or hybrid source implementations.

Remaining:

- Replace bridge-only contracts with real emitters one family at a time.
- Add Windows `ReadDirectoryChangesW` and Linux `inotify` helpers for parity with the macOS FSEvents file/folder helper.
- Add privileged macOS Endpoint Security, Windows ETW/auditing, and Linux fanotify helpers only for opt-in open/close/access semantics.
- For each remaining collector, add the native/app/browser source helper or mark the exact missing emitter in `docs/COLLECTOR_ARCHITECTURE.md`.
- Add focused tests proving actual source emission, not only bridge ingestion.
- Keep broad collector/semantic/API tests green after every source family.
