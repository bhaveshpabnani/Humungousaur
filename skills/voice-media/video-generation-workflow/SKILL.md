---
name: video-generation-workflow
description: Plan short videos, animations, Manim-style explainers, or storyboards with native execution boundaries, scripts, timing, and verification.
---

# Video Generation Workflow

## Purpose

Support video and animation creation from concept to storyboard/spec. Actual rendering requires a native or approved toolchain.

## When To Use

Use for short videos, explainer animations, Manim-style scenes, ASCII/video concepts, UI demos, and storyboard planning.

## Inputs And Evidence

- Topic, duration, audience, style, scenes, narration, assets, and output format.
- Native tool/provider status.

## Tool Map

- `write_note`
- `web-artifact-builder`
- `algorithmic-art`
- `media_storyboard_create`
- `media_storyboard_inspect`
- `voice_response_prepare`
- `tool_search`

## Workflow

1. Define message, audience, and duration.
2. Use `media_storyboard_create` for scene-by-scene storyboard, timing, dimensions, palette, narration/text, accessibility, and licensing constraints.
3. Draft narration and timing.
4. Use `media_storyboard_inspect` before reporting the storyboard or handing it to a renderer.
5. Generate only through approved native tools.
6. Verify output artifact if rendered.

## Native Implementation Boundaries

- Do not import Hermes Manim or ASCII video scripts.
- Rendering pipelines must be Humungousaur-owned or explicitly approved.
- Storyboards are not rendered videos.
- The native storyboard tool creates Markdown/JSON/SVG contact sheets and does not render video files.

## Safety And Approval

- Respect media rights and likeness constraints.
- Avoid deceptive videos.
- Do not upload/share without approval.

## Verification

- Rendered video needs artifact path and playback/inspection.
- Storyboard-only output should be labeled.
- Inspect storyboard artifacts and generated SVG contact sheets.
- Check audio/narration sync if generated.

## Failure Modes

- Claiming rendered output from a script draft.
- Too much content for duration.
- Missing asset licensing.

## References

- Shortlist item: `video-generation-workflow`.
