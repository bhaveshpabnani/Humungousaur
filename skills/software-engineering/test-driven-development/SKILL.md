---
name: test-driven-development
description: Implement changes with red-green-refactor discipline, focused tests, scoped edits, and verification matched to behavioral risk.
---

# Test Driven Development

## Purpose

Use tests as executable evidence for behavior changes. The assistant should add or update focused tests before or alongside implementation when the task risk justifies it.

## When To Use

Use for bug fixes, new behavior, parser/planner changes, shared APIs, regressions, and any change where a focused test can prevent backslide.

## Inputs And Evidence

- Expected behavior, failing case, existing tests, code under test, and verification command.
- Current test output before and after implementation.

## Tool Map

- `search_workspace`
- `read_file`
- `run_shell_command`
- `python_interpreter`
- `write_note`
- `diff_render`

## Workflow

1. Identify the behavior contract and existing coverage.
2. Add or update the smallest meaningful failing test when feasible.
3. Run the targeted test to confirm it fails for the right reason.
4. Implement the minimal scoped fix.
5. Run targeted tests, then broader tests when blast radius warrants it.
6. Refactor only after green tests and only when it reduces real complexity.

## Native Implementation Boundaries

- Use the repo's own test framework and Humungousaur tools.
- Do not import Hermes TDD scripts.
- Do not replace model-led planning with hardcoded test-name routing.

## Safety And Approval

- Do not delete tests to pass.
- Avoid broad snapshots unless they capture real behavior.
- Preserve unrelated user changes.

## Verification

- Report red and green commands when both were run.
- If a red run is skipped, say why.
- Mention any untested residual risk.

## Failure Modes

- Writing a test that only checks implementation detail.
- Overfitting to one brittle assertion.
- Running too narrow a check for a shared contract.

## References

- Shortlist item: `test-driven-development`.
- Upstream inspiration: Hermes TDD reference only.
