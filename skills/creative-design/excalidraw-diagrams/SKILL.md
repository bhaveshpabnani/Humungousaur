---
name: excalidraw-diagrams
description: Draft hand-drawn style diagram specs or Excalidraw-compatible JSON only through native artifact generation, with source evidence and review.
---

# Excalidraw Diagrams

## Purpose

Create hand-drawn style diagrams when that format helps communicate flows or concepts. Current execution should be native artifact creation or a draft spec unless a dedicated Excalidraw tool exists.

## When To Use

Use for informal system maps, whiteboard-style flows, teaching diagrams, and concept sketches.

## Inputs And Evidence

- Diagram purpose, elements, labels, relationships, and target file path.
- Current system evidence if technical.

## Tool Map

- `excalidraw_diagram_create`
- `diagram_artifact_create`
- `diagram_artifact_inspect`
- `canvas_a2ui_create`
- `canvas_a2ui_render`
- `architecture-diagrams`
- `write_note`
- `tool_search`

## Workflow

1. Define the diagram message.
2. Create a simple element/relationship list.
3. Use `excalidraw_diagram_create` for Humungousaur-owned Excalidraw-compatible JSON.
4. Use `diagram_artifact_create` when a Markdown/Mermaid spec is clearer than a sketch file.
5. Verify generated artifacts.
6. Keep labels readable and sparse.

## Native Implementation Boundaries

- Do not import Hermes Excalidraw scripts.
- Excalidraw JSON generation must be Humungousaur-owned.
- Use upstream examples only as reference.
- Mark generated sketches as `draft`, `proposed`, or `current`.

## Safety And Approval

- Avoid sensitive architecture disclosure.
- Mark sketches as draft.
- Do not overwrite existing diagrams without approval.

## Verification

- Artifact path or spec note proves output.
- Excalidraw output must be valid JSON with `type: excalidraw` and generated elements.
- Check element labels and relationships.
- Inspect companion diagram artifacts when produced.

## Failure Modes

- Overcrowded diagram.
- Invalid JSON claimed as Excalidraw-ready.
- Unverified technical flow.

## References

- Shortlist item: `excalidraw-diagrams`.
