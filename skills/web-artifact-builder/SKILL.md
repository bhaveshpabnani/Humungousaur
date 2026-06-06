---
name: web-artifact-builder
description: Build rich HTML/CSS/JS artifacts, prototypes, and interactive demos as local project-owned files with browser verification.
---

# Web Artifact Builder

## Purpose

Create local web artifacts that users can open, inspect, and interact with. Artifacts should be complete enough to demonstrate the idea, not static filler.

## When To Use

Use for one-off HTML prototypes, demos, interactive visualizations, mini tools, and shareable local artifacts.

## Inputs And Evidence

- Desired experience, content, assets, constraints, output path, and target browser.
- Existing files or design references.

## Tool Map

- `write_note`
- `read_file`
- `search_workspace`
- `browser_live_open`
- `browser_live_observe`
- `browser_live_screenshot`
- `canvas_a2ui_create`

## Workflow

1. Define the artifact purpose and first-screen experience.
2. Choose a minimal local structure.
3. Build with repo/native assets and code.
4. Avoid external dependencies unless approved.
5. Open and verify in a browser.
6. Report output path and interaction status.

## Native Implementation Boundaries

- Build project-owned files.
- Do not import Anthropic web-artifact-builder code.
- Do not depend on upstream artifact templates as runtime code.

## Safety And Approval

- Avoid remote scripts that can leak data.
- Keep generated assets inside allowed paths.
- Do not overwrite user files without confirmation.

## Verification

- Browser observation/screenshot proves rendering.
- Validate links and controls.
- Note if an artifact is static or interactive.

## Failure Modes

- Delivering code without testing it.
- Using generic decorative visuals.
- Broken local asset paths.

## References

- Shortlist item: `web-artifact-builder`.
