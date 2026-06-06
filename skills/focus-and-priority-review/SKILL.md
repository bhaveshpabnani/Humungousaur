---
name: focus-and-priority-review
description: Decide what matters most next across active goals, commitments, wakeups, environment constraints, risks, and opportunities. Use when choosing next work, triaging competing tasks, or recovering focus.
---

# Focus And Priority Review

## Purpose

Help the assistant and user choose the next best action from current evidence. This skill maps priority-review concepts to Humungousaur's cognitive priority tools.

## When To Use

Use when the user asks "what should I do next", "continue", "prioritize this", "what is important", or when autonomous work needs a bounded next action.

## Inputs And Evidence

- Active goals, tasks, and focus from `cognitive_state`.
- Commitments, wakeups, and recent briefings.
- Environment constraints and current system status.
- User urgency, deadlines, and interruption tolerance.

## Tool Map

- `cognitive_priority_review`
- `cognitive_priority_status`
- `cognitive_state`
- `cognitive_environment_status`
- `cognitive_commitment_status`
- `automation_daemon_tick`

## Workflow

1. Gather active work and explicit user constraints.
2. Identify hard deadlines, blockers, dependencies, and high-risk unresolved items.
3. Ask the model to rank next actions from evidence instead of task title similarity.
4. Choose one primary focus and at most a few secondary items.
5. If autonomous mode is active, queue only one interruptible next action unless explicitly allowed.
6. Communicate the reasoning and what will be deferred.

## Safety And Boundaries

- Do not bury user-explicit priorities under inferred priorities.
- Do not trigger high-risk work without approval.
- Do not keep cycling priority reviews when the next action is already clear.

## Verification

- The recommendation should map to active records or user input.
- Deferrals should name why they are deferred.
- If a next action is queued, verify it appears in the relevant queue/status.

## Failure Modes

- Producing many "top" priorities.
- Ignoring blockers and choosing an impossible action.
- Ranking from recency alone.

## References

- Shortlist item: `focus-and-priority-review`.
- Humungousaur tools: priority review and cognitive state.
