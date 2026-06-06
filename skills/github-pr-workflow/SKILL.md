---
name: github-pr-workflow
description: Manage GitHub pull-request workflows with native Git/gh shell commands, scoped branches, verification, CI inspection, and explicit user approval for pushes/merges.
---

# GitHub PR Workflow

## Purpose

Support branch-to-PR delivery while protecting worktree state and user changes. This skill uses local Git/gh through native shell tooling when configured.

## When To Use

Use for creating branches, committing, pushing, opening PRs, checking PR status, inspecting CI, or preparing merge-ready summaries.

## Inputs And Evidence

- Repo root, branch, remote, diff, commits, PR URL/number, CI checks, and user approval.
- Current worktree status and verification output.

## Tool Map

- `run_shell_command`
- `read_file`
- `search_workspace`
- `write_note`
- `code-review`
- `ci-failure-debugging`

## Workflow

1. Confirm repo root and worktree status.
2. Protect unrelated dirty changes.
3. Run appropriate tests or diff checks before commit when feasible.
4. Commit intentionally with scoped files.
5. Push only when the user requested it.
6. Open or inspect PR with `gh` only when configured and approved.
7. Report PR URL, branch, checks, and remaining risk.

## Native Implementation Boundaries

- Use native shell/Git/gh commands through Humungousaur tooling or the current Codex environment.
- Do not import Hermes GitHub workflow scripts.
- Do not use upstream GitHub helpers as runtime implementation.

## Safety And Approval

- Pushing, merging, rebasing shared branches, or deleting branches requires explicit user intent.
- Never reset or discard user changes without explicit instruction.
- Do not include secrets in commits or PR text.

## Verification

- Git status should be inspected before staging and after commit.
- Test/CI results should be current.
- PR claims require command output or connector evidence.

## Failure Modes

- Committing unrelated files.
- Pushing to the wrong branch.
- Saying CI is green without checking current checks.

## References

- Shortlist item: `github-pr-workflow`.
- Native tools: Git/gh through `run_shell_command` and local environment.
