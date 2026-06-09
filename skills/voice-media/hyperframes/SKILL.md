---
name: hyperframes
description: Native Humungousaur skill for Hyperframes. Use when a task calls for hyperframes workflows, readiness checks, artifacts, or approval-gated local/provider actions.
---

# Hyperframes

This is a Humungousaur-native skill. It is authored inside this repository and uses only Humungousaur-owned tools, approval gates, artifacts, and optional dependency records.

## When To Use

Use this skill when the user asks for hyperframes planning, execution, verification, troubleshooting, or artifact creation inside Humungousaur.

## Tool Map

- `tool_search`
- `tool_describe`
- `capability_surface`
- `write_note`
- `native_security_policy`
- `tool_output_store`
- `hyperframes_composition_prepare`
- `media_storyboard_create`
- `media_storyboard_inspect`
- `sound_spec_create`
- `diagram_artifact_create`
- `image_generate`
- `video_generate`
- `vision_analyze`
- `optional_dependency_installer`

## Workflow

1. Clarify the user's concrete hyperframes objective, target environment, credentials already configured, and expected artifact or action.
2. Use `tool_search` or `capability_surface` to find the native Humungousaur tools for the domain before choosing a path.
3. Run safe inspection/readiness steps first and write bounded notes or artifacts under the workspace or data directory.
4. Create native briefs, storyboards, SVG/contact sheets, sound specs, prompts, or local code artifacts before attempting provider generation.
5. Use optional dependency requests for domain engines such as ComfyUI, Manim, p5.js, TouchDesigner, Blender, or HyperFrames instead of silently installing them.
6. Summarize what ran, what was skipped, what remains blocked, and the exact files or records created.

## Safety And Boundaries

- Do not import, execute, or vendor upstream assistant code for this skill.
- Do not store raw secrets; store only environment variable names, secret references, or readiness booleans.
- Use approvals for writes, sends, purchases, desktop control, process launches, provider calls, and destructive operations.
- Respect licensing and avoid claiming a generated asset exists until a local file or provider result is present.

## Verification

- Record concrete evidence paths or tool outputs before claiming completion.
- Prefer dry-run or prepared artifacts when credentials, hardware, licenses, or live services are missing.
- If a provider-specific runtime is not configured, report the missing credential or binary by name and stop before live execution.
