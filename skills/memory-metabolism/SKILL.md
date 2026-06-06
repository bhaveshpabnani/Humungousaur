---
name: memory-metabolism
description: Curate assistant memory by retaining useful knowledge, summarizing noisy history, archiving stale records, and forgetting unsupported details. Use when memory feels noisy, outdated, duplicated, or too large.
---

# Memory Metabolism

## Purpose

Keep durable memory useful over time. This skill adapts OpenClaw active-maintenance and memory metabolism ideas into Humungousaur's model-led memory curation path.

## When To Use

Use when the user asks to clean memory, summarize past work, forget outdated details, preserve lessons, or review whether memory is helping current tasks.

## Inputs And Evidence

- `memory_summary` for recent or period-based history.
- `memory_search` for specific topics.
- `cognitive_memory_curate` proposals.
- Current goals, commitments, persona, and skill records.
- User-stated preferences about remembering or forgetting.

## Tool Map

- `memory_summary`
- `memory_search`
- `memory_write`
- `memory_profile`
- `cognitive_memory_curate`
- `cognitive_curation_status`
- `cognitive_state`

## Workflow

1. Define the curation purpose: retain, summarize, archive, forget, deduplicate, or audit.
2. Gather current memory records relevant to that purpose.
3. Use model-led curation for semantic decisions about value and staleness.
4. Preserve exact evidence references for memories that remain.
5. Archive or forget only when evidence is obsolete, unsupported, user-requested, or superseded.
6. Report what changed and what was intentionally left untouched.

## Safety And Boundaries

- Never delete or alter memory solely because it is inconvenient.
- Respect explicit user forget requests while preserving audit requirements.
- Do not infer sensitive stable facts from weak evidence.

## Verification

- Confirm curation status and counts of retained, archived, or summarized records.
- Check that important current commitments remain available.
- Verify that new summaries are grounded in source evidence.

## Failure Modes

- Summarizing away important deadlines.
- Treating one-time events as permanent preferences.
- Deleting evidence before follow-ups are complete.

## References

- Shortlist item: `memory-metabolism`.
- Upstream inspiration: OpenClaw `active-maintenance`.
- Humungousaur cognition: memory curation and event store.
