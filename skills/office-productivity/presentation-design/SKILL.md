---
name: presentation-design
description: Improve slide narrative, structure, visuals, speaker notes, and deck quality using evidence, brand rules, and artifact verification.
---

# Presentation Design

## Purpose

Make presentations clearer and more persuasive. This skill focuses on narrative, slide hierarchy, visual rhythm, and audience fit.

## When To Use

Use for improving decks, slide outlines, executive presentations, talks, pitch decks, and report presentations.

## Inputs And Evidence

- Audience, goal, source content, brand rules, slide count, existing deck/draft, and delivery context.

## Tool Map

- `presentation_plan_create`
- `presentation_plan_inspect`
- `pptx_deck_create`
- `pptx_deck_inspect`
- `pptx-operations`
- `doc-coauthoring`
- `brand-guidelines`
- `diagram_artifact_create`
- `infographic_plan_create`
- `data-visualization`
- `write_note`

## Workflow

1. Clarify audience and decision/action desired.
2. Use `presentation_plan_create` to shape audience, goal, desired action, narrative arc, slide sequence, visual intent, speaker notes, evidence refs, and risks.
3. Use `presentation_plan_inspect` before creating or reporting deck work.
4. Reduce slide text and strengthen visual hierarchy.
5. Add speaker notes where helpful.
6. Use `pptx_deck_create` only after the plan is coherent or the user explicitly asks for a deck file.
7. Use `pptx_deck_inspect` after deck generation.
8. Ensure charts/claims are evidence-backed.

## Native Implementation Boundaries

- Use Humungousaur writing/PPTX planning/native artifact tools.
- Do not import Anthropic PPTX/theme code.
- Dedicated deck generation must be native or approved interpreter work.
- Presentation plans are local artifacts and must mark `draft`, `ready_for_review`, or `final` status.
- Generated PPTX decks are not sent, published, or shared unless a separate approved channel/action tool does that.

## Safety And Approval

- Do not fabricate data or logos.
- Keep confidential decks private.
- Respect brand guidelines.

## Verification

- Check narrative flow against audience.
- Inspect presentation plans for slide count, evidence refs, and risks.
- Verify generated artifacts.
- Mark draft if visual QA is incomplete.

## Failure Modes

- Slide dump with no story.
- Overcrowded layouts.
- Unverified numbers.

## References

- Shortlist item: `presentation-design`.
