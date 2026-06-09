---
name: coding-agent
description: Delegate bounded repository work to Codex CLI or another trusted coding worker with explicit scope, verification, and completion reporting.
---

# Coding Agent Delegation

## Purpose

Coordinate bounded coding work through native Codex CLI and multi-agent tools while preserving user changes, test evidence, and explicit completion reporting.

## Tool Map

- `codex_cli_status`
- `codex_cli_plan`
- `codex_cli_run`
- `multi_agent_coordinate`
- `multi_agent_board`

Use this skill for background feature builds, code reviews, large refactors, and issue-to-PR loops. Do not use it for simple edits or read-only lookup.

## When To Delegate

Delegate when the work is:

- bounded and testable;
- repository-local;
- long enough to benefit from a separate worker;
- safe to run in the chosen sandbox;
- not dependent on secrets or private context the worker does not need.

## Required Steps

1. Check CLI availability with `codex_cli_status` or a shell command.
2. Prepare a prompt that includes:
   - objective;
   - repo path;
   - files or modules likely involved;
   - constraints;
   - expected tests;
   - how to report completion.
3. Use `codex_cli_plan` when available to prepare the handoff.
4. Use `codex_cli_run` only when the user requested implementation or verification that fits delegation.
5. Verify important claims locally after the worker completes.

## Workflow

1. Decide whether delegation is warranted or whether the current agent should do the work directly.
2. Check `codex_cli_status` and current repository state.
3. Build a scoped handoff with `codex_cli_plan` or `multi_agent_coordinate`.
4. Use `codex_cli_run` only after reviewing the generated task, sandbox, and approval requirements.
5. Re-read local git status, diffs, and relevant files after completion.
6. Run focused verification locally before accepting the worker's result.

## Prompt Shape

Include:

```text
Task:
<clear objective>

Workspace:
<absolute repo path>

Constraints:
- preserve user changes
- do not store secrets
- keep edits scoped
- run listed tests

Completion:
- summarize files changed
- report test output
- report blockers
```

## Safety

- Never delegate arbitrary secrets.
- Do not ask a worker to edit outside the intended workspace.
- Do not let a worker push or deploy unless the user explicitly asked.
- Treat worker output as evidence, not truth; verify.

## Native Implementation Boundaries

- Use native Codex and multi-agent Humungousaur tools for handoffs; do not shell out to unmodeled assistants or import third-party agent harnesses.
- Keep deterministic code limited to command construction, sandbox validation, and result capture.
- Mark unavailable CLIs as setup blockers instead of simulating delegation.

## Verification

- Confirm the worker ran in the intended workspace and sandbox.
- Confirm changed files are scoped to the delegated objective.
- Confirm test output or blocker evidence locally.
- Confirm no secrets or unrelated user changes were staged, committed, or reported as agent work.
