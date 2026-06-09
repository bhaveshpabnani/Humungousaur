---
name: infographic-design
description: Turn complex information into clear infographic plans or artifacts using verified data, hierarchy, accessible visuals, and native design tools.
---

# Infographic Design

## Purpose

Make complex information scannable through visual hierarchy, data integrity, and concise storytelling.

## When To Use

Use for data summaries, educational graphics, product explainers, reports, and one-page visual narratives.

## Inputs And Evidence

- Data/story, audience, dimensions, brand constraints, and target medium.
- Source files and verified metrics.

## Tool Map

- `data-visualization`
- `business-reporting`
- `infographic_plan_create`
- `infographic_plan_inspect`
- `diagram_artifact_create`
- `canvas_a2ui_create`
- `web-artifact-builder`
- `brand-guidelines`

## Workflow

1. Identify the key message.
2. Verify data and source context.
3. Build hierarchy: title, main number, sections, visual marks, notes.
4. Choose charts/icons/layout that clarify.
5. Use `infographic_plan_create` for a local plan with metrics, sections, visual marks, accessibility notes, and source refs.
6. Use `infographic_plan_inspect` before reporting or turning the plan into a canvas/web artifact.
7. Create a canvas/web artifact or detailed spec when useful.
8. Verify readability and data correctness.

## Native Implementation Boundaries

- Use Humungousaur visualization/canvas/web tools.
- Do not import Hermes infographic scripts.
- Use generated assets only through approved native workflows.
- Native infographic plans must preserve source refs and draft/review/final status.

## Safety And Approval

- Avoid misleading charts.
- Respect brand and data privacy.
- Do not publish without approval.

## Verification

- Check numbers against source.
- Verify artifact path/render.
- Inspect infographic plan artifacts for metric count, section count, and accessibility notes.
- Mark draft versus final.

## Failure Modes

- Decorative graphic with weak evidence.
- Too much text.
- Wrong scale or comparison.

## References

- Shortlist item: `infographic-design`.
