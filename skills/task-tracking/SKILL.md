---
name: task-tracking
description: Track tasks, commitments, blockers, statuses, and next actions across ongoing user work. Use when the user asks what is pending, what changed, what is blocked, what should be updated, or how to keep a task moving.
---

# Task Tracking

## Purpose

Maintain a concrete working ledger of tasks and obligations using Humungousaur's commitment, cognition, memory, and activity tools. This skill adapts OpenClaw task tracker patterns into local-first, evidence-backed tracking.

## When To Use

Use when the user asks to track work, update task status, review blockers, list follow-ups, inspect pending commitments, or continue an existing task across sessions.

## Inputs And Evidence

- Current `cognitive_state`.
- Commitment records from `cognitive_commitment_status`.
- Recent run notes, memory summaries, and activity records.
- Tool outputs from the task being tracked.
- User-provided status updates.

## Tool Map

- `cognitive_commitment_status`
- `cognitive_commitment_record`
- `cognitive_commitment_update`
- `cognitive_commitment_review`
- `cognitive_state`
- `memory_write`
- `memory_search`
- `activity_search`

## Workflow

1. Identify whether the user is asking to inspect, create, update, resolve, or summarize tasks.
2. Gather current commitments and active goals before writing anything new.
3. For each task, preserve title, status, owner, evidence, next action, blocker, and due/wakeup info when available.
4. Update exact commitment IDs when they exist; create new records only for genuinely new obligations.
5. Keep "waiting on user", "waiting on external system", and "ready to continue" distinct.
6. End with a concise task board and the most useful next action.

## Safety And Boundaries

- Do not mark work complete unless current evidence proves completion.
- Do not fabricate due dates or owners.
- Do not overwrite unrelated commitments because names look similar.

## Verification

- Every status update should include evidence from user input, tool output, or a stored record.
- Resolved tasks should include a completion reason.
- Blocked tasks should name the concrete blocker and the next unblock condition.

## Failure Modes

- Creating duplicate commitments from paraphrased task names.
- Marking a task done because a plan was written.
- Losing external dependencies or approvals.

## References

- Shortlist item: `task-tracking`.
- Upstream inspiration: OpenClaw `agent-task-tracker`.
- Humungousaur tools: commitment and cognition tool groups.
