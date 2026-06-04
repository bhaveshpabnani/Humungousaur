---
name: taskflow
description: Coordinate durable multi-step work with goals, tasks, waits, wakeups, autonomous cycles, and child/delegated tasks.
---

# TaskFlow

Use this skill when work should outlive one prompt, wait on external events, delegate subtasks, or require resumable progress.

## When To Use

- Multi-step tasks with one owner.
- Work that needs scheduled follow-up.
- Work waiting on a person, channel reply, file change, or external system.
- Background tasks that need status, cancellation, or resumption.
- Delegated coding or research jobs with child tasks.

## Humungousaur Shape

Use cognitive tools and stores for:

- goals;
- tasks;
- wakeups;
- triggers;
- runtime event queue;
- autonomous cycles;
- memories and learning records.

## Workflow

1. Create or reuse an active goal.
2. Add tasks with success criteria.
3. For work that cannot continue now, schedule a wakeup or trigger.
4. For background progress, run an autonomous cycle.
5. For delegation, link the child run or worker result back to the goal/task.
6. On completion, record evidence and learning.

## Wait States

Use a waiting state when:

- credentials are missing;
- approval is required;
- a user reply is needed;
- a remote channel must deliver a response;
- a scheduled time has not arrived.

Record the reason and the exact next stimulus that should resume the work.

## Verification

- Every durable task should have an owner, status, reason, and evidence refs.
- Do not create background loops without a stopping condition.
- Do not mark a task complete merely because a run started.
