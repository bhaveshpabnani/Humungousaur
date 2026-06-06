---
name: wakeup-scheduling
description: Create, review, evaluate, and cancel future reminders, wakeups, and triggers for the assistant. Use when the user wants follow-ups, timed checks, reminders, monitors, or future task continuation.
---

# Wakeup Scheduling

## Purpose

Manage future stimuli for the assistant in a bounded, auditable way. This skill adapts reminder and scheduling patterns from Hermes Apple Reminders and OpenClaw calendar/scheduling skills into Humungousaur triggers and wakeups.

## When To Use

Use when the user asks to remind, check later, follow up, monitor, continue tomorrow, run a future task, or cancel a scheduled wakeup.

## Inputs And Evidence

- User-stated trigger condition or time.
- Existing trigger and wakeup status.
- Commitments and related task context.
- Channel or response-mode constraints.

## Tool Map

- `cognitive_trigger_record`
- `cognitive_trigger_status`
- `cognitive_trigger_evaluate`
- `cognitive_trigger_cancel`
- `cognitive_commitment_status`
- `automation_daemon_status`

## Workflow

1. Clarify whether the user wants a one-time reminder, recurring monitor, conditional trigger, or task continuation.
2. Inspect existing triggers to avoid duplicates.
3. Record a trigger with clear name, text, source, and reason.
4. If a commitment is related, link the wakeup context in the reason or evidence.
5. For cancellation, use exact trigger ID where possible.
6. Verify the trigger appears in status and explain how it will fire.

## Safety And Boundaries

- Do not schedule external-visible actions without explicit approval.
- Do not create vague recurring monitors with no stop condition.
- Do not infer exact dates from ambiguous words without the current date/time context.

## Verification

- Confirm trigger ID, status, and trigger text.
- Confirm due/condition semantics in plain language.
- For cancellation, verify the target trigger was cancelled.

## Failure Modes

- Creating duplicate reminders for the same task.
- Misinterpreting relative dates.
- Scheduling a wakeup but failing to mention response mode.

## References

- Shortlist item: `wakeup-scheduling`.
- Upstream inspiration: Hermes `apple-reminders`, OpenClaw calendar/scheduling category.
- Humungousaur tools: trigger and automation daemon tools.
