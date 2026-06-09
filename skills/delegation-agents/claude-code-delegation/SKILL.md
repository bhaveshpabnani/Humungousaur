---
name: claude-code-delegation
description: Plan Claude Code delegation only when a native, approved adapter exists; otherwise prepare a handoff brief and report the missing implementation gap.
---

# Claude Code Delegation

## Purpose

Represent Claude Code as a possible coding worker without pretending it is integrated. Humungousaur must use an owned adapter before executing Claude Code tasks.

## When To Use

Use when the user asks to use Claude Code, compare coding workers, or prepare a Claude-oriented handoff.

## Inputs And Evidence

- Task objective, repo path, constraints, tests, and desired sandbox.
- Capability search showing whether a native Claude Code adapter exists.
- Handoff prompt or missing-adapter report.

## Tool Map

- `tool_search`
- `capability_surface`
- `write_note`
- `codex_cli_plan`
- `coding-agent`

## Workflow

1. Check whether Humungousaur exposes a native Claude Code tool or configured adapter.
2. If missing, say the adapter is not implemented and prepare a reusable handoff brief.
3. If implemented later, require approval and bounded sandbox execution.
4. Verify any delegated output locally.
5. Prefer existing `codex_cli_*` delegation when the user accepts Codex as the worker.

## Native Implementation Boundaries

- Do not call Claude Code CLI directly unless a Humungousaur-owned adapter/tool exists or the user explicitly requests an approved shell action.
- Do not import Hermes Claude Code scripts.
- Do not treat external installation as native integration.

## Safety And Approval

- Delegated coding tools can modify files; require approval and scoped workdirs.
- Do not pass secrets.
- Preserve dirty worktrees.

## Verification

- Capability status must prove whether native support exists.
- Handoff briefs are drafts, not executed work.
- Any executed result needs local verification.

## Failure Modes

- Claiming Claude Code ran when only a prompt was drafted.
- Delegating too much context.
- Skipping local verification.

## References

- Shortlist item: `claude-code-delegation`.
- Upstream inspiration: Hermes Claude Code references only.
