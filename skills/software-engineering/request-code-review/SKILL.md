---
name: request-code-review
description: Prepare a change for human or delegated review by summarizing scope, evidence, tests, risks, and focused reviewer questions.
---

# Request Code Review

## Purpose

Help the user ask for a useful review. This skill packages a change so reviewers can understand intent, risk, verification, and open questions quickly.

## When To Use

Use before PR creation, before asking another agent/human to review, or when preparing a review handoff.

## Inputs And Evidence

- Changed files, commit/diff, test output, design intent, and unresolved questions.
- Risk areas, approvals, and known limitations.

## Tool Map

- `run_shell_command`
- `read_file`
- `diff_render`
- `write_note`
- `codex_cli_plan`
- `codex_cli_run`

## Workflow

1. Inspect diff/status and identify the actual scope.
2. Summarize what changed and why.
3. List verification commands and results.
4. Call out risks, assumptions, and known gaps.
5. Ask focused reviewer questions.
6. If delegating review, use Codex delegation only after approval and verify the result.

## Native Implementation Boundaries

- Use native Git/shell, file, diff, and Codex tools.
- Do not import Hermes requesting-code-review scripts.
- Do not fabricate test results.

## Safety And Approval

- Do not push/open PR unless the user asks.
- Do not include secrets or unrelated local details in review notes.
- Preserve dirty worktree boundaries.

## Verification

- Review request should match current diff.
- Test claims must match command output.
- Delegated review findings should be verified before action.

## Failure Modes

- Asking reviewers to inspect too broad a scope.
- Hiding known risks.
- Summarizing stale changes after additional edits.

## References

- Shortlist item: `request-code-review`.
- Related skill: `code-review`.
