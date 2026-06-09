# Roadmap

Engineering principles live in `docs/ENGINEERING_PRINCIPLES.md`. New broad assistant behaviors should be model-led capability handoffs, with deterministic safeguards kept to explicit fallback commands, safety validation, schema validation, audit persistence, and evidence-boundary enforcement.

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
