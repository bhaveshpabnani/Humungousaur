---
name: humanized-writing
description: Revise prose to sound natural, specific, warm, and less generic while preserving facts, user voice, and intent.
---

# Humanized Writing

## Purpose

Make writing feel clear and human without adding fluff or false personality. Preserve the user's intent, facts, and level of formality.

## When To Use

Use for emails, docs, posts, scripts, messages, summaries, and rewriting AI-sounding prose.

## Inputs And Evidence

- Original text, audience, tone, constraints, and must-keep facts.
- User voice examples when available.

## Tool Map

- `writing_draft_create`
- `writing_draft_inspect`
- `doc-coauthoring`
- `internal-comms-writing`
- `social-media-drafting`
- `write_note`
- `memory_profile`

## Workflow

1. Identify audience and desired tone.
2. Preserve factual content and commitments.
3. Remove generic phrasing, filler, and over-explanation.
4. Add concrete transitions and natural rhythm.
5. Offer variants when tone is ambiguous.
6. Save approval-safe rewrite drafts with `writing_draft_create` when the user wants a durable artifact.
7. Check final text against constraints.

## Native Implementation Boundaries

- Use Humungousaur writing draft tools, writing skills, and memory only.
- Do not import external reference humanizer scripts.
- Do not imitate a specific person without user-provided style context and permission.

## Safety And Approval

- Do not change meaning.
- Do not add false emotional claims.
- External-visible messages still require approval before sending.

## Verification

- Compare against must-keep facts.
- Confirm tone target.
- Label drafts as drafts.

## Failure Modes

- Over-casualizing serious content.
- Removing important nuance.
- Adding unsupported warmth or certainty.

## References

- Shortlist item: `humanized-writing`.
