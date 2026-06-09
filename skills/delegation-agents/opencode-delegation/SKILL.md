---
name: opencode-delegation
description: Prepare or run OpenCode delegation only through a native approved Humungousaur adapter; otherwise produce a scoped handoff and report the missing adapter.
---

# OpenCode Delegation

## Purpose

Support OpenCode as a potential coding worker while preserving native implementation boundaries. This skill distinguishes capability planning from actual runtime integration.

## When To Use

Use when the user asks to use OpenCode, compare worker agents, or route a coding task to an alternate CLI.

## Inputs And Evidence

- Objective, repo path, constraints, expected tests, and adapter availability.
- Capability search/status and handoff prompt.

## Tool Map

- `tool_search`
- `capability_surface`
- `write_note`
- `codex_cli_plan`
- `coding-agent`

## Workflow

1. Search for a native OpenCode adapter/tool.
2. If absent, report the gap and prepare a bounded handoff prompt.
3. If present, inspect its schema, sandbox, and approval requirements before running.
4. Verify any worker output with local tools and tests.
5. Record lessons only after evidence-backed completion.

## Native Implementation Boundaries

- Do not import Hermes OpenCode scripts.
- Do not call arbitrary OpenCode commands as the skill implementation without user-approved native/shell path.
- Missing adapter means no live delegation claim.

## Safety And Approval

- Worker execution requires approval, repo scope, and no secrets.
- Avoid overlapping edits with active user changes.

## Verification

- Adapter presence must be proven by tool catalog.
- Handoff-only output must be labeled as not executed.
- Executed work needs diff/test review.

## Failure Modes

- Treating OpenCode installation as integration.
- Letting alternate workers edit outside scope.
- Reporting unverified worker claims.

## References

- Shortlist item: `opencode-delegation`.
- Upstream inspiration: Hermes OpenCode references only.
