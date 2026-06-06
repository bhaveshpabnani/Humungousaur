---
name: agent-worker-handoff
description: Hand bounded work to another agent, CLI, or worker process and verify its output. Use when delegating to Codex CLI, Claude Code, OpenCode, or another trusted specialist runtime.
---

# Agent Worker Handoff

## Purpose

Prepare safe, bounded handoffs to worker agents while keeping Humungousaur responsible for verification and user-facing claims. This adapts Hermes `codex`, `claude-code`, and `opencode` delegation workflows.

## When To Use

Use when a task is too large for a single foreground loop, benefits from independent review, or specifically asks to use a coding worker.

## Inputs And Evidence

- Objective, workspace path, allowed files, constraints, and expected outputs.
- Worker availability and sandbox/approval support.
- Current git state and user changes.
- Verification commands.

## Tool Map

- `codex_cli_status`
- `codex_cli_plan`
- `codex_cli_run`
- `multi_agent_coordinate`
- `run_shell_command`
- `read_file`
- `write_note`

## Workflow

1. Inspect worker availability and current workspace state.
2. Ask the configured model to decide whether delegation is appropriate.
3. Prepare a prompt containing objective, scope, constraints, verification, and reporting format.
4. Prefer read-only or dry-run-first for inspection and review.
5. Execute worker handoff only with approval when the tool requires it.
6. Verify worker outputs locally before incorporating them into the final result.

## Safety And Boundaries

- Do not pass secrets unless absolutely required and explicitly approved.
- Do not delegate outside the intended workspace.
- Do not allow worker-side push/deploy unless the user explicitly requested it.

## Verification

- Confirm worker command, cwd, sandbox, timeout, and output.
- Inspect changed files before accepting results.
- Run listed tests or explain why they could not run.

## Failure Modes

- Treating delegation as completion.
- Sending vague prompts that produce unactionable output.
- Failing to protect user changes in the worktree.

## References

- Shortlist item: `agent-worker-handoff`.
- Upstream inspiration: Hermes `codex`, `claude-code`, `opencode`.
- Existing skills: `codex-delegation`, `coding-agent`.
