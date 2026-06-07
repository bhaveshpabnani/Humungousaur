---
name: image-generation-workflow
description: Plan image generation or editing workflows with prompts, references, safety constraints, and native/provider-aware execution boundaries.
---

# Image Generation Workflow

## Purpose

Help create or edit images with clear prompts, references, aspect ratios, style constraints, and safety boundaries. Execution depends on available native or approved image-generation tools.

## When To Use

Use for generated images, mockups, illustrations, textures, icons, storyboards, and image-editing plans.

## Inputs And Evidence

- Subject, style, dimensions, references, negative constraints, usage, and provider/tool availability.
- Existing assets or desired output path.

## Tool Map

- `tool_search`
- `capability_surface`
- `media_storyboard_create`
- `media_storyboard_inspect`
- `write_note`
- `frontend-design`
- `brand-guidelines`

## Workflow

1. Define image purpose and usage.
2. Gather reference constraints and safety limits.
3. Draft a precise prompt/spec.
4. Use `media_storyboard_create` for local prompt/storyboard/contact-sheet artifacts when generation is not available or not yet approved.
5. Generate/edit only through approved tools.
6. Use `media_storyboard_inspect` or provider output inspection to verify output path and visual fit.

## Native Implementation Boundaries

- Do not import Hermes ComfyUI or OpenClaw image plugins.
- Image providers require Humungousaur-owned adapters or approved available tools.
- Prompt drafts are not generated artifacts.
- Storyboard artifacts are local visual planning outputs and must be labeled separately from generated images.

## Safety And Approval

- Respect likeness, copyright, and brand rules.
- Avoid unsafe or deceptive imagery.
- Keep private reference images local unless approved.

## Verification

- Artifact path or visual output proves generation.
- Check aspect ratio and intended use.
- Inspect storyboard artifacts when generation is not executed.
- Label prompt-only outputs clearly.

## Failure Modes

- Claiming generation when only prompt was written.
- Overly vague prompt.
- Ignoring asset licensing.

## References

- Shortlist item: `image-generation-workflow`.
