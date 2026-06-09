---
name: agent-team-orchestration
description: Coordinate multiple specialists or agent workers with task lifecycle, handoffs, reviews, and evidence-based completion. Use for complex work that benefits from delegation, parallel review, or role separation.
---

# Agent Team Orchestration

## Purpose

Break complex work into specialist tasks while preserving a single accountable orchestrator. This adapts external reference team orchestration and external reference kanban-orchestrator concepts into Humungousaur's multi-agent coordination board.

## When To Use

Use for large engineering changes, research plus implementation, security review, UI plus backend tasks, or any goal requiring multiple roles and verifiable handoffs.

## Inputs And Evidence

- User objective and success criteria.
- Current capability surface and available specialists.
- Existing task board and active commitments.
- Risk/approval boundaries.

## Tool Map

- `multi_agent_coordinate`
- `multi_agent_board`
- `cognitive_state`
- `cognitive_priority_review`
- `codex_cli_plan`
- `codex_cli_run`
- `write_note`

## Workflow

1. Define the shared goal and completion evidence.
2. Split work into small tasks with owner/role, input evidence, expected output, and verification.
3. Use `multi_agent_coordinate` to record a board when the task set is non-trivial.
4. Delegate to external workers only after model-led delegation planning and approval policy review.
5. Require each worker output to be verified locally.
6. Merge results into one final answer with unresolved risks and next actions.

## Safety And Boundaries

- Do not delegate secrets or broad write access unnecessarily.
- Treat worker output as evidence, not truth.
- Do not let parallel work overwrite user changes.

## Safety And Approval

- Delegate only bounded tasks with explicit workspace, allowed files, expected outputs, and verification.
- Require approval before external workers run commands, modify files, call live services, push, deploy, or access secrets.
- Keep one accountable orchestrator responsible for reviewing worker output and protecting user changes.
- Pause coordination if workers conflict, produce unverifiable claims, or require credentials/user decisions.

## Native Implementation Boundaries

- Use Humungousaur `multi_agent_coordinate`, board, cognitive state, priority, Codex delegation, and note tools.
- external reference/external reference team concepts are reference patterns only; task boards and handoffs must be stored through Humungousaur-native tools.
- Worker outputs are imported as evidence packets, not automatically trusted state.

## Verification

- Board should list tasks, owners/roles, statuses, and expected evidence.
- Every completed task should have verification output or a review note.
- Final response should identify unverified worker claims.

## Failure Modes

- Splitting work into roles but never reconciling outputs.
- Letting a worker commit/push/deploy without explicit approval.
- Creating coordination overhead for a simple task.

## References

- Shortlist item: `agent-team-orchestration`.
- Upstream inspiration: external reference `agent-team-orchestration`, external reference `kanban-orchestrator`.
- Humungousaur tool: `multi_agent_coordinate`.
