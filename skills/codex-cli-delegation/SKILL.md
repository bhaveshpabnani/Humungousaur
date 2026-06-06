---
name: codex-cli-delegation
description: Delegate bounded repository tasks to Codex CLI using native codex_cli_status, codex_cli_plan, and approval-gated codex_cli_run, then verify results locally.
---

# Codex CLI Delegation

## Purpose

Use Codex CLI as a trusted coding worker when a separate bounded run helps. Delegation is model-planned, approval-gated, and verified locally.

## When To Use

Use for long code inspections, implementation sub-tasks, review, CI debugging, or parallel investigation that has clear scope and success criteria.

## Inputs And Evidence

- Objective, repo path, scope, constraints, sandbox, approval policy, and expected tests.
- Codex CLI readiness, generated run input, worker output, and local verification.

## Tool Map

- `codex_cli_status`
- `codex_cli_plan`
- `codex_cli_run`
- `read_file`
- `run_shell_command`
- `code-review`

## Workflow

1. Check CLI readiness with `codex_cli_status`.
2. Use `codex_cli_plan` to create a safe handoff payload.
3. Review sandbox, approval policy, working directory, prompt, and timeout.
4. Run `codex_cli_run` only when approved and bounded.
5. Treat worker output as evidence, not truth.
6. Verify changed files, tests, and claims locally.

## Native Implementation Boundaries

- Use Humungousaur `codex_cli_*` tools.
- Do not import Hermes Codex wrappers or external delegation scripts.
- Do not pass secrets or unrelated private context.

## Safety And Approval

- `codex_cli_run` is approval-gated.
- Use read-only sandbox for investigation.
- Do not let delegated workers push, deploy, or change unrelated files unless explicitly requested.

## Verification

- Confirm CLI readiness before delegation.
- Confirm run output and changed files.
- Run local tests or review before reporting completion.

## Failure Modes

- Delegating vague goals.
- Trusting worker summaries without verification.
- Choosing a too-broad sandbox.

## References

- Shortlist item: `codex-cli-delegation`.
- Existing related skills: `codex-delegation`, `coding-agent`.
