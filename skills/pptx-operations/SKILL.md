---
name: pptx-operations
description: Plan, draft, inspect, and create slide-deck workflows through native notes/interpreter paths while marking missing dedicated PPTX adapters.
---

# PPTX Operations

## Purpose

Support slide-deck work as a structured content and artifact workflow. Current Humungousaur support should use notes, approved interpreter artifacts, or future native PPTX tools.

## When To Use

Use for slide outlines, speaker notes, deck narratives, content extraction from provided text, PowerPoint artifact planning, and native PPTX tool design.

## Inputs And Evidence

- Audience, deck goal, slide count, source material, visual style, and output path.
- Existing deck text or requirements.

## Tool Map

- `pptx_deck_create`
- `pptx_deck_inspect`
- `write_note`
- `read_file`
- `search_workspace`
- `python_interpreter`
- `canvas_a2ui_create`
- `presentation-design`

## Workflow

1. Clarify deck objective and audience.
2. Build a slide-by-slide narrative outline.
3. Draft titles, key bullets, visuals, and speaker notes.
4. Use `pptx_deck_create` for structured local PPTX artifacts.
5. Use `pptx_deck_inspect` to verify slide count and text.
6. Verify artifacts and note visual/render limitations.

## Native Implementation Boundaries

- Do not import Anthropic PPTX or Hermes PowerPoint scripts.
- Dedicated PPTX creation/inspection is Humungousaur-owned for structured local artifacts.
- Upstream skills are design references only.

## Safety And Approval

- Do not fabricate data or citations in slides.
- Respect brand and confidentiality.
- Do not overwrite existing decks without approval.

## Verification

- Confirm outline completeness.
- Artifact claims require output path and, ideally, render/inspection.
- Mark drafts as not final when visual QA is absent.

## Failure Modes

- Producing too much text per slide.
- Claiming slide formatting without rendering.
- Hiding missing adapter support.

## References

- Shortlist item: `pptx-operations`.
