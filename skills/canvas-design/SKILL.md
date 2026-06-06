---
name: canvas-design
description: Create static visual plans, node canvases, diagrams, and design boards using native A2UI canvas tools and verified artifacts.
---

# Canvas Design

## Purpose

Use canvas artifacts to organize ideas visually. This supports design boards, system maps, flows, and structured visual plans.

## When To Use

Use for static visual designs, node maps, workflow diagrams, concept boards, and artifact planning.

## Inputs And Evidence

- Canvas title, nodes, edges, annotations, viewport, and desired output.
- Source content and rendered artifact paths.

## Tool Map

- `canvas_a2ui_create`
- `canvas_a2ui_render`
- `data-visualization`
- `architecture-diagrams`
- `write_note`

## Workflow

1. Define the canvas purpose.
2. Convert content into typed nodes and edges.
3. Create the canvas with stable layout.
4. Render SVG/HTML when useful.
5. Verify artifact paths.
6. Iterate based on clarity, not decoration.

## Native Implementation Boundaries

- Use Humungousaur A2UI canvas tools.
- Do not import Anthropic canvas-design code.
- Add richer canvas renderers as native tools only.

## Safety And Approval

- Avoid embedding secrets in diagrams.
- Keep private strategy canvases local unless approved.
- Do not overwrite existing artifacts without confirmation.

## Verification

- Canvas create/render results prove artifacts.
- Check node labels and edge direction.
- Report if visual QA was not performed.

## Failure Modes

- Canvas without a clear message.
- Overcrowded nodes.
- Missing render verification.

## References

- Shortlist item: `canvas-design`.
