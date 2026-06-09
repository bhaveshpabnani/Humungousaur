# Open-Source Release Goal

Target publication date: June 10, 2026.

This document turns the release-prep brief into an executable checklist for making Humungousaur public on GitHub. It is intentionally stricter than a marketing checklist: every claim should have code, docs, tests, release evidence, or an explicit remaining blocker.

## Goal

Prepare Humungousaur for public open-source release as a production-standard local-first agent runtime with clear code organization, trustworthy agent architecture, detailed documentation, explicit safety boundaries, and verified real-world task readiness.

## External Reference Guardrails

- OpenHands uses repository-level always-on guidance plus on-demand `SKILL.md` files; Humungousaur should preserve that same separation through `AGENTS.md`, `docs/GLOBAL_AGENT_INSTRUCTIONS.md`, and workspace skills.
- The AGENTS.md convention keeps contributor guidance out of the human README while giving coding agents predictable setup, testing, architecture, and security instructions.
- OWASP GenAI guidance treats prompt injection, excessive agency, insecure output handling, sensitive information disclosure, and supply-chain risks as first-class agent release concerns.
- Upstream skill ecosystems such as OpenHands, OpenClaw, Hermes, Anthropic Skills, and Codex skills are reference evidence only. Humungousaur-owned tools, schemas, approvals, tests, and verification remain the implementation boundary.

## Code Organization

Status: mostly implemented; final gate required.

- Backend package code is grouped by runtime area: `cognition`, `planning`, `tools`, `safety`, `memory`, `integrations`, `indexing`, `dashboard`, and API/CLI entrypoints.
- Desktop app shells are isolated under `apps/macos` and `apps/windows`.
- Release automation is isolated under `script/`; smoke examples live under `scripts/`.
- Public architecture and release docs live under `docs/`.
- Workspace skills live under `skills/<skill-name>/SKILL.md` with frontmatter, workflow, safety, verification, and native boundaries.
- Irrelevant local files must be excluded or removed before publishing: `.DS_Store`, `__pycache__`, `.pyc`, `.env`, generated artifacts, local databases, signing keys, and package outputs.

Required evidence:

```bash
python3 script/verify_open_source_hygiene.py
python3 script/verify_publication_state.py --require-website
```

## Documentation

Status: implemented with final verification required.

- `README.md` is the human entrypoint.
- `AGENTS.md` is the repository-level agent/contributor instruction file.
- `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `.env.example`, and GitHub workflows are release-required files.
- `docs/RELEASE_CHECKLIST.md` and `docs/RELEASE_RUNBOOK.md` define the public release process.
- `docs/COGNITIVE_AGENT_ARCHITECTURE.md` explains the human-like runtime loop.
- `docs/GLOBAL_AGENT_INSTRUCTIONS.md` defines the non-keyword, model-led intelligence rule.
- `docs/AGENT_SKILL_AUTHORING_STANDARD.md` defines the skill-file contract.
- The sibling `Humungousaur-Website/AGENTS.md` defines website code, content, design, and publication boundaries.

Required evidence:

```bash
python3 script/verify_release_readiness.py --require-website
```

## Agent Architecture

Status: implemented in layers; central prompt migration covers model-client JSON instructions, planner/ReAct/selector/repair/review prompts, Codex delegation/skill-sync prompts, generic workflow model-task/output-compaction prompts, final response synthesis, plus the core cognition attention, specialist-delegation, reflection, consolidation, self-review, interaction-review, priority-review, memory-curation, skill-evolution, skill-forge, persona-evolution, briefing, recovery, environment-review, and commitment-review prompts.

The agent should behave as a bounded cognitive runtime, not a chatbot with arbitrary tool access. The release architecture includes:

- perception and compact planning context
- model-led attention and planning
- explicit fallback commands only
- goals, tasks, focus, commitments, environment, priorities, wakeups, triggers, and autonomous queue state
- durable memory, learning, reflection, recovery, consolidation, curation, skill evolution, persona evolution, self-review, and interaction review
- specialist contracts and capability groups
- tool schemas, approval policy, audit logs, cancellation checkpoints, and evidence-boundary checks
- final response preparation only after sufficient observation or explicit uncertainty

The core model-client JSON instructions, planning, ReAct, selector, repair, and planner-review prompts now live in `humungousaur/resources/prompts/planning.yaml`. The core attention, specialist-delegation, task-reflection, memory-consolidation, self-review, interaction-review, priority-review, memory-curation, skill-evolution, skill-forge, persona-evolution, briefing, recovery, environment-review, and commitment-review prompts live in `humungousaur/resources/prompts/cognition.yaml`. Codex CLI delegation and Codex skill-sync prompts live in `humungousaur/resources/prompts/codex.yaml`. Generic workflow model-task and output-compaction prompts live in `humungousaur/resources/prompts/workflow.yaml`. Final user-facing response synthesis lives in `humungousaur/resources/prompts/response.yaml`. Python code remains responsible for schemas, validation, parsing, model-client calls, and deterministic safety gates; durable natural-language agent policy lives in bundled prompt resources.

Required evidence:

```bash
python -m pytest tests/test_planning.py -q
python -m pytest tests/test_cognition.py -q
python -m pytest tests/test_tools.py -q
```

## Skill Files

Status: implemented with validation required.

Every production skill must include:

- YAML frontmatter with matching `name` and a concrete `description`
- purpose and when-to-use guidance
- inputs and evidence
- Humungousaur tool map
- workflow steps
- native implementation boundaries
- safety and approval rules
- verification
- failure modes
- references

Required evidence:

```bash
python -m pytest tests/test_workspace_skill_format.py -q
python scripts/smoke_skills.py --workspace .
```

## Real-World Task Smoke Tests

Status: ready as release gate; live external tasks should use test accounts and non-sensitive data.

Run representative smoke tasks before publishing:

```bash
python -m humungousaur run "system_status {}" --workspace . --planner explicit
python -m humungousaur run "cognitive_state {}" --workspace . --planner explicit
python -m humungousaur run "agent_skill_catalog {\"source\":\"workspace\"}" --workspace . --planner explicit
python -m humungousaur run "browser_live_status {}" --workspace . --planner explicit
python -m humungousaur run "channel_catalog {}" --workspace . --planner explicit
python -m humungousaur run "voice_provider_status {}" --workspace . --planner explicit
python scripts/smoke_agent.py --workspace .
python scripts/smoke_complete_agent.py --workspace .
python scripts/smoke_real_world_tasks.py --workspace .
```

Live app/browser/channel tests must observe before acting, use test targets, avoid private accounts unless intentionally approved, and stop at approval gates for state-changing or external-visible actions.

For a stronger local browser proof, run:

```bash
python scripts/smoke_real_world_tasks.py --workspace . --live-browser
```

Current native app-launch smoke coverage uses allowlisted apps such as Calculator/TextEdit/Finder in dry-run mode. Calendar-style work is verified through `google_workspace_operation_prepare`, which creates an approval-required operation artifact and does not call Google APIs. Direct local Calendar app launch should remain a documented gap until the app allowlist and approval UX intentionally support it.

## Release Gate

Do not publish until all applicable checks pass:

```bash
python -m pip install -e ".[browser,pdf,ocr,office,test]"
python -m unittest discover -v
python3 script/verify_desktop_parity.py
python3 script/verify_desktop_runtime_smoke.py
python3 script/verify_open_source_hygiene.py
python3 scripts/smoke_real_world_tasks.py --workspace .
python3 script/verify_release_readiness.py --require-website --release-tag v0.1.0
python3 script/generate_release_report.py --require-website --check-github-release
python3 script/verify_publication_state.py --require-website
```

Website release checks from the sibling repository:

```bash
npm ci
npm run lint
npm run check:downloads
npm run check:publication
npm run build
npm audit --audit-level=moderate
```

## Remaining Blocker Policy

If any live smoke task cannot run because credentials, OS platform, browser runtime, signing certificates, or GitHub release assets are unavailable, record it as a release blocker or documented limitation. Do not convert an untested integration into a public claim.
