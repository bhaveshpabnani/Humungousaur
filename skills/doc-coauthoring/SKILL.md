---
name: doc-coauthoring
description: Co-author specs, proposals, plans, reports, and markdown documents from evidence with clear structure, review loops, and saved drafts.
---

# Doc Coauthoring

## Purpose

Help the user think and write, not just generate text. This skill supports collaborative drafting, restructuring, critique, and polishing of documents from evidence.

## When To Use

Use for specs, proposals, design docs, strategy notes, reports, policies, FAQs, and long-form markdown or text artifacts.

## Inputs And Evidence

- Audience, purpose, constraints, source notes, files, and desired format.
- Existing draft, outline, comments, and review criteria.

## Tool Map

- `read_file`
- `search_workspace`
- `write_note`
- `memory_search`
- `diff_render`

## Workflow

1. Clarify audience, purpose, and required sections.
2. Gather source evidence and mark assumptions.
3. Create or improve an outline before expanding.
4. Draft in the user's desired tone and structure.
5. Review for factual support, gaps, redundancy, and actionability.
6. Save drafts or notes only when requested or useful.

## Native Implementation Boundaries

- Use Humungousaur file, note, memory, and diff tools.
- Do not import Anthropic doc-coauthoring skill code.
- Office-format export requires a native tool or approved interpreter workflow.

## Safety And Approval

- Do not invent facts, citations, or commitments.
- Keep confidential docs out of channels unless approved.
- Preserve user voice and ownership.

## Verification

- Check final doc against stated audience and purpose.
- Cite source files or evidence when relevant.
- Mark drafts as drafts until reviewed.

## Failure Modes

- Over-polishing away user intent.
- Writing generic prose without evidence.
- Saving to the wrong location.

## References

- Shortlist item: `doc-coauthoring`.
