---
name: status-update-writing
description: Create concise blocker-first project updates, daily summaries, handoff notes, and progress reports from verified task, run, and commitment evidence.
---

# Status Update Writing

## Purpose

Turn work state into compact updates the user and collaborators can scan quickly. The preferred shape is blocker-first, evidence-backed, and clear about what is done, pending, blocked, and next.

## When To Use

Use when the user asks for current status, daily update, project update, standup note, handoff, "what changed", "where are we", or a communication-ready progress summary.

## Inputs And Evidence

- Git status, run results, tests, outbox, commitments, notes, and task records.
- User's target audience and channel.
- Known blockers, approvals, missing setup, or uncertainty.

## Tool Map

- `writing_draft_create`
- `writing_draft_inspect`
- `cognitive_state`
- `cognitive_commitment_status`
- `cognitive_interaction_review`
- `read_file`
- `search_workspace`
- `channel_message_prepare`
- `write_note`

## Workflow

1. Gather current evidence before summarizing.
2. Lead with blockers or risks when they affect action.
3. List completed work only when verified by files, tests, commits, or tool results.
4. Separate "done", "in progress", "blocked", "not started", and "next".
5. Keep updates short unless the user asks for detailed audit.
6. Save status drafts with `writing_draft_create` when the update should be reused or sent later.
7. Prepare channel-ready versions only after checking audience and approval needs.

## Native Implementation Boundaries

- Use Humungousaur state, file, channel, and cognition tools.
- Do not rely on upstream status templates as runtime dependencies.
- Do not use keyword matching to decide which updates matter; let model-led review rank relevance from evidence.

## Safety And Approval

- Do not claim completion without verification.
- Do not expose private local paths or secrets in team updates unless necessary and approved.
- Mark uncertainty plainly.

## Verification

- Each status claim should have a file, test, run, commit, or state record behind it.
- Channel drafts should be in outbox or clearly unsent.
- If evidence is missing, say what was not verified.

## Failure Modes

- Flat summaries that hide blockers.
- Reporting stale worktree state.
- Saying "pushed" when changes are only local.

## References

- Shortlist item: `status-update-writing`.
- User preference: direct current-status answers with evidence.
