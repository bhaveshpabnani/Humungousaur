---
name: systematic-debugging
description: Debug failures through evidence collection, reproduction, hypothesis ranking, focused fixes, and verification instead of brittle error-string matching.
---

# Systematic Debugging

## Purpose

Find root causes methodically. The assistant should collect current evidence, reproduce the problem when possible, form hypotheses, test them, patch narrowly, and verify the fix.

## When To Use

Use for test failures, runtime errors, broken UI flows, flaky behavior, integration issues, CI failures, and "why does this not work" tasks.

## Inputs And Evidence

- Error output, logs, failing command, expected behavior, recent changes, and environment.
- Source files, tests, config, runtime status, and reproduction steps.
- Verification command output after the fix.

## Tool Map

- `read_file`
- `search_workspace`
- `run_shell_command`
- `python_interpreter`
- `browser_live_observe`
- `system_status`
- `write_note`

## Workflow

1. Reproduce or inspect the failure with current evidence.
2. Define what "fixed" means before editing.
3. Rank hypotheses from evidence, not keyword triggers.
4. Inspect the smallest relevant code path.
5. Make a scoped fix that preserves existing behavior.
6. Run targeted verification and report residual risk.

## Native Implementation Boundaries

- Use Humungousaur tools and current repo commands.
- Do not import Hermes debugging helpers or upstream scripts.
- Do not implement deterministic error-message-to-fix maps.

## Safety And Approval

- Avoid destructive cleanup unless explicitly approved.
- Do not mask failures by weakening tests.
- Keep user changes intact.

## Verification

- The failing command should pass or the remaining blocker should be proven.
- Add or update tests when risk warrants it.
- Report exact commands run and outcomes.

## Failure Modes

- Patching the symptom while root cause remains.
- Over-broad refactors during debugging.
- Trusting stale logs.

## References

- Shortlist item: `systematic-debugging`.
- Upstream inspiration: Hermes systematic debugging reference only.
