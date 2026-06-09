---
name: code-review
description: Review diffs and code for bugs, regressions, missing tests, security risks, and behavioral gaps with findings first and evidence-backed line references.
---

# Code Review

## Purpose

Act as a reviewer, not a summarizer. Prioritize defects, behavioral regressions, security issues, missing tests, and risky assumptions.

## When To Use

Use when the user asks for review, PR review, diff review, bug hunt, pre-merge check, or "is this safe".

## Inputs And Evidence

- Git diff, changed files, tests, related docs, and intended behavior.
- Line references and execution path evidence.

## Tool Map

- `run_shell_command`
- `read_file`
- `search_workspace`
- `diff_render`
- `tool_search`

## Workflow

1. Inspect changed files and surrounding context.
2. Understand intended behavior and affected execution paths.
3. Look for concrete bugs before style concerns.
4. Verify whether tests cover the changed behavior.
5. Present findings first, ordered by severity, with file/line references.
6. If no issues are found, state that clearly and note residual risk.

## Native Implementation Boundaries

- Use Humungousaur file/shell/diff tools.
- Do not import external reference GitHub code-review scripts.
- Do not use regex-only static checks as the review brain.

## Safety And Approval

- Do not modify code during a pure review unless the user asks.
- Avoid exposing private code beyond the workspace.
- Keep comments actionable and grounded.

## Verification

- Findings require specific evidence.
- Test gaps should name the missing behavior.
- Avoid speculative issues without a plausible failure mode.

## Failure Modes

- Leading with a summary instead of defects.
- Reporting style nits while missing behavioral bugs.
- Reviewing only the diff and missing an affected caller.

## References

- Shortlist item: `code-review`.
- Related user preference: review stance means findings first.
