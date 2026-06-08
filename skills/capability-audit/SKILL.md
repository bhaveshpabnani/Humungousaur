---
name: capability-audit
description: Audit Humungousaur's effective tools, skills, plugins, channels, providers, local services, and missing capability gaps. Use before large integrations, after adding tools, or when the user asks what the agent can currently do.
---

# Capability Audit

## Purpose

Give the user and model an evidence-backed map of what the assistant can actually do now. This skill adapts OpenClaw agent audit patterns to Humungousaur's capability surface and plugin catalogs.

## When To Use

Use before large architecture changes, after adding tools/skills/plugins, when debugging "is this wired?", or when choosing the next integration batch.

## Inputs And Evidence

- `capability_surface` records.
- Tool catalog and descriptions.
- Workspace skill catalog and memory skills.
- Per-skill capability audit matrix.
- Plugin and channel catalogs.
- Provider readiness for OpenAI, Groq, Ollama, voice, browser, and OS tools.
- Recent smoke test artifacts.

## Tool Map

- `capability_surface`
- `tool_search`
- `tool_describe`
- `agent_skill_catalog`
- `agent_skill_capability_audit`
- `plugin_catalog`
- `channel_catalog`
- `voice_provider_status`
- `external_integrations_status`
- `system_status`

## Workflow

1. Gather the current capability surface with records included when useful.
2. Run `agent_skill_capability_audit` when the question includes skill completeness, prompt-only skills, live readiness, or smoke coverage.
3. Count tools, skills, channels, providers, plugins, and notable missing surfaces.
4. Verify readiness for local services and cloud providers before claiming availability.
5. Compare current capabilities to the user's requested architecture or shortlist.
6. Identify gaps as missing, partially wired, untested, blocked by credentials, or blocked by policy.
7. Recommend the next implementation batch with verification steps.

## Safety

- Do not claim a provider is usable because config exists; use status or smoke evidence.
- Do not treat catalog declarations as direct execution support.
- Keep external secrets redacted.

## Native Implementation Boundaries

- Use `capability_surface`, `tool_search`, `tool_describe`, catalogs, and status tools as authoritative current-state inputs.
- Use `agent_skill_capability_audit` for skill implementation status; do not classify skills from informal names or reference repos.
- Report live readiness separately from native local support when credentials, CLIs, local models, or network access are unavailable.

## Verification

- Capability counts should come from current tool output.
- Skill completeness should cite the per-skill audit artifact.
- Readiness claims should cite status tool or smoke artifact evidence.
- Missing skills should be listed by exact target name where possible.

## Failure Modes

- Confusing planned capabilities with implemented tools.
- Counting ignored `external_repos` files as active skills.
- Reporting broad readiness without live or focused verification.

## References

- Shortlist item: `capability-audit`.
- Upstream inspiration: OpenClaw agent audit entries.
- Humungousaur tools: capability surface, plugin catalog, channel catalog.
