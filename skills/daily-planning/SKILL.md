---
name: daily-planning
description: Plan a day or work session by reviewing goals, commitments, memory, activity, calendar-like inputs, and current environment, then producing prioritized tasks, follow-ups, and wakeups. Use when the user asks to plan today, organize work, choose what to do next, or recover from scattered context.
---

# Daily Planning

## Purpose

Create a realistic plan for the user from current evidence instead of inventing a generic schedule. This skill adapts patterns from OpenClaw daily planner and founder planner workflows into Humungousaur's cognition, commitment, memory, and wakeup tools.

## When To Use

Use when the user asks to plan a day, morning, evening, sprint, work block, or personal assistant agenda. Also use when the user feels scattered and wants the assistant to decide priorities from remembered goals, commitments, activity, and current environment.

## Inputs And Evidence

- `cognitive_state` for active goals, tasks, commitments, wakeups, persona, skills, and focus.
- `memory_summary` or `memory_search` for recent work and stable preferences.
- `activity_search` for recent activity when the user wants context-aware planning.
- `cognitive_commitment_status` for explicit obligations.
- `system_status` or `cognitive_environment_status` for local environment constraints.

## Tool Map

- `cognitive_state`
- `cognitive_priority_review`
- `cognitive_commitment_status`
- `cognitive_trigger_record`
- `cognitive_briefing_prepare`
- `daily_plan_create`
- `daily_plan_inspect`
- `memory_summary`
- `activity_search`
- `voice_response_prepare`

## Workflow

1. Gather current cognitive state and any explicit user constraints such as time window, energy, location, deadline, or "must do" items.
2. Review commitments and wakeups before adding new tasks; do not duplicate obligations already tracked.
3. Ask the model to rank tasks using evidence, user preferences, deadlines, risk, dependencies, and environment constraints.
4. Use `daily_plan_create` to preserve must-do items, time blocks, waiting/deferred items, risks, evidence refs, and reminder drafts.
5. Use `daily_plan_inspect` before responding or before creating any wakeups/commitments.
6. If responding by voice, prepare a brief spoken summary and leave detailed steps in text or notes.

## Safety

- Do not infer private calendar details unless provided by tools or user text.
- Do not create reminders, messages, purchases, or external actions without explicit approval.
- Avoid over-scheduling; preserve focus and recovery time when evidence suggests overload.

## Native Implementation Boundaries

- Use cognition, commitment, memory, activity, and daily-plan tools as the native planning path.
- `daily_plan_create` prepares a local plan only; reminder drafts are not scheduled until separate approved wakeup/cognition tools run.
- Do not import upstream daily-planner code; adapt concepts into Humungousaur-owned plan artifacts and cognitive tools.

## Verification

- The final plan should cite the evidence categories used, such as commitments, memory, activity, or environment.
- Verify that every "must do" item from the user appears in the plan or is explicitly deferred.
- Check that generated wakeups or commitments have a concrete title and reason.
- Inspect daily plan artifacts and confirm `prepared_not_scheduled` unless reminders were explicitly created.

## Failure Modes

- Producing a motivational list without inspecting current state.
- Treating old memories as current deadlines without verification.
- Creating too many parallel priorities.
- Turning suggestions into commitments without user consent.

## References

- Shortlist item: `daily-planning`.
- Upstream inspiration: OpenClaw `agent-daily-planner`, `adhd-founder-planner`.
- Humungousaur standard: `docs/AGENT_SKILL_AUTHORING_STANDARD.md`.
