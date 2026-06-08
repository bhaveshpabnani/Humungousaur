# Skill Capability Goal Progress

Last updated: 2026-06-08

## Goal

Smoke test each skill task one by one, identify skills that are only prompt/procedure, and add native Humungousaur tools, scripts, artifacts, and smoke coverage wherever a capability is missing or too weak. The target is not just skill text: every important skill should be backed by executable, inspectable, native capability surfaces that the agent can call through orchestration.

## Current Status

- Repository state reviewed during the final thin-skill hardening slice.
- Current workspace skill count: `132`.
- Current tool-domain folders: `33`.
- Latest full skill smoke result: `557` sections, `0` failures.
- Latest per-skill audit matrix: `132` skills audited, `132` native-capable or script-backed, `0` thin-tool-map skills needing deeper workflow/safety/verification detail, `0` prompt-only, `0` unresolved Tool Map entries, `0` attention items.
- Latest per-skill task-smoke coverage: `132` skills covered, `132` directly task-smoked, `0` composition-smoked, `0` pending task-smoke skills, `221` native tools seen in smoke evidence, `0` skills with mapped native tools still pending narrower smoke.
- Latest live-boundary coverage: `132` skills covered, `136` approval/medium/high-risk boundary tools tracked, `0` skills with missing boundary evidence, `28` skills with dry-run-only boundaries, and `128` skills needing live or credentialed validation for daily-use certainty.
- The goal is still active. The current work proves strong incremental progress, but not exhaustive completion across every skill and external/live integration.

## Completed Capability Slices

These slices have been implemented, smoke-tested, regression-tested, committed, and pushed to `main`.

| Commit | Slice | What Was Added |
| --- | --- | --- |
| `9c99ca9` | Productivity skill wiring | Initial productivity skill smoke and tool routing. |
| `269f405` | Skill maps and smoke expansion | Broader skill map validation and smoke coverage. |
| `3ae34a3` | Office artifacts | Native DOCX and PPTX create/inspect tools. |
| `b8ec48d` | Analysis artifacts | Native CSV profiling, chart artifact, and business report support. |
| `7ac4db5` | Writing skills and async hardening | Native writing artifacts and more robust async execution path. |
| `d593f2b` | Channel action preparation | Native channel manifest/setup/status/message preparation/send gating. |
| `53fad76` | PDF and OCR | PDF merge/extract/read smoke and OCR provider status surface. |
| `908275d` | RSS monitoring | Native RSS/feed monitoring tools and smoke coverage. |
| `3f89c30` | Transcript summaries | Native transcript/audio/video summary artifacts. |
| `cea957e` | Notion and Airtable packets | Native operation packet preparation/inspection without importing upstream packages. |
| `2a927b2` | Research citations | Literature set and bibliography/citation artifact support. |
| `c60f3bd` | Travel planning | Travel itinerary/map-style planning artifacts. |
| `8e06e43` | Commerce safety | Shopping comparison and purchase safety artifacts. |
| `03b2803` | Personal planning | Contact notes, daily planning, priority/focus-related artifacts. |
| `ef662a2` | Design system artifacts | Brand-guideline and theme-pack create/inspect tools with Markdown/JSON/CSS sidecars. |
| `1e296e1` | Visual artifacts | Diagram, Mermaid, Excalidraw-compatible JSON, and infographic plan tools. |
| `045cb2f` | Presentation planning | Native presentation plan create/inspect tools with audience, goal, narrative arc, slide plan, visual intent, speaker notes, evidence refs, risks, and status. |
| `b2f6679` | Google Workspace operation packets | Native local packets for Calendar, Drive, Docs, Sheets, and Gmail-style Google operations, with OAuth scopes, approval requirements, payload previews, and `not_executed` status. |
| `49e8598` | Network and DNS safety diagnostics | Native bounded DNS lookup, HTTP endpoint check, and single-port TCP connectivity probe tools. |
| `51b4d32` | Creative writing and songwriting artifacts | Native creative brief, song structure, and creative revision packet artifacts with originality guardrails. |
| `6d13f22` | Security review artifacts | Native dependency inventory, secret-scan report, prompt-injection review, and approval-policy review artifacts. |
| `e35444f` | GitHub and CI workflow artifacts | Native GitHub issue packets, PR packets, CI failure reports, repo-state reports, artifact inspection, skill docs, and smoke coverage without requiring live GitHub credentials. |
| current slice | Desktop channel-operations integration | Windows app allowlist/group allowlist onboarding, outbound channel message preparation, approval-gated send flow, API channel-message routes, and API regression coverage. |
| current slice | Desktop channel onboarding | Backend channel setup requirements endpoint plus Windows app provider-specific required secrets, setup steps, delivery/policy/runtime summaries, and setup doctor results. |
| current slice | Channel integration smoke | Native non-sending channel readiness report covering setup/status, doctor blockers, prepared outbox, dry-run send wiring, listener state, API route, app button, skill docs, and smoke coverage. |
| current slice | Desktop runtime and approvals | Windows app Runtime page with recent runs, pending approvals, timeline details, approve/reject actions, and run cancellation. |
| current slice | Per-skill capability audit matrix | Native skill audit tool writes Markdown/JSON artifacts, resolves exact Tool Maps, classifies all 132 workspace skills, and is now part of full skill smoke. |
| current slice | Channel skill hardening | Shared channel operations plus Slack, Telegram, Discord, and WhatsApp skills now document native workflows, safety/approval rules, implementation boundaries, and verification against native channel smoke. |
| current slice | Browser/computer-use skill hardening | Browser/computer-use, OpenAI-style computer-use, and Claude-style computer-use skills now document native observe-act-verify workflows, approval boundaries, implementation limits, and verification against browser/OS smoke and tests. |
| current slice | Cognition/orchestration skill hardening | Self-assessment, self-reflection, team orchestration, worker handoff, autonomous loop, memory metabolism, persona evolution, taskflow, task tracking, priority review, and wakeup scheduling now document safety/approval and native-boundary contracts. |
| current slice | Voice/audio/meeting skill hardening | Speech operations, local speech, spoken response style, voice loop, voice wakeup, voice call gateway, audio summaries, meeting transcription, meeting follow-up, and music/sound generation now document native workflows, safety rules, native implementation boundaries, and verification expectations. |
| current slice | Final thin-skill hardening | Ambient room context, bot-loop protection, capability audit/surfaces, channel gateway, Codex/coding delegation, daily planning, gog, session wrap-up, skill authoring/security review, and wacli now meet native workflow, safety, boundary, and verification standards. |
| current slice | Per-skill task-smoke coverage | Full skill smoke now writes Markdown/JSON task-coverage artifacts, records exact native tool evidence, directly task-smokes 131 skills, composition-smokes the remaining wrapper skill, and reports 0 skills without task-smoke evidence. |
| current slice | Foundational native-tool smoke | Added safe/dry-run smokes for file/search/shell/code catalogs, memory, activity, conversation, email, cognition review, skill forge, and canvas tools, raising native tools seen in evidence from 148 to 177 and reducing skills with pending mapped tools from 116 to 72. |
| current slice | Complete mapped-tool smoke closure | Added direct safe/dry-run evidence for live-browser observe/click/type/scroll/tabs/search/save-PDF/close, channel send/listener tick, voice STT/TTS, Codex CLI status/run, Lobster approval, OS element/clipboard controls, plugin setup/manifests, browser extraction aliases, Python artifact readback, taskflow cognition tools, persona/briefing/curation status, and PDF optional-dependency boundaries, raising native tools seen in evidence to 221 and reducing mapped pending native tools to 0. |
| current slice | Live-boundary coverage artifact | Full skill smoke now writes Markdown/JSON live-boundary coverage artifacts that separately track approval-gated, medium-risk, and high-risk mapped tools, proving `0` missing local boundary evidence while explicitly flagging `128` skills that still need credentialed/live validation. |

## Current Native Capability Areas

Humungousaur now has native tool domains for:

- Activity and stimuli ingestion
- Analysis and business reporting
- Browser and live browser control
- Capability/tool discovery
- Channels and channel action gating
- Code execution and interpreter artifacts
- Codex delegation and skill import/sync
- Commerce and purchase safety
- Content/transcript summaries
- Conversation response preparation
- Cognition, memory curation, persona evolution, automations, and multi-agent coordination
- Creative writing, songwriting, and revision artifacts
- Design systems and theme packs
- Desktop app channel setup requirements, setup doctor, non-sending channel smoke, allowlists, runtime settings, runtime runs/timelines, approval actions, voice settings, and outbound channel operations
- External integration status surfaces
- Files, PDFs, OCR, and shell/file utilities
- GitHub issue/PR/CI/repo-state workflow artifacts
- Media/storyboard/music/video planning
- Memory search/write/summary/profile
- Network/DNS/HTTP/TCP diagnostics
- Office DOCX/PPTX/presentation plan artifacts
- OS/screen/keyboard/mouse/window/clipboard control surfaces
- Personal planning and contact notes
- Plugin discovery
- Productivity operations including Gmail draft, XLSX, Notion, Airtable, and Google Workspace operation packets
- Research citation/literature artifacts
- Security/dependency/secret/prompt-injection review artifacts
- Skills, scripts, skill catalog/read/run surfaces
- Skill capability audit matrix artifacts
- System health/status
- Travel planning
- Visual diagram/infographic artifacts
- Voice provider/STT/TTS/wakeup loop surfaces
- Workflow tools: diffs, JSON LLM tasks, output compaction, typed approval workflows, canvas A2UI
- Writing drafts and follow-up packets

## Verification So Far

The recurring verification pattern for each completed slice has been:

- Focused unit tests for the new tools.
- Global tool-catalog/schema tests.
- Full skill smoke through `scripts.smoke_skills`.
- Full pytest regression.
- `git diff --check`.
- Commit and push to `origin/main`.

Latest verified results:

- Full skill smoke after live-boundary coverage slice: `557` sections, `0` failures.
- Per-skill task coverage artifact after the same smoke: `132` skills, `132` direct task-smoked, `0` composition-smoked, `0` pending task-smoke, `221` native tools seen in smoke evidence, `0` skills with mapped native tools still pending narrower smoke, `0` unresolved Tool Maps.
- Live-boundary coverage artifact after the same smoke: `132` skills, `136` boundary tools tracked, `111` boundary tools seen in smoke evidence, `0` skills with missing boundary evidence, `28` skills with dry-run-only boundaries, `128` skills needing live or credentialed validation.
- Focused regression after mapped-tool smoke closure slice: `125 passed`, `1 skipped`.
- Full regression after mapped-tool smoke closure slice: `393 passed`, `6 skipped`, `8 warnings`, `264 subtests passed`.
- The warnings are from `openpyxl` datetime deprecation during XLSX tests, not from the new skill slices.

## Still To Do

The following areas still need one-by-one hardening or deeper exploration. They are ordered roughly by current thinness, user value, and risk.

### 1. Google Workspace Live Execution And Desktop Onboarding

Current status: local Google Workspace operation packets are being added for Calendar, Drive, Docs, Sheets, and Gmail-style operations. Remaining work is live adapter execution and desktop configuration/onboarding.

Needed work:

- Desktop-app configuration/onboarding surfaces for provider credentials.
- OAuth token storage and refresh flow.
- Guarded live execution after explicit approval.
- Browser-assisted fallback smoke where native OAuth is not configured.
- Live Calendar/Drive/Docs/Sheets/Gmail smoke when credentials are available.

### 2. Creative Writing And Songwriting Publishing And Audio Follow-Through

Current status: native creative brief, song structure, and revision packet artifacts are being added. Remaining work is deeper drafting, audio generation handoff, and publishing/approval flows.

Needed work:

- Richer long-form drafting workflows with model-led revision loops.
- Audio generation provider handoff from song structures after explicit approval.
- Publishing/channel packet integration for final creative outputs.
- Optional plagiarism/similarity/originality review against user-provided references.

### 3. Network And DNS Live Change Management

Current status: native diagnostic tools are being added for DNS lookup, HTTP endpoint checks, and single-port TCP probes. Remaining work is safe live change management for DNS/proxy/firewall/tunnel settings.

Needed work:

- Native rollback-plan artifact for DNS/proxy/firewall/tunnel changes.
- Approval-gated setting change packets for Windows DNS/proxy/firewall operations.
- Admin privilege detection and blocked-state reporting.
- Before/after diagnostics for approved live changes.

### 4. GitHub And CI Live Execution

Current status: local issue packets, PR packets, CI failure reports, repo-state reports, artifact inspection, docs, and smoke coverage are implemented. Remaining work is live GitHub connector/CLI execution and polling.

Needed work:

- Optional live GitHub connector tests when credentials are configured.
- Current PR/CI polling and status refresh through approved `gh` or connector paths.
- Approval-gated issue posting, PR opening, PR commenting, labeling, and check summaries.
- Desktop UX for GitHub account state and live action approval.

### 5. Security And Dependency Live Scanner Integration

Current status: native local review artifacts are being added for dependency inventory, secret-scan reports, prompt-injection reviews, and approval policy reviews. Remaining work is live scanner integration and richer repository-wide automation.

Needed work:

- Native wrappers for approved external scanners.
- Repository-wide dependency graph extraction from lockfiles.
- GitHub/CI integration for security findings.
- Desktop approval UX for risky install/scanner/network actions.

### 6. Delegation Skills

Current weak signal: Codex delegation is stronger, but Claude/opencode delegation remains partly generic.

Needed work:

- Native delegation plan/packet format shared across Codex, Claude Code, opencode, and worker handoff.
- Clear capability status for unavailable external CLIs.
- Smoke tests that verify non-live planning packets and status detection.

### 7. Local And Live Provider Testing

Current weak signal: many local/offline surfaces exist, but live provider coverage depends on installed models, keys, and runtime state.

Needed work:

- Repeat Ollama model detection and local model smoke.
- Local STT/TTS smoke using the installed voice assets where available.
- OpenAI/Groq smoke only through configured desktop settings, not hardcoded `.env` defaults for user-facing provider choices.
- Deepgram/ElevenLabs live smoke where credentials and network allow it.
- Explicit failure docs for provider unavailable/blocked states.

### 8. Desktop App End-To-End

Current status: the Windows app exposes runtime start/stop, recent runs, timeline details, approval approve/reject actions, run cancellation, provider/model settings, voice settings, provider-aware channel setup requirements, channel setup doctor, non-sending channel integration smoke, channel allowlists, listener status, inbound preview, prepared outbound messages, and approval-gated channel sends. Remaining work is full live validation and richer daily-use panels.

Needed work:

- Runtime start/stop/status from the app.
- Voice wakeup/STT/agent/TTS end-to-end through the app.
- Tool execution visibility, run timelines, cancellation, and approval UX.
- Full app smoke with chat message, voice message, channel message, OS/browser task, and response.

### 9. Live Channel Integrations

Current status: channel manifests, setup requirements, setup/status, setup doctor, non-sending integration smoke, listener status, webhook ingest, inbound preview, prepared outbox, allowlists, and approval-gated outbound send are wired through the backend and Windows app. Live provider-specific execution still needs credentialed smoke.

Needed work:

- Telegram bot token onboarding and live receive/send smoke.
- Slack app token/signing secret onboarding and MPIM/group behavior checks.
- Discord bot onboarding and DM/server receive/send smoke.
- WhatsApp QR/pairing state flow and safe outbound gating.
- Bot loop protection tests.
- Ambient room context tests for channels that support it.

### 10. Resolve Exhaustive Skill Audit Findings

Current status: the native audit matrix now proves Tool Map resolution and implementation classification across all 132 skills, and the full smoke now writes per-skill task-coverage artifacts. Current task coverage is 132 direct task-smoked skills, 0 composition-smoked wrapper skills, 0 pending task-smoke skills, 221 native tools seen in smoke evidence, 0 skills with mapped native tools still pending narrower smoke, and 0 unresolved Tool Map entries.

Needed work:

- Keep mapped-tool smoke coverage green as skills evolve, and add credentialed/live smoke for tools whose local evidence is intentionally dry-run, prepared, or provider-gated.
- Flag and live-test credentialed/provider-backed capabilities that currently only have local, dry-run, or prepare/approve evidence.
- Prioritize high-value assistant live paths first: Google Workspace, channels, desktop/OS/browser, voice, coding/delegation, security, memory/cognition.

## Open Questions To Explore

- Which skills should have live external execution versus local prepare/approve/send packets only?
- Which skills need durable background daemons rather than one-shot tools?
- Which tools should become first-class desktop app panels?
- Which live channels should be supported first for daily use?
- How much local model capability is acceptable before hosted provider fallback is needed?
- What is the minimum reliable end-to-end daily assistant loop: wake, hear, plan, act, speak, remember, and follow up?

## Suggested Next Slices

1. Google Workspace native operation packets.
2. Network/DNS safety diagnostics.
3. Creative writing/songwriting artifacts.
4. Security/dependency/prompt-injection artifact tools.
5. Desktop app settings and runtime flow integration.
6. Live channel onboarding and smoke tests.
7. GitHub live connector and CI polling.

## Definition Of Done For This Goal

The goal should only be considered complete when:

- Every skill has a detailed `Tool Map` with native Humungousaur tools or clearly documented external/live boundaries.
- Every important skill task has at least one representative smoke test.
- Prompt-only skills have been converted into native tools, scripts, artifacts, or explicit safe operation packets where appropriate.
- Live integrations are either tested end-to-end or explicitly marked as unavailable with provider/setup reason.
- The desktop app can configure and run the core assistant loop end-to-end.
- Full skill smoke and full regression are green after the final slice.
