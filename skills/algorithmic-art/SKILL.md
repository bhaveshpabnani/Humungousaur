---
name: algorithmic-art
description: Create generative art concepts or code-owned sketches using approved local code/artifact tools, with clear output and licensing boundaries.
---

# Algorithmic Art

## Purpose

Create code-driven visuals such as p5/canvas/SVG sketches, generative patterns, and interactive art, using project-owned code rather than imported upstream examples.

## When To Use

Use for generative art, creative coding, visual experiments, procedural patterns, and code-based art assets.

## Inputs And Evidence

- Style, palette, motion/static target, dimensions, output format, and interaction needs.
- Existing app/artifact context.

## Tool Map

- `python_interpreter`
- `web-artifact-builder`
- `browser_live_open`
- `browser_live_screenshot`
- `canvas_a2ui_create`

## Workflow

1. Define visual concept and constraints.
2. Choose local HTML/canvas/SVG/Python artifact path.
3. Generate code-owned art assets.
4. Verify render visually.
5. Refine composition and responsiveness.
6. Report artifact paths and limitations.

## Native Implementation Boundaries

- Do not import Anthropic algorithmic-art or Hermes p5js code.
- Any sketch code must be written in the project/workspace.
- Avoid third-party libraries unless approved.

## Safety And Approval

- Respect copyright and brand constraints.
- Avoid flashing/motion-heavy visuals unless requested.
- Keep outputs local unless sharing is approved.

## Verification

- Screenshot or artifact path proves output.
- Check nonblank render.
- Note static versus interactive behavior.

## Failure Modes

- Unverified blank canvas.
- Generic random noise with no design intent.
- Broken asset paths.

## References

- Shortlist item: `algorithmic-art`.
