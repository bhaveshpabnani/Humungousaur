---
name: codex-delegation
description: Delegate bounded repository work to Codex CLI through model-planned, approval-gated handoffs.
---

# Codex Delegation

## Tool Map

- `codex_cli_status`
- `codex_cli_plan`
- `codex_cli_run`
- `codex_capability_status`

Use this skill when another Codex run should inspect, implement, or verify a bounded repository task.

Workflow:

1. Use `codex_cli_status` to confirm the CLI is available.
2. Use `codex_cli_plan` to let the configured model prepare the handoff, sandbox, approval policy, and verification plan.
3. Review the generated `codex_cli_run` input before execution.
4. Use `codex_cli_run` only when the task is explicit, bounded, and appropriate for delegation.
5. Treat the delegated result as evidence and verify important claims locally.

Verification:

- Keep read-only delegation for investigation.
- Use workspace-write delegation only when implementation is required.
- Do not pass secrets or unrelated private context into delegated tasks.
