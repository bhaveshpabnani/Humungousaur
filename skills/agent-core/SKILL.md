---
name: agent-core
description: Parent skill for core agent cognition, safety, memory, taskflow, approvals, system readiness, and self-improvement workflows.
---

# Agent Core

## Purpose

Use this parent skill when a request is about the agent's own operating loop: memory, goals, priorities, approvals, safety, autonomy, task tracking, system state, or capability health.

## Hierarchy Reading Rules

1. Read this parent first to choose the smallest relevant child skill.
2. Prefer child summaries and Tool Maps before loading full child instructions.
3. Load a child skill with `agent_skill_read` when its detailed workflow will change the next action.
4. Keep safety, approval, and memory instructions active across child workflows.

## Tool Map

- `agent-access-control`
- `agent-self-assessment`
- `agent-self-reflection`
- `ambient-room-context`
- `approval-gated-external-actions`
- `audit-trail-review`
- `autonomous-loop-operations`
- `bot-loop-protection`
- `capability-audit`
- `capability-surfaces`
- `focus-and-priority-review`
- `memory-metabolism`
- `persona-evolution`
- `prompt-injection-screening`
- `secrets-handling`
- `session-wrap-up`
- `system-health-check`
- `task-tracking`
- `taskflow`
- `wakeup-scheduling`

## Child Skill Guide

- Use access, approvals, prompt-injection, bot-loop, and secrets skills for safety boundaries before high-risk or external actions.
- Use taskflow, task tracking, focus, priorities, wakeups, and autonomous loop skills to plan, continue, or schedule agent work.
- Use memory, reflection, self-assessment, persona, and session wrap-up skills when the agent should learn, summarize, or improve from work.
- Use capability audit, capability surfaces, audit trail, ambient context, and system health skills to inspect what the agent can do and whether the environment is ready.

## Verification

- Do not claim durable learning, approval, or scheduling happened unless the relevant child tool or child skill produced evidence.
- Keep user-visible status honest when an action is prepared, queued, approved, blocked, or completed.
