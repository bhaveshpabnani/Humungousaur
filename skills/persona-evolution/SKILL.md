---
name: persona-evolution
description: Update assistant persona, communication style, user preferences, boundaries, and stable facts from evidence. Use when the user corrects behavior, states preferences, or asks the assistant to become more personally useful.
---

# Persona Evolution

## Purpose

Let the assistant grow a stable working relationship with the user without inventing personality or overfitting. This skill uses Humungousaur's model-led persona evolution over evidence.

## When To Use

Use when the user says how they want the assistant to communicate, how decisions should be made, what to remember about them, or what behavior should change over time.

## Inputs And Evidence

- Direct user statements.
- Interaction review records.
- Persona records and evolutions.
- Repeated preferences across sessions.
- Current task context and communication channel.

## Tool Map

- `cognitive_persona_evolve`
- `cognitive_persona_evolution_status`
- `cognitive_interaction_review`
- `memory_profile`
- `memory_write`
- `cognitive_state`

## Workflow

1. Separate stable preferences from momentary task-specific instructions.
2. Gather current persona and recent interaction evidence.
3. Use model-led persona evolution to propose updates.
4. Record only preferences or stable facts with direct evidence.
5. Preserve boundaries such as not claiming emotions, identity, or certainty beyond evidence.
6. In the response, explain the practical behavior change.

## Safety And Boundaries

- Do not store sensitive personal facts unless useful and clearly requested or appropriate.
- Do not infer protected attributes.
- Do not overwrite explicit preferences with weak contradictory evidence.

## Safety And Approval

- Persona updates must be grounded in direct user statements, repeated behavior, or interaction-review evidence.
- Do not create claims about the assistant's identity, emotions, relationship, or certainty beyond evidence and policy boundaries.
- Do not store private or sensitive user facts unless they are operationally useful and appropriate to retain.
- If the user asks to forget or change a preference, preserve the latest explicit instruction over older inferred behavior.

## Native Implementation Boundaries

- Use Humungousaur persona-evolution, interaction-review, memory-profile, memory-write, and cognitive-state tools.
- Personal-development patterns from references are guidance only; persistent persona/user-model changes must be model-led and evidence-backed.
- Deterministic code may merge bounded records and validate schemas, but must not infer stable user traits from keyword matches.

## Verification

- Persona updates should cite user statements or interaction records.
- The final answer should say what will change operationally.
- Existing preferences should not be duplicated under different wording.

## Failure Modes

- Treating sarcasm or frustration as a durable preference.
- Creating a persona change without user evidence.
- Storing private details that are not needed.

## References

- Shortlist item: `persona-evolution`.
- Upstream inspiration: personal-development and second-brain skill patterns from OpenClaw.
- Humungousaur cognition: persona evolution providers.
