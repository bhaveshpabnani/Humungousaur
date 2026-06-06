---
name: claude-api-development
description: Build or debug Anthropic Claude API integrations from official docs and current project evidence, with adapter boundaries and no hardcoded provider assumptions.
---

# Claude API Development

## Purpose

Support Claude API app development when the user requests it, while keeping Humungousaur's own provider logic generalized and native.

## When To Use

Use for Anthropic SDK usage, Claude Messages API, tool use, model migration, provider debugging, or app integration reviews.

## Inputs And Evidence

- Current project code, provider config, error output, docs or user-provided API requirements.
- Desired model, tool schema, streaming behavior, and retry/error policy.

## Tool Map

- `read_file`
- `search_workspace`
- `run_shell_command`
- `write_note`
- `tool_search`
- `openai-api-development`

## Workflow

1. Inspect existing provider abstraction before adding code.
2. Use official/current docs when API details could have changed.
3. Keep provider-specific code behind an adapter.
4. Add schema validation, retries, redaction, and tests.
5. Avoid hardcoded model routing for intelligence decisions.
6. Verify with mocked tests or approved live smoke.

## Native Implementation Boundaries

- Implement adapters in the target project/Humungousaur codebase.
- Do not import Anthropic skill repository code as implementation.
- Do not make Claude the only intelligence path unless the user asks.

## Safety And Approval

- API keys stay in env/secret storage.
- Live calls can cost money and require user intent.
- Redact prompts/responses when they contain secrets.

## Verification

- Tests should cover request shape and error handling.
- Live smoke should report model/provider and exact result boundaries.
- If docs were not refreshed, say so for unstable API details.

## Failure Modes

- Hardcoding model IDs or provider-specific assumptions.
- Logging API keys.
- Treating mock success as live provider readiness.

## References

- Shortlist item: `claude-api-development`.
- Upstream inspiration: Anthropic Claude API skill reference only.
