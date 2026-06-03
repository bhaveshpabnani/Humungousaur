# Humungousaur

Humungousaur is the local-first agent core for Umang: a safe, extensible desktop assistant runtime that can receive natural-language tasks, call permissioned tools, record audit logs, and grow into voice, browser, OS, and memory workflows.

## Current Slice

This first slice focuses on trust and extensibility:

- model-led structured planner with explicit command fallback
- durable cognitive state for events, goals, persona, and reusable skills
- file/workspace tools
- policy checks before every action
- SQLite audit log
- saved notes under `artifacts/notes`
- CLI for text-command testing

## Quick Start

```powershell
cd Humungousaur
python -m humungousaur run "summarize this project and tell me the next best task" --workspace ..
python -m humungousaur run "summarize PDFs" --workspace .
python -m humungousaur run "research https://example.com" --workspace .
python -m humungousaur run "open browser https://example.com" --workspace .
python -m humungousaur run "show my browser sessions" --workspace . --planner model
python -m humungousaur run "observe browser session SESSION_ID" --workspace . --planner model
python -m humungousaur run "extract pricing from browser session SESSION_ID" --workspace . --planner model
python -m humungousaur run "click observed element link:0 in browser session SESSION_ID" --workspace . --planner model
python -m humungousaur run "type Dev into browser element form:0:field:name in session SESSION_ID" --workspace . --planner model
python -m humungousaur run "find browser text pricing in session SESSION_ID" --workspace . --planner model
python -m humungousaur run "go back in browser session SESSION_ID" --workspace . --planner model
python -m humungousaur run "fill form 0 in session SESSION_ID name=Dev message=Hello" --workspace .
python -m humungousaur run "submit form 0 in session SESSION_ID" --workspace .
python -m humungousaur run "forget browser session SESSION_ID because it is stale" --workspace . --planner model
python -m humungousaur run "check live browser status" --workspace . --planner model
python -m humungousaur run "open https://example.com in a live browser" --workspace . --planner model
python -m humungousaur run "observe live browser session LIVE_SESSION_ID" --workspace . --planner model
python -m humungousaur run "list live browser tabs for session LIVE_SESSION_ID" --workspace . --planner model
python -m humungousaur run "open a new live browser tab in session LIVE_SESSION_ID at https://example.com" --workspace . --planner model
python -m humungousaur run "switch live browser session LIVE_SESSION_ID to tab 1" --workspace . --planner model
python -m humungousaur run "wait for selector button.submit in live browser session LIVE_SESSION_ID" --workspace . --planner model
python -m humungousaur run "query selector select[name=status] in live browser session LIVE_SESSION_ID" --workspace . --planner model
python -m humungousaur run "click live browser element live:0 in session LIVE_SESSION_ID because I chose it" --workspace . --planner model
python -m humungousaur run "type hello into live browser element live:1 in session LIVE_SESSION_ID" --workspace . --planner model
python -m humungousaur run "select approved in live browser dropdown live:2 for session LIVE_SESSION_ID" --workspace . --planner model
python -m humungousaur run "press Enter in live browser session LIVE_SESSION_ID because I want to submit" --workspace . --planner model
python -m humungousaur run "upload report.pdf to live browser file input live:4 in session LIVE_SESSION_ID" --workspace . --planner model
python -m humungousaur run "download from live browser element live:5 in session LIVE_SESSION_ID because I need the export" --workspace . --planner model
python -m humungousaur run "save live browser session LIVE_SESSION_ID as a PDF" --workspace . --planner model
python -m humungousaur run "evaluate JavaScript in live browser session LIVE_SESSION_ID to read document.title" --workspace . --planner model
python -m humungousaur run "save live browser screenshot for session LIVE_SESSION_ID" --workspace . --planner model
python -m humungousaur run "close tab 1 in live browser session LIVE_SESSION_ID because it is stale" --workspace . --planner model
python -m humungousaur run "close live browser session LIVE_SESSION_ID because it is no longer needed" --workspace . --planner model
python -m humungousaur run "system status" --workspace .
python -m humungousaur run "what is my active window" --workspace .
python -m humungousaur run "list visible windows" --workspace . --planner model
python -m humungousaur run "observe the foreground app UI" --workspace . --planner model
python -m humungousaur run "click UI element uia:2 from observation OBSERVATION_ID" --workspace . --planner model
python -m humungousaur run "type hello into UI element uia:3 from observation OBSERVATION_ID" --workspace . --planner model
python -m humungousaur run "scroll down UI element uia:4 from observation OBSERVATION_ID" --workspace . --planner model
python -m humungousaur run "send Ctrl+S because I approved saving the current app" --workspace . --planner model
python -m humungousaur run "switch to window:1234 because I want that app focused" --workspace . --planner model
python -m humungousaur run "resize window:1234 to 800 by 600 at 0,0" --workspace . --planner model
python -m humungousaur run "where is my cursor" --workspace . --planner model
python -m humungousaur run "click screen coordinates 250,300 because I approved that target" --workspace . --planner model
python -m humungousaur run "invoke UIA element uia:5 from observation OBSERVATION_ID" --workspace . --planner model
python -m humungousaur run "maximize window:1234 because I want the app full size" --workspace . --planner model
python -m humungousaur run "inspect Windows virtual desktops" --workspace . --planner model
python -m humungousaur run "move window:1234 to desktop 11111111-1111-1111-1111-111111111111" --workspace . --planner model
python -m humungousaur run "list Windows apps matching notepad" --workspace . --planner model
python -m humungousaur run "launch Windows app Notepad because I want to edit a note" --workspace . --planner model
python -m humungousaur run "read clipboard because I want to summarize copied text" --workspace . --planner model
python -m humungousaur run "write hello to clipboard because I approved preparing paste text" --workspace . --planner model
python -m humungousaur run "open notepad" --workspace .
python -m humungousaur run "capture screenshot for current-screen context" --workspace . --planner model
python -m humungousaur screen-captures --workspace .
python -m humungousaur run "delete screenshot capture screenshot-20260601-120000.png because it is no longer needed" --workspace . --planner model
python -m humungousaur run "remember I prefer concise project updates" --workspace .
python -m humungousaur run "memory about concise project updates" --workspace .
python -m humungousaur run "check external integration status" --workspace . --planner model
python -m humungousaur run "record activity from accessibility text: reviewed browser-use tools" --workspace . --planner model
python -m humungousaur run "search activity for browser-use tools" --workspace . --planner model
python -m humungousaur run "show my activity memory privacy policy" --workspace . --planner model
python -m humungousaur run "exclude Mail from activity memory and keep activity for 7 days" --workspace . --planner model
python -m humungousaur run "prune activity memory older than 7 days because of retention" --workspace . --planner model
python -m humungousaur run "summarize this project" --workspace . --planner model --model gpt-5-mini
python -m humungousaur run "summarize this project" --workspace . --planner model --model-provider openai-chat --model gpt-5-mini
python -m humungousaur run "summarize this project" --workspace . --planner model --model-provider groq
python -m humungousaur run "summarize this project" --workspace . --planner model --model-provider ollama --model llama3.1
python -m humungousaur run "summarize this project" --workspace . --planner model --model-provider grok --model grok-4.3
python -m humungousaur run "system_status {}" --workspace . --planner explicit
python -m humungousaur run "run a local Python analysis that prints the number of markdown files" --workspace . --planner model
python -m humungousaur run "run a local Python analysis with pandas allowed" --workspace . --planner model
python -m humungousaur run "show recent Python interpreter runs" --workspace . --planner model
python -m humungousaur run "show Python interpreter run RUN_ID" --workspace . --planner model
python -m humungousaur run "read result.txt from Python interpreter run RUN_ID" --workspace . --planner model
python -m humungousaur run "show Python interpreter sessions" --workspace . --planner model
python -m humungousaur run "resume Python interpreter session SESSION_ID and replay prior cells" --workspace . --planner model
python -m humungousaur run "run python --version" --workspace .
python -m humungousaur approvals --workspace .
python -m humungousaur approval-edit APPROVAL_TOKEN "{\"argv\":[\"python\",\"-V\"]}" --workspace .
python -m humungousaur approve APPROVAL_TOKEN --workspace .
python -m humungousaur reject APPROVAL_TOKEN --workspace .
python -m humungousaur run "run python --version" --workspace . --approve-high-risk
python -m humungousaur run-activation ..\voice-wakeup\artifacts\recordings\20260601_150000.json --workspace ..
python -m humungousaur run-activation ..\voice-wakeup\artifacts\recordings\20260601_150000.json --workspace .. --harness --response-mode voice_prepare
python -m humungousaur stimulus "summarize this project" --source voice_transcript --response-mode voice_prepare --workspace .
python -m humungousaur stimulus "User looked at a dashboard" --source activity --response-mode silent --workspace .
python -m humungousaur run "say hello there" --workspace .
python -m humungousaur audit --limit 5
python -m humungousaur plans --limit 5
python -m humungousaur memory --limit 5
python -m humungousaur memory-search "project"
python -m humungousaur memory-summary --period today
python -m humungousaur memory-profile
python -m humungousaur run "cognitive_state {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_briefing_prepare {\"purpose\":\"current\",\"horizon_hours\":24}" --workspace . --planner explicit
python -m humungousaur run "cognitive_briefing_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_memory_curate {\"purpose\":\"memory_hygiene\",\"max_archive\":5,\"max_summaries\":2}" --workspace . --planner explicit
python -m humungousaur run "cognitive_curation_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_skill_evolve {\"purpose\":\"skill_review\",\"max_updates\":5,\"max_new_skills\":2}" --workspace . --planner explicit
python -m humungousaur run "cognitive_skill_evolution_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_persona_evolve {\"purpose\":\"persona_review\"}" --workspace . --planner explicit
python -m humungousaur run "cognitive_persona_evolution_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_self_review {\"purpose\":\"autonomy_check\"}" --workspace . --planner explicit
python -m humungousaur run "cognitive_self_review_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_focus_update {\"mode\":\"monitoring\",\"summary\":\"Tracking open follow-ups.\",\"pinned_context\":[\"follow-ups\"]}" --workspace . --planner explicit
python -m humungousaur run "cognitive_knowledge_record {\"kind\":\"procedure\",\"text\":\"Use blockers-first updates for project status.\",\"source\":\"user\"}" --workspace . --planner explicit
python -m humungousaur run "cognitive_learning_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_specialist_record {\"name\":\"File reviewer\",\"purpose\":\"Read files and return verified evidence.\",\"contract\":\"Use read-only tools and do not infer file contents without reading.\",\"tools\":[\"read_file\"],\"success_criteria\":[\"Requested file evidence is returned.\"]}" --workspace . --planner explicit
python -m humungousaur run "cognitive_reflection_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_consolidation_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_recovery_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_wakeup_schedule {\"delay_seconds\":300,\"text\":\"check the queued follow-up\",\"response_mode\":\"silent\",\"reason\":\"keep future work visible\"}" --workspace . --planner explicit
python -m humungousaur run "cognitive_wakeup_status {\"status\":\"scheduled\"}" --workspace . --planner explicit
python -m humungousaur run "cognitive_wakeup_cancel {\"wakeup_id\":\"WAKEUP_ID\",\"reason\":\"no longer needed\"}" --workspace . --planner explicit
python -m humungousaur run "create a durable goal for tomorrow's project review" --workspace . --planner model
python -m humungousaur run "autonomous_queue_status {}" --workspace . --planner explicit
python -m humungousaur run "autonomous_cycle_run {\"max_cycles\":1}" --workspace . --planner explicit --approve-high-risk
python -m humungousaur autonomous-status --workspace .
python -m humungousaur autonomous-loop --workspace . --max-cycles 10 --stop-after-idle-cycles 2
python -m humungousaur benchmark --iterations 3
python -m humungousaur index --rebuild --json
python -m humungousaur serve --workspace . --port 8765
python -m unittest discover -v
```

## Product Direction

Engineering guidance lives in `docs/ENGINEERING_PRINCIPLES.md` and the strict global intelligence rule lives in `docs/GLOBAL_AGENT_INSTRUCTIONS.md`: broad assistant behavior should be model-led and schema-driven through OpenAI, Groq, Ollama, Grok, or another configured OpenAI-compatible client. Do not implement cognition, routing, delegation, response strategy, memory decisions, experience consolidation, skill evolution decisions, persona evolution decisions, metacognitive self-review, persona update decisions, future wakeup/timing decisions, adaptive recovery decisions, completion judgment, proactive assistance, or task decomposition with pattern matching, regex intent maps, keyword lists, static routing tables, hardcoded constant routing, command templates, brittle handcrafted cases, or deterministic natural-language inference. Deterministic safeguards are reserved for explicit fallback commands, safety checks, schema validation, audit persistence, and evidence-boundary enforcement.

The long-term human-like assistant architecture lives in `docs/COGNITIVE_AGENT_ARCHITECTURE.md`. The first cognitive runtime layers are implemented as durable event, goal/task, focus, persona, persona evolution, self-review, knowledge, learning, consolidation, curation, skill evolution, recovery, briefing, wakeup, skill, specialist, and reflection stores; planner-visible cognitive state tools; model-led attention, reflection, consolidation, curation, skill evolution, persona evolution, self-review, recovery, and briefing decisions with explicit fallback; and a bounded autonomous runtime loop with queued events, due wakeups, task graphs, explicit delegation, pause/interrupt boundaries, completion gates, evidence-backed learning, adaptive repair tasks, current-work briefings, model-led memory hygiene, model-led reusable-skill review, model-led persona/user-model review, model-led metacognitive risk and uncertainty review, model-led experience consolidation, idle stopping, and cycle summaries.

The voice wake-word module should call this runtime after transcription:

```text
wake word -> transcribe -> interaction harness -> orchestrator -> tools -> audit log -> text/voice response
```

Current voice bridge:

```powershell
cd ..\voice-wakeup
python -m voice_wakeup dispatch-activation .\artifacts\recordings\20260601_150000.json --agent-api-url http://127.0.0.1:8765
```

Interaction harness behavior:

- Direct user text and voice transcripts are treated as explicit stimuli and normally produce a response.
- Passive activity, accessibility, OCR, browser, and audio snippets are recorded as context; they only trigger analysis when upstream structured metadata marks them as actionable.
- Response modes are `text`, `voice_prepare`, `voice_speak`, and `silent`.
- `voice_response_prepare` writes a local spoken-response artifact under the data directory; `voice_speak` uses the local OS TTS engine where supported.

The rule is simple: every future capability becomes a tool with a risk level, policy check, execution result, and audit event.
Tools also expose JSON-schema-style `input_schema` metadata, so model planning can select and populate tool calls from explicit contracts instead of fragile payload guessing. The executor validates those inputs before approval or execution.
Tools are grouped by capability (`activity`, `files`, `browser`, `integrations`, `memory`, `os`, `plugins`, `screen`, `shell`, `system`, `voice`) so the permissions surface can stay understandable as the product grows.
Before planning, the orchestrator gathers a compact local context bundle: workspace paths, system health, active-window metadata, recent memory, recent browser sessions, and safety flags. This context is treated as untrusted data and its collection is recorded in the run timeline.

External reference projects are integrated through explicit adapters, not copied wholesale:

- `external_integrations_status` checks local development availability for Browser Use, Screenpipe, Windows-Use, and Open Interpreter.
- `activity_ingest`, `activity_search`, `activity_policy`, `activity_policy_update`, and `activity_prune` implement a native Screenpipe-inspired activity-memory schema with local retention and privacy exclusions inside Umang.
- `plugin_manifests` and `plugin_manifest` discover local JSON plugin manifests from `.umang/plugins` and the local data directory; manifest-declared tools are visible to planning and permissions but blocked until a trusted runtime exists.
- Reference repos can be cloned under `external_repos/` for code inspection; that folder is ignored by git.

## Model Configuration

Model planning is the preferred intelligent orchestration path; the offline fallback accepts only explicit tool commands or JSON plans. The workspace `.env` is authoritative for that workspace and can override stale process environment values. Keep real keys out of git.

Supported planner transports:

- `auto`: prefer OpenAI when `OPENAI_API_KEY` is present, then Groq when `GROQ_API_KEY` is present, otherwise Ollama.
- `openai-responses`: OpenAI Responses API with structured JSON output.
- `openai-chat`: OpenAI Chat Completions compatible JSON output.
- `groq`: Groq OpenAI-compatible Chat Completions endpoint.
- `ollama`: local Ollama OpenAI-compatible endpoint, defaulting to `http://127.0.0.1:11434/v1`.
- `grok`: xAI/Grok Chat Completions endpoint.
- `local-openai`: legacy local OpenAI-compatible endpoint alias.

Useful local environment variables:

```text
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
GROQ_API_KEY=
GROQ_BASE_URL=https://api.groq.com/openai/v1
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODEL=llama3.1
XAI_API_KEY=
XAI_BASE_URL=https://api.x.ai/v1
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_API_KEY=local
```

## Local API

The daemon binds to loopback by default:

```powershell
python -m humungousaur serve --workspace . --port 8765
```

Open the dashboard at `http://127.0.0.1:8765/`.

Dashboard runs are queued asynchronously. Use the `Stop` control to request cooperative cancellation; the timeline records both the cancellation request and the safe checkpoint where the run stopped.
Approval decisions execute or reject the pending action against the original run, so the source timeline remains the single audit trail for the task.
The dashboard can select the planner, model provider, model name, optional base URL override, API-key environment-variable name, and dry-run mode for each run. It never asks for raw API keys; put secrets in `.env` or the process environment and pass only the env var name.

Core endpoints:

- `GET /health`
- `GET /system/status`
- `GET /screen/captures`
- `GET /permissions`
- `GET /benchmarks?iterations=3&q=project`
- `GET /autonomous/status`
- `GET /index/status`
- `GET /browser/sessions`
- `GET /browser/sessions/{session_id}`
- `POST /index/rebuild`
- `POST /permissions/read-roots/add`
- `POST /permissions/read-roots/remove`
- `POST /runs`
- `POST /runs/async`
- `POST /autonomous/cycles`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/timeline`
- `POST /runs/{run_id}/cancel`
- `GET /plans`
- `GET /plugins`
- `GET /memory`
- `GET /memory/search?q=...`
- `GET /memory/summary?period=today&q=...`
- `GET /memory/profile`
- `GET /approvals`
- `POST /approvals/{token}/approve`
- `POST /approvals/{token}/reject`

## Safety Posture

- Model or provider output is untrusted until parsed and tool-allowlisted.
- Planner context is compact, local, and treated as untrusted data; collection is audited before tool execution.
- Tool input contracts are explicit, visible to the model planner and permissions dashboard, and enforced before policy approval or execution.
- High-risk tools pause with an approval request by default.
- Pending approvals can be edited before approval; replacement tool input is schema-validated and audited on the source run.
- Approved commands are still constrained by command allowlists, shell command profiles, and workspace boundaries.
- Local plugin manifests are metadata-only by default: declared tools appear in the registry as blocked placeholders until an explicit trusted plugin runtime is added.
- Permissions are visible through the dashboard and `GET /permissions`.
- Capability groups summarize tool count, approval gates, directly allowed tools, and highest risk.
- Extra read roots are stored locally in `permissions.json` under the data directory.
- Explicit memory notes are stored locally in SQLite and can be searched by the agent as a tool.
- Memory summaries can recap today, yesterday, the last week, or recent local events without sending memory data anywhere.
- Explicit preferences, facts, workflows, and task notes are projected into a local user profile and included in model planning context.
- File listing and workspace search scan every allowed read root by default.
- PDF listing, reading, and summarization stay inside allowed read roots and respect file-size limits.
- Web research is read-only, HTTP(S)-only, timeout-bounded, size-bounded, blocks credentials/private networks, and treats page content as untrusted data.
- Browser sessions persist page state, images, and local history, and can navigate numbered links or observed link elements while preserving the same URL safety checks.
- Browser observation, extraction, observed-element clicking, field typing, and text finding follow Browser Use-style indexed page state while remaining native Umang tools.
- Browser session listing returns local metadata only, so model plans can inspect available sessions without receiving page text.
- Browser form filling saves a local draft first; form submission is high-risk and pauses for explicit approval.
- Browser session forgetting is approval-gated and deletes only local browser-session metadata and drafts.
- Live browser control is an optional native Playwright-backed layer: `browser_live_status` reports availability, `browser_live_open` starts an in-process page, and `browser_live_observe` returns live DOM element ids without relying on brittle natural-language selectors.
- Live browser search, wait, tab listing/switching, new-tab opening, text scrolling, dropdown option listing, and CSS selector queries are explicit bounded tools rather than unconstrained browser automation.
- Live browser click, coordinate click, typing, dropdown selection, key press, file upload, download, PDF export, JavaScript evaluation, tab close, screenshots, and session close actions are approval-gated where they mutate page or browser state.
- Live browser uploads can only use files from allowed read roots and respect file-size limits; downloads, PDFs, and screenshots are saved locally under the data directory and do not inline file bytes.
- Activity ingestion is approval-gated because screen/audio/app context can expose sensitive local history.
- Activity policy settings are stored locally and can disable sources, exclude apps/window terms/text terms/domains, set retention days, and prune old activity events after approval.
- Activity privacy exclusions are enforced before ingestion and when activity appears through activity search, general memory search, planning context, and memory summaries.
- OS observation can inspect the foreground window title without reading screen content.
- Visible-window listing reads top-level window metadata only; foreground UI Automation observation is approval-gated because element names and values can expose sensitive screen content.
- OS UI actions use short-lived observed element/window ids, are approval-gated, and send only explicit click/type/scroll/shortcut/window actions through the audited tool executor.
- Desktop app launching is allowlisted and high-risk, so it pauses for explicit approval before opening apps.
- Screenshot capture is a high-risk `screen` capability: it pauses for approval, saves PNGs locally under the data directory, and does not inline image bytes in responses.
- Screenshot capture metadata is listed separately; the API and dashboard expose filenames, dimensions, timestamps, reasons, and active-window titles without serving image bytes.
- Screenshot deletion is also high-risk and approval-gated; it accepts only registry filenames and deletes the PNG plus JSON sidecar inside the local screenshot directory.
- `python_interpreter` provides an Open Interpreter-inspired local analysis primitive: it is high-risk, approval-gated, timeout-bounded, runs in a child Python process, blocks subprocesses, blocks network by default, reads only allowed read roots, writes only allowed write roots, and defaults to stdlib-only imports.
- Interpreter imports support explicit policies: `stdlib`, `allowlist` with approved package names, or `all` for deliberately trusted runs.
- Interpreter filesystem writes use explicit sandbox profiles: `read_only` writes only run artifacts, `data_write` writes configured data roots, `workspace_write` can edit the workspace, and `trusted_dev` can write configured allowed roots.
- Interpreter sessions group related Python runs under local session manifests. A later approved run can set `replay_session=true` to replay prior successful cells before the current cell for lightweight variable continuity.
- Python interpreter runs write local manifests with status, stdout/stderr tails, policy paths, and artifact metadata. `python_interpreter_runs`, `python_interpreter_run`, and `python_interpreter_artifact` expose bounded metadata and manifest-listed text artifacts without broad filesystem reads.
- System status checks expose local runtime and disk pressure before indexing, audit logs, or benchmarks fail.
- Read-root permission edits automatically rebuild the local file index; file changes mark the index stale and search falls back to live scanning until the next rebuild.
- Local benchmarks cover permissions, explicit fallback planning, planning context, schema validation, file/search tools, memory search/summary/profile tools, OS observation, screenshot dry-run and metadata listing, web/browser guards, indexing, and a dry-run agent task.
- Retrieved file/web/page content must be treated as data, not instructions.
- Model planning uses structured JSON and falls back only to explicit tool commands or JSON plans if validation fails.
- Provider errors are redacted before they are written to plan traces.
