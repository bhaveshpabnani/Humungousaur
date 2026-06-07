---
name: ci-failure-debugging
description: Inspect failing CI checks, retrieve logs, reproduce locally when possible, patch root causes, and verify without weakening tests.
---

# CI Failure Debugging

## Purpose

Turn red CI into actionable evidence and a verified fix. This skill separates CI environment issues, test failures, dependency problems, and real regressions.

## When To Use

Use when GitHub Actions or other CI checks fail, PR checks are red, logs need inspection, or local tests differ from CI.

## Inputs And Evidence

- PR/commit, failing check name, log output, local reproduction command, and changed files.
- CI environment, dependency versions, and workflow config.

## Tool Map

- `ci_failure_report_create`
- `github_artifact_inspect`
- `github_pr_packet_create`
- `github_repo_state_report_create`
- `run_shell_command`
- `read_file`
- `search_workspace`
- `systematic-debugging`
- `github-pr-workflow`
- `code-review`

## Workflow

1. Identify failing check and current commit.
2. Retrieve logs with `gh` or provided evidence.
3. Classify failure: test, lint, build, environment, auth, flake, or workflow config.
4. Create a durable `ci_failure_report_create` artifact with check name, workflow/run URL, log excerpt, suspected causes, reproduction commands, fix plan, verification, and residual risks.
5. Inspect the report with `github_artifact_inspect` before patching or summarizing.
6. Reproduce locally when feasible.
7. Patch root cause, not just CI symptoms.
8. Run targeted local checks and re-inspect CI status after push if requested.

## Native Implementation Boundaries

- Use native shell/GitHub CLI and repo tooling.
- Use native CI failure report artifacts to hold evidence and avoid brittle log-pattern fixes.
- Do not import external CI-fix scripts.
- Do not hardcode failure-pattern-to-fix maps.

## Safety And Approval

- Do not weaken tests, ignore lint, or skip CI without explicit reason.
- Pushing CI fixes requires user intent.
- Redact secrets from logs.

## Verification

- A fixed claim needs passing local command or current CI evidence.
- If CI cannot be checked, report local-only verification.
- Local CI reports should show `live_execution_status: not_executed` when no live CI query or update occurred.
- Keep residual flake risk explicit.

## Failure Modes

- Fixing a different failure than the red check.
- Assuming CI logs are current.
- Masking a production bug by changing tests.

## References

- Shortlist item: `ci-failure-debugging`.
- Native path: GitHub CLI and repo test commands.
