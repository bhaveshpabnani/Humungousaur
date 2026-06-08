---
name: codex-delegation
description: Delegate bounded repository work to Codex CLI through model-planned, approval-gated handoffs.
---

# Codex Delegation

## Purpose

Delegate bounded repository work to Codex CLI through native Humungousaur delegation tools while keeping scope, sandbox, approvals, and verification explicit.

## When To Use

Use this skill when another Codex run should inspect, implement, or verify a bounded repository task that is too large or parallelizable for the current agent turn.

## Tool Map

- `codex_cli_status`
- `codex_cli_plan`
- `codex_cli_run`
- `codex_capability_status`

## Workflow

1. Use `codex_cli_status` to confirm the CLI is available.
2. Use `codex_cli_plan` to let the configured model prepare the handoff, sandbox, approval policy, and verification plan.
3. Review the generated `codex_cli_run` input before execution.
4. Use `codex_cli_run` only when the task is explicit, bounded, and appropriate for delegation.
5. Treat the delegated result as evidence and verify important claims locally.

## Safety

- Do not pass secrets, unrelated private context, or broad filesystem scope to delegated tasks.
- Do not ask delegated Codex to push, deploy, delete, or install unless the user explicitly approved that scope.
- Keep implementation delegation approval-gated through `codex_cli_run`.

## Native Implementation Boundaries

- Use Humungousaur `codex_cli_status`, `codex_cli_plan`, `codex_cli_run`, and `codex_capability_status` as the native path.
- Treat Codex plugin/skill references as instructions or capability discovery, not as imported runtime implementation.
- Delegated output is not authoritative until the current agent verifies files, tests, and git state.

## Verification

- Keep read-only delegation for investigation.
- Use workspace-write delegation only when implementation is required.
- Do not pass secrets or unrelated private context into delegated tasks.
- Confirm the local repo state, changed files, test output, and claimed blockers after the delegated run.
