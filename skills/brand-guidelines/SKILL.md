---
name: brand-guidelines
description: Apply, document, and check brand colors, typography, tone, logos, spacing, and usage rules in product or content work.
---

# Brand Guidelines

## Purpose

Keep outputs aligned with brand identity and usage rules. This skill supports both applying existing guidelines and creating lightweight brand systems.

## When To Use

Use for branded UI, documents, decks, marketing copy, product pages, logos, and visual QA.

## Inputs And Evidence

- Brand guide, logo assets, color tokens, typography, tone, examples, and prohibited uses.
- Target artifact or codebase.

## Tool Map

- `read_file`
- `search_workspace`
- `frontend-design`
- `presentation-design`
- `theme-factory`
- `write_note`

## Workflow

1. Inspect existing brand rules or assets.
2. Identify required colors, type, tone, and layout constraints.
3. Apply rules consistently to the artifact.
4. Document new rules if creating a guide.
5. Verify output against brand examples.
6. Call out missing or conflicting brand direction.

## Native Implementation Boundaries

- Use project/user-provided assets and code.
- Do not import Anthropic brand-guidelines skill code.
- Do not invent official brand rules without labeling them as proposed.

## Safety And Approval

- Do not misuse third-party logos or trademarks.
- Keep confidential brand work private.
- Respect licensing for fonts/assets.

## Verification

- Cite source brand guide or files.
- Check visual output where possible.
- Mark proposed guidelines separately from official ones.

## Failure Modes

- Mixing unofficial and official rules.
- Inconsistent tone across surfaces.
- Using inaccessible brand combinations.

## References

- Shortlist item: `brand-guidelines`.
