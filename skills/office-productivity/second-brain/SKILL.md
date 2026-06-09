---
name: second-brain
description: Capture, retrieve, curate, and connect personal knowledge through Humungousaur memory, notes, activity, and skill-learning tools with privacy controls.
---

# Second Brain

## Purpose

Help the assistant accumulate useful knowledge like a human assistant: memories, notes, links, preferences, decisions, and lessons, while forgetting or curating stale/noisy material.

## When To Use

Use for personal knowledge capture, retrieval, weekly review, memory hygiene, project context, relationship notes, and durable lessons from completed work.

## Inputs And Evidence

- User-approved facts, notes, activity, source files, decisions, and relevance/retention needs.
- Memory search results and profile summaries.

## Tool Map

- `memory_write`
- `memory_search`
- `memory_summary`
- `memory_profile`
- `cognitive_memory_curate`
- `activity_search`
- `write_note`

## Workflow

1. Decide whether information belongs in memory, notes, tasks, or nowhere.
2. Capture only useful, explicit, evidence-backed facts.
3. Retrieve context before planning when relevant.
4. Periodically curate duplicates, stale items, and sensitive records.
5. Preserve privacy exclusions for activity-derived context.
6. Let model-led review decide importance; do not use keyword buckets.

## Native Implementation Boundaries

- Use Humungousaur memory/activity/cognition tools.
- Do not import external reference second-brain plugins.
- Do not store third-party plugin state as memory without consent.

## Safety And Approval

- Personal memory can be sensitive.
- Avoid protected traits, private inferences, and speculative relationship judgments.
- Support correction and forgetting.

## Verification

- Memory writes return event IDs.
- Retrieval should cite relevant records.
- Curations should report archived/skipped counts.

## Failure Modes

- Remembering too much noise.
- Forgetting active commitments.
- Inferring personal facts without evidence.

## References

- Shortlist item: `second-brain`.
