# Codex Skill Integration

Date: 2026-06-03

Humungousaur integrates local Codex skills in two separate layers:

1. Codex evidence layer: discover local Codex plugins, discover `SKILL.md` files, read selected skill docs safely, and inspect backend readiness.
2. Agent skill layer: sync relevant Codex skills into Humungousaur's reusable cognitive skill store so model-led planning can recall them during future work.

This is not an intent router. The synced skills are reusable guidance records. The planner still chooses tools from schemas, risk levels, current context, and model reasoning. Deterministic code only catalogs files, validates paths, bounds reads, writes skill records, and enforces approval policy.

## Local Codex Sources Checked

The current machine has user/session Codex skills and plugins under `C:\Users\bhave\.codex`, plus bundled Codex app resources under the installed Codex Desktop app `app\resources` tree.

Relevant sources inspected:

- Browser plugin: `plugins/cache/openai-bundled/browser/26.601.21317`
- Browser skill: `skills/control-in-app-browser/SKILL.md`
- Browser runtime script: `scripts/browser-client.mjs`
- Bundled Chrome skill: `plugins/openai-bundled/plugins/chrome/skills/control-chrome/SKILL.md`
- Bundled Computer Use skill: `plugins/openai-bundled/plugins/computer-use/skills/computer-use/SKILL.md`
- User Playwright skill: `skills/playwright/SKILL.md`
- System skills: `openai-docs`, `skill-creator`, `skill-installer`, `plugin-creator`
- GitHub plugin skills: `github`, `yeet`, review/CI skills
- Office artifact skills: Documents, Spreadsheets, Presentations
- Product Design plugin skills
- Cloudflare skills: Agents SDK, MCP server, Workers, Durable Objects, Sandbox, web performance
- Hugging Face skills: CLI, datasets, jobs, trainers, Transformers.js, Spaces-oriented workflows

A dedicated `codex-cli` `SKILL.md` was not found in the checked Codex skill tree. Humungousaur covers Codex CLI as a capability surface backed by the current Codex manual's documented `codex exec` non-interactive mode:

- `codex_capability_status` checks Codex CLI command availability.
- `codex_cli_status` reports discovered CLI candidates and the documented delegation pattern.
- `codex_cli_run` delegates an approved task to `codex exec` with structured argv, cwd validation, sandbox/approval inputs, optional JSONL output, resume, output-file/schema flags, timeout handling, and dry-run support.
- Native computer-use behavior is exposed through the existing OS/UI tools such as `os_windows`, `os_observe_ui`, `os_click_element`, `os_type_text`, `os_send_keys`, window tools, virtual-desktop tools, clipboard tools, and screenshots.

## Tools

- `codex_capability_status`: inspect Codex home roots, plugin/skill counts, Codex CLI, Playwright, Browser Use, Chrome/Edge, computer-use Python packages, and native tool coverage.
- `codex_cli_status`: inspect Codex CLI readiness and the documented `codex exec` delegation contract.
- `codex_cli_run`: approval-gated task delegation through Codex CLI non-interactive mode.
- `codex_plugin_catalog`: list `.codex-plugin/plugin.json` manifests with skill counts, app manifests, keywords, licenses, and notable scripts such as `browser-client.mjs`.
- `codex_skill_catalog`: list local `SKILL.md` references from workspace/user/env Codex homes and bundled app resources.
- `codex_skill_read`: read a bounded local `SKILL.md` by exact `skill_id`.
- `codex_skill_import`: import selected exact Codex skill refs into the cognitive skill store.
- `codex_skill_sync`: read relevant Codex skill refs and write curated agent skill records for Browser, Chrome, Computer Use, Playwright, OpenAI docs, skill/plugin creation, GitHub, office artifacts, product design, Cloudflare agents, Chrome performance, and Hugging Face workflows.

## Sync Profiles

- `core_assistant`: Browser, Chrome, Computer Use, Playwright, OpenAI docs, skill creation/installing, plugin authoring, GitHub, Documents, Spreadsheets, Presentations, and Product Design.
- `browser_computer`: Browser, Chrome, Computer Use, Playwright, and Chrome/Web Performance guidance.
- `knowledge_work`: OpenAI docs, GitHub, Documents, Spreadsheets, Presentations, and Product Design.
- `all_relevant`: all currently encoded Codex-derived agent skill templates.

## Example Commands

```powershell
python -m humungousaur run "codex_capability_status {\"codex_home\":\"C:\\Users\\bhave\\.codex\"}" --workspace . --planner explicit
python -m humungousaur run "codex_cli_status {\"probe_help\":false}" --workspace . --planner explicit
python -m humungousaur run "codex_cli_run {\"task\":\"summarize this repository structure\",\"sandbox\":\"read-only\",\"dry_run\":true}" --workspace . --planner explicit
python -m humungousaur run "codex_plugin_catalog {\"query\":\"browser\",\"codex_home\":\"C:\\Users\\bhave\\.codex\"}" --workspace . --planner explicit
python -m humungousaur run "codex_skill_catalog {\"query\":\"computer-use\",\"source\":\"app\"}" --workspace . --planner explicit
python -m humungousaur run "codex_skill_catalog {\"query\":\"playwright\",\"codex_home\":\"C:\\Users\\bhave\\.codex\"}" --workspace . --planner explicit
python -m humungousaur run "codex_skill_sync {\"profile\":\"core_assistant\",\"codex_home\":\"C:\\Users\\bhave\\.codex\",\"reason\":\"sync useful local Codex skills into the agent\"}" --workspace . --planner explicit
```

After sync, `cognitive_state {}` exposes the created reusable skills to planner context.
