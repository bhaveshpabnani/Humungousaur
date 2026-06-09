---
name: audit-trail-review
description: Inspect run history, approvals, outbox, interpreter manifests, screenshots, and memory events to reconstruct what the agent actually did.
---

# Audit Trail Review

## Purpose

Reconstruct reality from logs and artifacts. This skill helps answer what happened, what was approved, what was sent, what changed, and what remains uncertain.

## When To Use

Use when the user asks current status, "did it send", "what changed", "why did this happen", or for compliance/debug audits.

## Inputs And Evidence

- Run IDs, approval tokens, outbox IDs, interpreter run IDs, screenshot filenames, commit hashes, and memory events.

## Tool Map

- `channel_outbox`
- `python_interpreter_runs`
- `python_interpreter_run`
- `screen_captures`
- `memory_search`
- `cognitive_state`
- `status-update-writing`

## Workflow

1. Identify the time window and artifact types.
2. Inspect relevant native stores/tools.
3. Separate prepared, approved, executed, failed, blocked, and skipped actions.
4. Tie claims to IDs/paths/tool results.
5. Report missing evidence as missing.
6. Recommend cleanup or follow-up if needed.

## Native Implementation Boundaries

- Use Humungousaur audit/artifact/status tools.
- Do not import external reference audit-trail plugins.
- Do not infer completion without evidence.

## Safety And Approval

- Audit logs may contain sensitive data.
- Redact secrets and private messages.
- Do not delete artifacts unless approved.

## Verification

- Cite IDs, paths, commits, or statuses.
- Confirm current worktree/run state.
- Label uncertainty.

## Failure Modes

- Relying on memory instead of logs.
- Mixing prepared and sent states.
- Ignoring failed approvals.

## References

- Shortlist item: `audit-trail-review`.
