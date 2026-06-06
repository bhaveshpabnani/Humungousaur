---
name: github-issues
description: Create, inspect, triage, label, and update GitHub issues using native GitHub CLI/API paths when configured, with evidence and approval boundaries.
---

# GitHub Issues

## Purpose

Manage issue workflows without losing context. This skill helps turn bugs, feature requests, logs, and investigations into clear GitHub issue records.

## When To Use

Use for issue creation, triage, updates, linking PRs, labeling, milestones, and summarizing issue state.

## Inputs And Evidence

- Repo, issue number/title, labels, severity, reproduction, logs, screenshots, and desired action.
- gh auth status or API setup.

## Tool Map

- `run_shell_command`
- `read_file`
- `write_note`
- `systematic-debugging`
- `status-update-writing`

## Workflow

1. Identify repo and issue intent.
2. Gather reproduction or evidence before drafting.
3. Draft issue title, problem, expected behavior, actual behavior, steps, impact, and evidence.
4. Use `gh issue` only when configured and the user wants live GitHub action.
5. For updates, inspect current issue state first.
6. Report exact created/updated URL or keep as a draft.

## Native Implementation Boundaries

- Use native shell/gh or future Humungousaur GitHub tools.
- Do not import Hermes GitHub issue scripts.
- Do not pretend GitHub was updated when only a draft was written.

## Safety And Approval

- Public or team-visible issue creation/update needs user approval.
- Redact secrets, customer data, tokens, and private logs.
- Confirm repo before posting.

## Verification

- Live updates require a URL or command output.
- Drafts should be clearly marked unsent.
- Labels/milestones should match existing repo choices when checked.

## Failure Modes

- Filing vague issues without reproduction.
- Posting private data.
- Updating the wrong repository.

## References

- Shortlist item: `github-issues`.
- Native path: GitHub CLI through approved shell tooling.
