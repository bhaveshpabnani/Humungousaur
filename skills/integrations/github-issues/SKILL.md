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

- `github_issue_packet_create`
- `github_artifact_inspect`
- `secret_scan_report_create`
- `approval_policy_review_create`
- `run_shell_command`
- `read_file`
- `write_note`
- `systematic-debugging`
- `status-update-writing`

## Workflow

1. Identify repo and issue intent.
2. Gather reproduction or evidence before drafting.
3. Use `github_issue_packet_create` to create a local issue packet with title, problem, expected behavior, actual behavior, steps, impact, labels, and evidence.
4. Inspect the packet with `github_artifact_inspect` before posting, sharing, or referencing it as a final artifact.
5. Use `secret_scan_report_create` or an equivalent review before including logs, configs, screenshots, or customer data.
6. Use `gh issue` only when configured and the user wants live GitHub action.
7. For updates, inspect current issue state first.
8. Report exact created/updated URL or keep as a draft.

## Native Implementation Boundaries

- Use native Humungousaur GitHub packet tools first for drafts and triage.
- Use native shell/gh only for approved live GitHub action.
- Do not import external reference GitHub issue scripts.
- Do not pretend GitHub was updated when only a draft was written.

## Safety And Approval

- Public or team-visible issue creation/update needs user approval.
- Redact secrets, customer data, tokens, and private logs.
- Confirm repo before posting.

## Verification

- Live updates require a URL or command output.
- Drafts should be clearly marked unsent with `live_execution_status: not_executed`.
- Labels/milestones should match existing repo choices when checked.

## Failure Modes

- Filing vague issues without reproduction.
- Posting private data.
- Updating the wrong repository.

## References

- Shortlist item: `github-issues`.
- Native path: GitHub CLI through approved shell tooling.
