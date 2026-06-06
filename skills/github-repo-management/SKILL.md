---
name: github-repo-management
description: Manage repository remotes, clones, forks, branches, releases, and repo metadata with native Git/gh commands and strong approval boundaries.
---

# GitHub Repo Management

## Purpose

Handle repo administration tasks carefully. Repo management can affect collaboration and release state, so this skill emphasizes verification and explicit user intent.

## When To Use

Use for cloning, adding remotes, checking origin/upstream, forking, listing branches, releases, tags, repo metadata, and repo setup diagnosis.

## Inputs And Evidence

- Repository URL/path, remote names, branch names, tag/release names, and requested operation.
- Current git status, remotes, auth status, and command output.

## Tool Map

- `run_shell_command`
- `list_files`
- `read_file`
- `system_status`
- `github-pr-workflow`

## Workflow

1. Confirm target repo and operation.
2. Inspect current remotes, branch, and worktree status.
3. For read-only tasks, gather evidence with Git/gh commands.
4. For mutating tasks, confirm exact target and approval.
5. Execute the smallest necessary command.
6. Verify resulting remote/branch/tag/release state.

## Native Implementation Boundaries

- Use Git/gh through native shell tooling or future Humungousaur GitHub adapters.
- Do not import Hermes repo-management scripts.
- Do not use destructive Git commands unless explicitly requested and approved.

## Safety And Approval

- Remotes, branches, releases, tags, forks, and deletes can affect collaborators.
- Do not overwrite history without explicit instruction.
- Keep credentials out of command text and notes.

## Verification

- Report command output for repo state.
- Verify branch/remote after changes.
- If auth blocks action, report the exact blocker.

## Failure Modes

- Managing the parent workspace instead of nested repo.
- Confusing origin and upstream.
- Creating release/tag in the wrong repo.

## References

- Shortlist item: `github-repo-management`.
- Native path: Git/gh through Humungousaur shell tooling.
