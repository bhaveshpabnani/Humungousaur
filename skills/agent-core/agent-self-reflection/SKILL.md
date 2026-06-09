---
name: agent-self-reflection
description: Review recent agent behavior, uncertainty, mistakes, interaction quality, and lessons so the assistant can improve future work. Use after complex tasks, failures, user corrections, or long sessions.
---

# Agent Self Reflection

## Purpose

Run a model-led reflection over recent work so the assistant can understand what happened, what worked, what failed, and what should change. This is a Humungousaur-owned adaptation of external reference self-reflection patterns.

## When To Use

Use after a smoke failure, user correction, long debugging session, complex implementation, or any task where future behavior should improve from evidence.

## Inputs And Evidence

- Recent audit runs and notes.
- Current `cognitive_state`.
- User corrections and preferences.
- Test results, tool failures, and recovery actions.
- Current commitments and follow-ups.

## Tool Map

- `cognitive_self_review`
- `cognitive_self_review_status`
- `cognitive_interaction_review`
- `cognitive_interaction_review_status`
- `cognitive_skill_evolve`
- `memory_write`
- `memory_summary`

## Workflow

1. Gather exact evidence from recent work before reflecting.
2. Ask the model to separate facts, uncertainty, risks, user impact, and recommended changes.
3. Record durable lessons only when supported by evidence.
4. Use skill evolution when the lesson is reusable workflow knowledge.
5. Use persona evolution only when the evidence reflects communication style or stable user preference.
6. Report a concise reflection with concrete next changes.

## Safety And Boundaries

- Do not overfit one incident into a permanent rule.
- Do not hide failures; reflection should surface evidence and limitations.
- Do not claim improvement unless the behavior was changed or recorded.

## Safety And Approval

- Reflection must not rewrite durable memory, skills, persona, or commitments without evidence and the native tool's approval/validation path.
- Do not store sensitive or speculative user facts from a single ambiguous event.
- Do not use reflection to justify ignoring the user's newest instruction or active task.
- Keep user-facing reflection concise unless the user asks for a detailed postmortem.

## Native Implementation Boundaries

- Use Humungousaur cognitive self-review, interaction-review, skill-evolution, and memory tools.
- Do not import upstream self-reflection implementations or create deterministic moral/confidence scoring.
- Model-led providers decide semantic lessons; deterministic code only validates schemas, persists records, and surfaces evidence.

## Verification

- The reflection should mention the evidence inspected.
- Any durable memory or skill update should include evidence references.
- User-facing conclusions should distinguish fact from recommendation.

## Failure Modes

- Generic apologies without evidence.
- Creating permanent preferences from one ambiguous comment.
- Reflecting instead of finishing urgent active work.

## References

- Shortlist item: `agent-self-reflection`.
- Upstream inspiration: external reference `agent-self-reflection`.
- Humungousaur cognition: self-review and interaction-review providers.
