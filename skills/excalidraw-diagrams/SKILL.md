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

- `canvas_a2ui_create`
- `canvas_a2ui_render`
- `architecture-diagrams`
- `write_note`
- `tool_search`

## Workflow

1. Define the diagram message.
2. Create a simple element/relationship list.
3. Check for native Excalidraw artifact support.
4. If absent, create a canvas/markdown diagram spec.
5. Verify generated artifacts.
6. Keep labels readable and sparse.

## Native Implementation Boundaries

- Do not import Hermes Excalidraw scripts.
- Excalidraw JSON generation must be Humungousaur-owned.
- Use upstream examples only as reference.

## Safety And Approval

- Avoid sensitive architecture disclosure.
- Mark sketches as draft.
- Do not overwrite existing diagrams without approval.

## Verification

- Artifact path or spec note proves output.
- Check element labels and relationships.
- State if Excalidraw-native export is not implemented.

## Failure Modes

- Overcrowded diagram.
- Invalid JSON claimed as Excalidraw-ready.
- Unverified technical flow.

## References

- Shortlist item: `excalidraw-diagrams`.
