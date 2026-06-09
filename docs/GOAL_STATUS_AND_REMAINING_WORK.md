# Humungousaur Goal Status And Remaining Work

Last updated: 2026-06-09

## Goal Scope

This goal is to make Humungousaur a practical personal assistant platform, not a prompt-only demo. The work includes native tools, granular skill implementations, browser and Windows control, voice wakeup/STT/TTS, channels, desktop configuration, local and hosted model providers, cognition, memory, orchestration, approvals, and smoke coverage.

The core standard for this goal is:

- Prefer native Humungousaur implementations over direct imports from OpenClaw, Hermes, Open Interpreter, Windows-use, or other references.
- Use structured tool schemas, capability packets, artifacts, and model-led reasoning instead of brittle keyword, regex, or hardcoded command routing.
- Make each skill executable or inspectable through native tools, scripts, artifacts, packets, or clearly documented live-integration boundaries.
- Keep dangerous or external-visible work approval gated.
- Verify each slice with focused tests, full skill smoke, full regression, diff hygiene, commit, and push.

## Current Repository Status

- Branch: `main`.
- Last fully pushed capability commit before this slice: `e036e75 Expand foundational skill smoke coverage`.
- Latest documented full skill smoke: `558` sections, `0` failures.
- Latest documented full regression: `466` tests OK, `6` skipped for `python3 -m unittest discover -v`.
- Latest release source preflight: `190` checks passed, `0` warnings, `0` failures for `python3 script/verify_release_readiness.py --require-website --release-tag v0.1.0`; the preflight now requires `docs/GLOBAL_AGENT_INSTRUCTIONS.md`, `docs/COGNITIVE_AGENT_ARCHITECTURE.md`, and `docs/AGENT_SKILL_AUTHORING_STANDARD.md` as public release sources and checks the global model-led intelligence rule, cognitive runtime loop, frontmatter, tool-map, safety-boundary, verification, native-tooling contracts, release workflow, desktop parity, desktop runtime smoke, website publication, and release asset gates.
- Latest GitHub release preflight: `106` checks passed, `1` warning because no latest GitHub release exists yet.
- Latest strict local artifact preflight: `153` checks passed, `2` failures because `Humungousaur-Windows.zip` is not present locally and `checksums.txt` does not yet contain the Windows checksum row.
- Latest focused release-readiness unit suite: `29` tests passed with `3` subtests for `python3 -m pytest tests/test_release_readiness.py -q`, including the real-world smoke runner, publication-state gate requirements, sibling website publication-gate integration, combined runtime-plus-website publication error aggregation, required architecture/global-instruction/skill-authoring-standard tracking, source hygiene, oversized publish-candidate checks, package scripts, signature/notarization checks, release report checks, and workflow permission checks.
- Latest focused planner suite: `62` tests passed for `python3 -m pytest tests/test_planning.py -q`. Model-client JSON instructions plus core planning, ReAct, selector, repair, and planner-review prompts now load from `humungousaur/resources/prompts/planning.yaml` as named templates; grounded source URL repairs now skip redundant live-navigation model review once the repaired URL matches prior observations.
- Latest focused model-client suite: `4` tests passed for `python3 -m pytest tests/test_model_clients.py -q`. OpenAI Responses and OpenAI-compatible Chat JSON instruction messages now load from the bundled `model_client_json_instructions` template instead of inline string literals.
- Latest focused cognition suite: `38` tests passed for `python3 -m pytest tests/test_cognition.py -q`. Core attention, specialist delegation, task reflection, memory consolidation, self-review, interaction review, priority review, memory curation, skill evolution, skill forge, persona evolution, briefing, recovery, environment review, and commitment review prompts now load from `humungousaur/resources/prompts/cognition.yaml` as named templates.
- Latest focused tool suite: `42` tests passed and `3` skipped for `python3 -m pytest tests/test_tools.py -q`. Codex CLI delegation and Codex skill-sync prompts now load from `humungousaur/resources/prompts/codex.yaml` as named templates.
- Latest focused workflow suite: `8` tests passed for `python3 -m pytest tests/test_workflow_tools.py -q`. Generic JSON workflow tasks and tokenjuice model summaries now load from `humungousaur/resources/prompts/workflow.yaml` as named templates.
- Latest focused model-orchestrator suite: `21` tests passed for `python3 -m pytest tests/test_model_orchestrator.py -q`. Final user-facing response synthesis now loads from `humungousaur/resources/prompts/response.yaml` as a named template, and the model-planning loop guidance now loads from `humungousaur/resources/prompts/planning.yaml` instead of inline orchestration text.
- Latest broader focused backend suite: `207` tests passed, `3` skipped, and `267` subtests passed for `python3 -m pytest tests/test_cognition.py tests/test_planning.py tests/test_tools.py tests/test_workflow_tools.py tests/test_model_orchestrator.py tests/test_model_clients.py tests/test_release_readiness.py tests/test_workspace_skill_format.py -q`.
- Latest open-source hygiene scan: `python3 script/verify_open_source_hygiene.py` scanned `529` agent and website publish candidates, including tracked and untracked non-ignored files, likely secrets, signing material, generated local state, and oversized source candidates, with `0` failures.
- Latest real-world safe smoke: `python3 scripts/smoke_real_world_tasks.py --workspace .` passed, and `python3 scripts/smoke_real_world_tasks.py --workspace . --live-browser` passed against a local browser target. The script covers system status, browser status/opening, app-launch preparation, OS observation preparation, and Calendar-style Google Workspace operation preparation without calling live Google APIs.
- Latest website download readiness: `npm run lint`, `npm run check:downloads`, `npm run check:assets`, `npm run check:release-assets:selftest`, `npm run build`, and `npm audit --audit-level=moderate` pass in `Humungousaur-Website`, with `0` reported vulnerabilities. `npm run check:assets` validates that all `18` `/assets` references in `src/data/siteData.ts` point to existing optimized JPEGs, rejects stale PNG assets, rejects unreferenced leftovers in `public/assets`, and enforces the compact image-size limit; the previously unreferenced `humungousaur-hero-system-agent.jpg` was removed. Browser QA against `http://127.0.0.1:5173/` verified desktop `1280x720` and mobile `390x844` rendering, all `29` homepage images loading as optimized JPEGs, no relevant console warnings/errors, no horizontal homepage overflow, and a working mobile `Start building` route into `/docs`. The generated website image assets were converted from large PNGs to optimized JPEGs, reducing each publish-candidate image to less than `500` KiB while preserving the visual asset map. A mobile Docs overflow and drawer issue found during rendered QA was fixed in `src/docs2.css`; mobile Docs now reports no horizontal overflow, and the drawer opens onscreen from a hidden closed state. The download source checker validates the concrete Windows/macOS entries, shared `releaseBase`, zip hrefs, checksum hrefs, and `DownloadSection` render wiring instead of only checking loose snippets. The live release asset checker self-test covers success, bad-hash failure, missing-checksum-row failure, missing-required-asset failure, and empty-required-asset failure. `npm run check:publication` is wired as the website final publication gate, is required by the release runbook/checklist and website CI, and now passes after the website release/download files, optimized image replacement, Docs mobile CSS fix, and image asset checker were committed in `Humungousaur-Website`.
- Latest website open-source contributor guidance: `Humungousaur-Website/AGENTS.md` now documents setup, tests, source layout, design direction, content boundaries, security, and release gates; both the website publication gate and the runtime release preflight require it.
- Latest generated local release report: `python3 script/generate_release_report.py --skip-website --release-tag v0.1.0 --output artifacts/release/release-readiness.md` completed, and `python3 script/verify_release_report.py --report artifacts/release/release-readiness.md --skip-website --require-pass-status` verified it. The report now includes a first-class `Desktop Runtime Smoke` section with `31` shared desktop API checks passed.
- Latest combined publication-state gate: `python3 script/verify_publication_state.py --require-website` passes after the runtime release files and sibling website release files were committed; it now verifies that required runtime and website publication files are tracked and both working trees are clean.
- Latest desktop parity check: `64` checks passed, including shared API routes, runtime secrets, model-provider controls, and user-facing UI surfaces across Windows and macOS.
- Latest shared desktop runtime API smoke: `31` checks passed across health, system status, tools, channels, channel setup/status/doctor/smoke/listeners/outbox/send approval, voice provider status, chat stimulus, runs, timelines, approvals, and autonomy endpoints used by both desktop apps.
- Latest macOS local app-bundle smoke: `./script/build_and_run.sh --verify` builds the SwiftPM target, stages `dist/HumungousaurMac.app`, launches the app bundle, and confirms the `HumungousaurMac` process starts.
- Latest local Windows packaging probe: current host is macOS/Darwin ARM64 and has no `dotnet` or `pwsh` in PATH, so `Humungousaur-Windows.zip` must be produced on Windows or the GitHub Actions `windows-latest` release job; Windows package/verify scripts now fail fast with clear platform and .NET SDK guidance.
- Latest local GitHub artifact probe: `gh` is authenticated, but the remote does not yet expose the unpushed `Release Desktop Apps` workflow and there is still no `v0.1.0` release. `script/collect_release_artifacts.py` is ready to download `Humungousaur-Windows` and `Humungousaur-macOS` artifacts from a successful Actions run, copy both desktop zips into `artifacts/release`, regenerate `checksums.txt`, and run strict release verification.
- Latest release and website asset checkers validate exact tags, download both desktop zips, compare their SHA-256 hashes against `checksums.txt`, verify the exact staged upload directory with `--release-dir artifacts/release/final`, reject unsafe or platform metadata zip entries, require clean desktop package staging before creating public zips, require explicit macOS code-signature, Gatekeeper, and stapled-notarization verification for public tag releases, require timestamped Authenticode verification for every packaged Windows executable and Humungousaur-owned DLL, require least-privilege GitHub workflow permissions with read-only CI/default release jobs and write access only in the release publish job, require the tag-release workflow to install test extras, compile release scripts, run shared desktop runtime smoke, and run full backend regression before packaging, require `publish` to explicitly depend on `preflight`, `macos`, and `windows`, require the publish job to install test extras before generating final release evidence, support manual `workflow_dispatch` release repair with `publish_release=true` and a validated existing `release_tag`, require all manual release jobs to check out that exact tag before packaging, provide a local Actions artifact collector for both desktop zips, require the final upload directory to contain only the intended four public release files, verify the generated `release-readiness.md` with `script/verify_release_report.py --require-pass-status` before upload, re-check the exact staged upload directory together with the published GitHub assets after upload, require `release-readiness.md` to include backend regression, a first-class desktop runtime smoke section, website lint/download/build/audit evidence, and a live website release-asset check when release verification is requested, and include local mock-release tests for success, bad-hash failure, missing-checksum-row failure, missing-required-asset failure, and empty-required-asset failure; exact-tag live check currently fails only because the `v0.1.0` GitHub release is not published yet.
- Latest per-skill audit matrix: `132` skills audited, `132` native-capable or script-backed, `0` thin-tool-map skills needing deeper detail, `0` prompt-only, `0` unresolved Tool Map entries, `0` attention items.
- Latest workspace skill-format check: `3` tests passed with `264` subtests for `python3 -m pytest tests/test_workspace_skill_format.py -q`, validating frontmatter, skill names, descriptions, catalog capacity, and Tool Map resolution to native tools or workspace skills.
- Latest per-skill task-smoke coverage: `132` skills covered, `132` direct task-smoked, `0` composition-smoked, `0` pending task-smoke skills, `221` native tools seen in smoke evidence, `0` skills with mapped native tools still pending narrower smoke.
- Latest live-boundary coverage: `132` skills covered, `136` approval/medium/high-risk boundary tools tracked, `0` skills with missing boundary evidence, `28` skills with dry-run-only boundaries, and `128` skills needing live or credentialed validation.
- Latest live-smoke plan: `10` domains planned, `128` skills and `111` boundary tools included, `0` domains with missing tools, and highest-priority domains are channels, voice, browser, desktop OS, and workspace productivity.
- Current tool-domain folders observed: `33`.
- Current skills observed: more than `130`.
- Current working tree note: per-skill task-smoke coverage and direct task scenarios have been added in this slice; final commit/push status should be checked with `git status` and `git log`.

## Done And Pushed

These areas have native implementation, skill wiring, smoke/regression coverage, and pushed commits.

| Area | Status | Evidence |
| --- | --- | --- |
| Productivity skill wiring | Done | Initial productivity routing and skill smoke were added. |
| Skill maps and smoke expansion | Done | Broader skill map validation and smoke coverage were added. |
| Office artifacts | Done | Native DOCX and PPTX create/inspect tools. |
| Analysis and reporting | Done | Native CSV profiling, chart artifact, and business report tools. |
| Writing skills | Done | Native writing artifacts and follow-up packets. |
| Async execution hardening | Done | Agent async execution path was hardened while adding writing skills. |
| Channel action preparation | Done | Native channel manifests, setup/status, message preparation, send gating, listener/webhook paths, ambient and bot-loop concepts. |
| Channel skill hardening | Done in current slice | Shared channel operations plus Slack, Telegram, Discord, and WhatsApp skills now document native workflows, safety/approval rules, implementation boundaries, and verification against the existing channel smoke path. |
| Browser/computer-use skill hardening | Done in current slice | Browser, OpenAI-style computer-use, and Claude-style computer-use skills now document native observe-act-verify workflows, approval boundaries, native implementation limits, and verification against browser/OS smoke and tests. |
| Cognition/orchestration skill hardening | Done in current slice | Self-assessment, self-reflection, team orchestration, worker handoff, autonomy, memory metabolism, persona evolution, taskflow, task tracking, priority review, and wakeup scheduling now have explicit safety/approval and native-boundary contracts. |
| Voice/audio/meeting skill hardening | Done in current slice | Speech operations, local speech, spoken response style, voice loop, voice wakeup, voice call gateway, audio summaries, meeting transcription, meeting follow-up, and music/sound generation now have explicit safety, native-boundary, workflow, and verification contracts. |
| Final thin-skill hardening | Done in current slice | Ambient room context, bot-loop protection, capability audit/surfaces, channel gateway, Codex/coding delegation, daily planning, gog, session wrap-up, skill authoring/security review, and wacli now have explicit workflow, safety, native-boundary, and verification contracts. |
| PDF and OCR surfaces | Done | PDF merge/extract/read support and OCR provider status surface. |
| RSS/feed monitoring | Done | Native RSS/feed monitoring tools and smoke coverage. |
| Transcript and spoken-content summaries | Done | Native transcript/audio/video summary artifacts. |
| Notion and Airtable packets | Done | Native local operation packets and inspection, without importing upstream packages. |
| Research citations | Done | Literature set, bibliography, and citation artifact support. |
| Media planning | Done | Storyboard/music/video-style planning artifacts. |
| Travel planning | Done | Travel itinerary and planning artifacts. |
| Commerce safety | Done | Shopping comparison and purchase safety artifacts. |
| Personal planning | Done | Contact notes, daily planning, priority and focus artifacts. |
| Design system artifacts | Done | Brand-guideline and theme-pack tools with Markdown/JSON/CSS sidecars. |
| Visual artifacts | Done | Diagram, Mermaid, Excalidraw-compatible JSON, and infographic plan tools. |
| Presentation planning | Done | Presentation plan create/inspect tools with narrative, slide plan, speaker notes, evidence, risks, and status. |
| Google Workspace packets | Done locally as safe packets | Calendar, Drive, Docs, Sheets, and Gmail-style operation packets with scopes, approval requirements, payload previews, and `not_executed` status. |
| Network diagnostics | Done | DNS lookup, HTTP endpoint check, and single-port TCP probe tools. |
| Creative writing and songwriting | Done | Creative brief, song structure, and revision packet artifacts with originality guardrails. |
| Security review artifacts | Done | Dependency inventory, secret-scan report, prompt-injection review, and approval-policy review artifacts. |
| GitHub and CI workflow artifacts | Done | Native GitHub issue packets, PR packets, CI failure reports, repo-state reports, artifact inspection, skill docs, and smoke coverage without requiring live GitHub credentials. |
| Desktop channel operations | Done locally in this slice | Windows app allowlist/group allowlist onboarding, outbound channel message preparation, approval-gated send flow, API channel-message routes, and API regression coverage. |
| Per-skill capability audit matrix | Done | Native `agent_skill_capability_audit` tool writes Markdown/JSON audit artifacts, classifies every workspace skill, resolves Tool Maps against native tools/skills, and runs in full skill smoke. |
| Workflow support tools | Done | Diff, JSON-only task, typed approval workflow, output compaction, tool search/catalog, and canvas/A2UI style surfaces are represented as native capability areas. |
| Voice provider surfaces | Done as tool surfaces | Voice provider status, transcription, response preparation, speech, response listing, Deepgram, ElevenLabs, Windows SAPI, and local Whisper provider paths are represented. |
| OS and browser control surfaces | Done as native surfaces | Browser, screen, keyboard, mouse, window, app, clipboard, and virtual desktop tool surfaces exist. |
| Cognition and memory | Done as native surfaces | Memory, persona, reflection, self-assessment, automations, autonomous loop, and multi-agent coordination surfaces exist. |
| Per-skill task-smoke coverage | Done in current slice | Full skill smoke now emits Markdown/JSON coverage artifacts, records exact native tool evidence, directly task-smokes all 132 skills, and reports 0 skills without task-smoke evidence. |
| Foundational native-tool smoke | Done in current slice | Safe/dry-run smokes now cover file/search/shell/code catalogs, memory, activity, conversation, email, cognition review, skill forge, and canvas tools, raising native tools seen in evidence from 148 to 177 and reducing skills with pending mapped tools from 116 to 72. |
| Complete mapped-tool smoke closure | Done in current slice | Direct safe/dry-run evidence now covers the remaining mapped live-browser, channel, voice, Codex CLI, Lobster, OS element/clipboard, plugin, browser extraction, Python artifact, taskflow cognition, persona/briefing/curation, and PDF optional-dependency boundaries, raising native tools seen in evidence to 221 and reducing mapped pending native tools to 0. |
| Live-boundary coverage artifact | Done in current slice | Full skill smoke now emits Markdown/JSON live-boundary coverage artifacts that separately track approval-gated, medium-risk, and high-risk mapped tools, with 0 skills missing local boundary evidence and 128 skills explicitly flagged for credentialed/live validation. |
| Live-smoke plan artifact | Done in current slice | Full skill smoke now emits Markdown/JSON live-smoke plan artifacts that group remaining live/credentialed validation into 10 prioritized domains: channels, voice, browser, desktop OS, workspace productivity, developer workflows, security/network, workflow approvals, cognition/autonomy, and other boundaries. |
| Open-source and release readiness gates | Done locally in current slice | Source hygiene, desktop parity, tag-release backend regression, generated report verification, backend-test and website-check evidence, signed package scripts, version-aligned desktop metadata, release workflow checks, exact staged upload-directory verification, zip metadata/path hygiene, website download checks, ordered release runbook, and published-release checksum/hash verification are represented in CI/preflight. |

## Implemented But Still Needs Deeper Live Validation

These areas have code and skills, but they are not yet finished as daily-use, live, end-to-end experiences.

| Area | Current State | Still Needed |
| --- | --- | --- |
| Desktop Windows and macOS apps | Native app structures exist under `apps/`; runtime settings, provider/model settings including OpenAI, Groq, Grok, Ollama, and Local OpenAI, voice settings, provider-aware channel setup requirements, channel allowlists, setup doctor, listener status, inbound preview, prepared outbound messages, approval-gated sends, recent runs, timelines, approval decisions, run cancellation, app-owned process secret hydration, and channel listener polling are represented across the Windows and macOS clients through the shared API and source-level UI parity checks. | Run both desktop apps end to end, validate live chat, provider selection, channel onboarding, approvals, voice, runtime start/stop, and credentialed always-on channel listening from each app. |
| Voice wakeup to spoken response | Native voice tools exist, and local/provider STT/TTS surfaces are wired. | Run continuous wake word, STT, agent turn, tool execution, TTS, and playback in one live Windows flow. |
| OpenAI/Groq/Ollama provider path | Provider clients and smoke flows exist; OpenAI is currently the practical default for live smoke. | Reconfirm configured desktop settings, local Ollama model health, context-window fit, fallback policy, and live model-specific failures. |
| Local speech models | Local Whisper/faster-whisper paths reference the separate `voice-wakeup` assets. | Confirm installed local model paths, test actual transcription on current machine, add local TTS if the installed assets include it. |
| Channels | Native channel catalog, setup requirements, setup/status, doctor, non-sending integration smoke, webhook ingest, listener tick, outbox, message preparation, allowlists, approval-gated send routes, desktop listener polling, and desktop-started process secrets exist, and both Windows and macOS apps can operate them with provider-specific onboarding details. | Complete credentialed live receive/send smoke for Telegram, Slack, Discord, WhatsApp, SMS, WebChat, and other important channels. |
| Google Workspace | Safe operation packets exist. | Add OAuth onboarding, token storage/refresh, approval-gated execution, and live Gmail/Calendar/Drive/Docs/Sheets smoke. |
| Browser/computer use | Native browser and OS/computer tools exist. | Run complex browser and Windows UI tasks end to end from natural user requests, with visual verification and recovery behavior. |
| Open Interpreter-style capability | Code execution and interpreter-style artifacts exist. | Expand sandbox policy, richer long-running process control, artifact capture, and user approval for risky execution. |
| Delegation | Codex delegation is stronger than other delegation paths. | Add shared delegation packets and status detection for Codex CLI, Claude Code, opencode, worker handoff, and unavailable CLIs. |
| Public desktop release assets | macOS zip exists locally and verifies. Website download sources exist, and the live asset checker now validates exact tags, required assets, non-empty asset metadata, downloaded zip hashes, checksum rows, and local mock-release self-test coverage. Windows package/verify scripts explicitly require Windows because the app targets `net8.0-windows` and WinUI. `script/collect_release_artifacts.py` can pull both desktop zips from a successful Actions run and regenerate local checksums. | Run the Windows packaging job on Windows or GitHub Actions, collect/publish `Humungousaur-Windows.zip`, `Humungousaur-macOS.zip`, and `checksums.txt` on the tagged GitHub release, then rerun strict local and website live-release checks. |

## Still To Do

### 1. Keep Mapped-Tool Smoke Green And Add Live Skill Smoke

- The generated per-skill audit matrix now reports `0` thin-tool-map skills and `0` attention items.
- The generated per-skill task-smoke coverage now reports `0` pending task-smoke skills.
- The generated per-skill task-smoke coverage now reports `0` skills with mapped native tools still pending narrower smoke.
- The generated live-boundary coverage now reports `0` skills with missing local boundary evidence and `128` skills that still need credentialed/live validation.
- The generated live-smoke plan now prioritizes channels, voice, browser, desktop OS, and workspace productivity as the first live validation domains.
- Keep this evidence green as skills evolve.
- Flag and live-test credentialed/provider-backed skills that still only have local, dry-run, or prepare/approve evidence.

### 2. Complete Desktop App End-To-End Validation

- Provider, model, API key, channel, voice, runtime, and approval settings should remain configurable from the Windows app.
- `.env` should remain internal or fallback configuration, not the normal user-facing setup surface.
- Channel onboarding should continue using backend channel manifests as the source of truth for required fields, required secrets, delivery mode, policy, listener mode, and doctor findings.
- Desktop channel checks should use `channel_integration_smoke` for non-sending readiness evidence before any live provider-specific smoke.
- Add richer tool execution visibility.
- Keep approvals, run status, timelines, approve/reject decisions, and cancellation visible from the Windows app.
- Run live app smoke against the local API.

### 3. Run Full Daily Assistant End-To-End Smoke

Minimum daily loop to validate:

1. Wake word activates the assistant.
2. Audio is transcribed.
3. The agent reasons over the user stimulus.
4. The agent selects tools through schema-based orchestration.
5. The agent runs at least one browser, OS, file, and productivity task.
6. The agent writes/updates memory when appropriate.
7. The agent responds through voice and app chat.
8. The interaction is visible in logs, traces, artifacts, and the desktop UI.

### 4. Complete Live Channel Integrations

Priority channels:

- Telegram
- Slack
- Discord
- WhatsApp
- WebChat
- SMS
- Microsoft Teams or Google Chat, depending on daily use

For each channel:

- In-app onboarding.
- Setup doctor.
- Non-sending integration smoke.
- Listener status.
- Inbound event normalization.
- Bot-loop protection.
- Ambient room behavior where relevant.
- Approval-gated outbound send.
- Live smoke evidence.

### 5. Complete Live Google Workspace Execution

- Gmail compose/send drafts.
- Calendar event create/update.
- Drive file search/upload/download.
- Docs create/update/export.
- Sheets read/write/update.
- OAuth and revocation UX.
- Approval before external-visible changes.

### 6. Harden Voice And Local Models

- Re-check Ollama installed models and choose local default by available RAM/VRAM.
- Add model health checks and fallback explanation.
- Validate local Whisper/faster-whisper STT with real audio.
- Add or integrate local TTS if available.
- Keep OpenAI as reliable default until local path is proven.

### 7. Expand Browser And Windows Computer-Use Validation

- Test app launching, window switching, screen reading, mouse/keyboard, clipboard, browser navigation, downloads, forms, and screenshots.
- Add recovery behavior for missing windows, stale handles, permission failures, and timeout.
- Add visual or state assertions where possible.

### 8. Harden Open Interpreter And Code Execution Capabilities

- Add richer code execution packets.
- Capture stdout/stderr/artifacts cleanly.
- Support long-running task supervision.
- Add approval gates for network, install, filesystem mutation, and process control.

### 9. Harden GitHub Live Execution And CI Polling

- Add optional live GitHub connector/`gh` tests when credentials are configured.
- Add current PR/CI polling and check-summary refresh.
- Approval-gate issue posting, PR opening, PR comments, labels, and merges.
- Expose GitHub account/setup state in the desktop app.

### 10. Add Durable Autonomous Behaviors

- Background monitors.
- Reminders and follow-ups.
- Long-running task memory.
- Skill learning from repeated tasks.
- Skill proposal, creation, testing, and approval workflow.
- Delegated multi-agent task coordination.

## Areas To Explore

- Which skills should support live execution, and which should stay as safe prepare/approve packets?
- Which skills need background daemons instead of one-shot tools?
- Which capabilities deserve first-class Windows app panels?
- Which chat channels are most valuable for daily use first?
- How much local model quality is acceptable before falling back to OpenAI?
- How should the assistant learn new skills from repeated tasks without polluting the skill catalog?
- What should be forgotten, summarized, or promoted into long-term memory?
- How should multiple agents share task state, approvals, and final accountability?

## Suggested Next Order

1. Expand live/credentialed smoke for the highest-value skills now that representative per-skill and mapped-tool smoke is complete.
2. Complete the desktop app settings/runtime surface.
3. Run the full voice-to-agent-to-voice Windows smoke.
4. Live-test the top channels.
5. Live-test Google Workspace.
6. Harden local model and local voice paths.
7. Add GitHub live connector and CI polling.
8. Add autonomous learning and skill-creation workflows.

## Completion Criteria

This goal should be considered complete only when:

- Every skill has a detailed tool map and concrete execution path.
- Every high-value skill has native tools, scripts, artifacts, packets, or explicit live boundaries.
- Every important skill task has smoke coverage.
- Live integrations are either tested end to end or clearly marked unavailable with exact setup reason.
- The Windows app can configure and run the assistant loop without relying on manual `.env` setup for normal user choices.
- Voice wakeup, STT, reasoning, tool execution, memory, response preparation, TTS, and UI feedback are validated as one loop.
- Full skill smoke and full regression are green after the final slice.
