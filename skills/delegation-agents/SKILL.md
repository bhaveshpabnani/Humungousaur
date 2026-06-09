---
name: delegation-agents
description: Parent skill for sub-agent delegation, coding-agent handoffs, multi-agent orchestration, Codex/Claude/opencode delegation, and worker contracts.
---

# Delegation Agents

## Purpose

Use this parent skill when work should be split across specialists, delegated to a coding agent, inspected by another agent, or coordinated through explicit worker contracts.

## Hierarchy Reading Rules

1. Decide whether delegation is needed because of parallel evidence gathering, independent review, code implementation, or tool isolation.
2. Load the child skill for the target worker type before creating the handoff.
3. Give sub-agents specific objectives, allowed tools, evidence requirements, and stop conditions.
4. Validate returned work against local evidence before merging it into the main answer.

## Tool Map

- `agent-team-orchestration`
- `agent-worker-handoff`
- `claude-code-delegation`
- `codex-cli-delegation`
- `codex-delegation`
- `coding-agent`
- `opencode-delegation`

## Child Skill Guide

- Use team orchestration and worker handoff for generic sub-agent boards, task splits, and result synthesis.
- Use coding-agent, Codex, Claude Code, Codex CLI, or opencode skills when the delegate is a code worker with specific runtime expectations.
- Keep delegation instructions generalized in the parent and task-specific details inside child skills and handoff payloads.

## Verification

- Treat sub-agent outputs as evidence to verify, not as final truth.
- Record unresolved assumptions and failed worker attempts before finalizing.
