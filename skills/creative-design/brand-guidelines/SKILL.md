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
- `brand_guidelines_create`
- `brand_guidelines_inspect`
- `frontend-design`
- `presentation-design`
- `theme-factory`
- `write_note`

## Workflow

1. Inspect existing brand rules or assets.
2. Identify required colors, type, tone, and layout constraints.
3. Use `brand_guidelines_create` to create an official/proposed/draft local artifact with colors, typography, tone, usage rules, accessibility notes, and source refs.
4. Use `brand_guidelines_inspect` before applying or reporting rules.
5. Verify output against brand examples.
6. Call out missing or conflicting brand direction.

## Native Implementation Boundaries

- Use project/user-provided assets and code.
- Do not import Anthropic brand-guidelines skill code.
- Do not invent official brand rules without labeling them as proposed.
- Native brand artifacts must mark `official`, `proposed`, or `draft` status explicitly.

## Safety And Approval

- Do not misuse third-party logos or trademarks.
- Keep confidential brand work private.
- Respect licensing for fonts/assets.

## Verification

- Cite source brand guide or files.
- Check visual output where possible.
- Inspect brand-guideline artifacts for status, color count, and accessibility notes.
- Mark proposed guidelines separately from official ones.

## Failure Modes

- Mixing unofficial and official rules.
- Inconsistent tone across surfaces.
- Using inaccessible brand combinations.

## References

- Shortlist item: `brand-guidelines`.
