---
name: autonomous-loop-operations
description: Run bounded autonomous cycles over queued events, due wakeups, ready tasks, and optional initiative while preserving approvals and stop conditions. Use when configuring, testing, or operating Humungousaur as a continuing assistant.
---

# Autonomous Loop Operations

## Purpose

Operate the assistant's autonomous loop safely: ingest stimuli, decide whether to act, execute bounded work, record evidence, and stop cleanly. This adapts OpenClaw autonomy primitive ideas to Humungousaur's automation daemon and cognition loop.

## When To Use

Use when the user wants the agent to run continuously, process queued tasks, wake itself up, watch for ready work, or perform one bounded daemon tick.

## Inputs And Evidence

- `autonomous-status` or `automation_daemon_status`.
- Queue entries, wakeups, triggers, recent cycles, and active commitments.
- User-configured loop policy such as max cycles, idle behavior, and approval posture.
- Current tool permissions and safety gates.

## Tool Map

- `automation_daemon_status`
- `automation_daemon_configure`
- `automation_daemon_tick`
- `cognitive_trigger_status`
- `cognitive_trigger_evaluate`
- `cognitive_priority_review`
- `cognitive_state`

## Workflow

1. Inspect daemon status and current queue before changing configuration.
2. Confirm loop bounds: max cycles, idle stop condition, response mode, approval behavior, and whether initiative is allowed.
3. Configure the daemon only when the user asks to persist loop settings.
4. Run one tick for verification before suggesting a longer loop.
5. Review tick output for actions taken, skipped work, approvals, and queued follow-ups.
6. Record lessons or environment constraints when the loop exposes recurring blockers.

## Safety And Boundaries

- Never run unbounded loops without an explicit user request and clear stop conditions.
- External-visible actions still require the channel/message/tool approval policy.
- Do not enable initiative when the user asked only for passive monitoring.

## Safety And Approval

- Always set bounded max cycles, idle stop behavior, and initiative policy before running a loop.
- Run a single verification tick before recommending continuous operation.
- Keep high-risk, external-visible, destructive, or privileged actions paused for approval.
- Stop or reduce scope on repeated failures, duplicate event processing, model/provider unavailability, or unclear queue state.

## Native Implementation Boundaries

- Use Humungousaur automation daemon, trigger, priority review, cognitive state, queue, and autonomous-cycle tools.
- OpenClaw autonomy patterns are reference concepts only; runtime state and loop execution must remain Humungousaur-native.
- The model owns semantic decisions about attention and initiative; deterministic code only enforces bounds, queue mechanics, schemas, and approvals.

## Verification

- Confirm the loop reports cycle count, idle state, and queue changes.
- Check whether high-risk actions were paused for approval.
- Ensure final status explains whether more work remains queued.

## Failure Modes

- Treating "continuous" as permission for unlimited tool use.
- Reprocessing the same event repeatedly.
- Running initiative when the user wanted silence.

## References

- Shortlist item: `autonomous-loop-operations`.
- Upstream inspiration: OpenClaw `agent-autonomy-primitives`.
- Humungousaur tools: automation daemon and trigger tools.
