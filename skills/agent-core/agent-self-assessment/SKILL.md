---
name: agent-self-assessment
description: Assess the assistant's readiness, capability fit, safety risks, tool coverage, and verification plan before or during complex work. Use when work is high-impact, ambiguous, risky, long-running, or failure-prone.
---

# Agent Self Assessment

## Purpose

Create an explicit readiness check before the assistant commits to complex action. This skill combines external reference agent audit and self-assessment ideas with Humungousaur capability, tool, policy, and cognition surfaces.

## When To Use

Use for high-impact tasks, broad architecture changes, long autonomous runs, external integrations, multi-agent work, or when the assistant is unsure whether it has enough tools and context.

## Inputs And Evidence

- Capability surface and tool descriptions.
- Current workspace state and relevant files.
- Model provider readiness.
- Safety policy and approval requirements.
- Known blockers, memory, and environment constraints.

## Tool Map

- `capability_surface`
- `tool_search`
- `tool_describe`
- `cognitive_self_review`
- `cognitive_environment_status`
- `system_status`
- `plugin_catalog`
- `channel_catalog`

## Workflow

1. Clarify the objective and expected end state.
2. Inspect capability surface and relevant tool schemas.
3. Identify missing credentials, missing tools, policy gates, and high-risk actions.
4. Decide whether to proceed, narrow scope, ask for input, or run a safer dry run.
5. Define verification evidence before execution.
6. Reassess after failures or surprising tool output.

## Safety And Boundaries

- Do not use assessment as a substitute for doing safe, obvious work.
- Do not downplay risks when tools can affect external systems.
- If a model/provider is unavailable, stop or use explicit tool commands only; do not invent deterministic intent handling.

## Safety And Approval

- Treat self-assessment as advisory evidence, not permission to bypass approval gates.
- If the assessment identifies external-visible, destructive, privileged, or privacy-sensitive actions, require the relevant tool approval before execution.
- Do not downgrade risk because a task is familiar; use current tool schemas, provider status, credentials, and workspace state.
- Report model-unavailable or tool-unavailable states honestly instead of substituting brittle keyword rules.

## Native Implementation Boundaries

- Use Humungousaur capability, tool, cognition, plugin, channel, and system-status tools only.
- external reference or other references may shape the checklist, but readiness decisions must be model-led and evidence-backed through native records.
- A readiness claim is valid only for the current workspace/configuration snapshot; rerun assessment after tool, credential, branch, or environment changes.

## Verification

- Assessment output should name capability gaps and verification steps.
- Any "ready" claim must be backed by current tool or status output.
- High-risk actions must show approval posture.

## Failure Modes

- Producing a vague confidence score without evidence.
- Continuing after a missing credential blocks the actual requirement.
- Recommending tools that are not present in the catalog.

## References

- Shortlist item: `agent-self-assessment`.
- Upstream inspiration: external reference `agent-self-assessment`, `agent-audit`.
- Humungousaur docs: `docs/GLOBAL_AGENT_INSTRUCTIONS.md`.
