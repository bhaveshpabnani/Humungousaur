---
name: contact-and-relationship-notes
description: Maintain useful people, contact, preference, relationship, and follow-up notes from explicit evidence while respecting privacy and memory boundaries.
---

# Contact And Relationship Notes

## Purpose

Help the assistant remember useful human context like names, roles, preferences, commitments, and follow-ups. This skill supports a human-like assistant memory without guessing private relationship facts.

## When To Use

Use when the user asks to remember something about a person, prepare for a conversation, follow up with someone, summarize relationship context, or extract contact-related notes from meetings/messages.

## Inputs And Evidence

- Explicit user statements, meeting notes, messages, or contact records.
- Person name, role, organization, preferred channel, timezone, preferences, and follow-up items.
- Sensitivity level and whether the memory should be durable.

## Tool Map

- `memory_write`
- `memory_search`
- `memory_profile`
- `contact_note_create`
- `contact_note_inspect`
- `cognitive_commitment_record`
- `cognitive_trigger_record`
- `write_note`
- `cognitive_interaction_review`

## Workflow

1. Identify whether the fact is durable, useful, and explicitly evidenced.
2. Separate factual contact data from subjective interpretations.
3. Use `contact_note_create` for local evidence-backed contact artifacts with sensitivity, source refs, preferences, follow-ups, and memory boundary.
4. Use `contact_note_inspect` before recording durable memory, commitments, or triggers.
5. Before a conversation, retrieve relevant notes and produce a compact prep brief.
6. Allow correction and forgetting when the user updates or retracts a memory.

## Native Implementation Boundaries

- Use Humungousaur memory and commitment tools.
- Do not import second-brain or CRM plugins from OpenClaw/Hermes.
- Do not scrape contacts from apps unless the user explicitly asks and a native approved tool path exists.
- `contact_note_create` is a local artifact tool; durable memory still requires explicit memory/cognition tool action.

## Safety And Approval

- Avoid storing sensitive personal data unless the user explicitly requests it and it is needed.
- Do not infer emotions, relationship quality, health, politics, or protected traits without direct evidence.
- Do not expose one person's private context to another channel.

## Verification

- Memory records should include evidence or confidence.
- Follow-ups should have commitment/trigger IDs when recorded.
- Inspect contact note artifacts and confirm `prepared_not_memorized` unless durable memory was explicitly recorded.
- If no relevant memory exists, say so rather than inventing context.

## Failure Modes

- Turning a one-time mention into a permanent preference.
- Guessing relationship state.
- Mixing two people with similar names.

## References

- Shortlist item: `contact-and-relationship-notes`.
- Upstream inspiration: OpenClaw second-brain entries as reference only.
