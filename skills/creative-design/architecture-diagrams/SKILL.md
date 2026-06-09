---
name: architecture-diagrams
description: Create system, agent, data-flow, sequence, and deployment diagrams from evidence using markdown, Mermaid, canvas, or native artifact tools.
---

# Architecture Diagrams

## Purpose

Make complex systems understandable through accurate diagrams. Diagrams must reflect inspected architecture, not imagined components.

## When To Use

Use for agent architecture, API flows, deployment maps, data pipelines, sequence diagrams, and module relationships.

## Inputs And Evidence

- Source files, docs, services, endpoints, data flows, and user target audience.
- Desired diagram format.

## Tool Map

- `codebase-inspection`
- `read_file`
- `search_workspace`
- `diagram_artifact_create`
- `diagram_artifact_inspect`
- `excalidraw_diagram_create`
- `canvas_a2ui_create`
- `canvas_a2ui_render`
- `write_note`

## Workflow

1. Inspect the actual system path.
2. Choose diagram type: component, sequence, data-flow, deployment, or state.
3. Include only evidenced components or clearly mark proposed ones.
4. Use `diagram_artifact_create` for local Markdown, JSON, and Mermaid sidecars with typed nodes, edges, evidence refs, and status.
5. Use `diagram_artifact_inspect` before reporting the diagram.
6. Use `excalidraw_diagram_create` only when a hand-drawn compatible file is requested.
7. Render/verify artifacts when using canvas.
8. Add a short explanation of key flows and unknowns.

## Native Implementation Boundaries

- Use Humungousaur markdown/canvas/file tools.
- Do not import external reference architecture-diagram scripts.
- Do not make diagrams from stale assumptions.
- Native diagram artifacts must mark `current`, `proposed`, or `draft` status explicitly.

## Safety And Approval

- Architecture may reveal security details; keep sensitive diagrams local unless approved.
- Avoid exposing secrets or internal URLs unnecessarily.

## Verification

- Map diagram nodes to files/docs.
- Verify rendered artifact if generated.
- Inspect diagram artifacts for node count, edge count, evidence refs, and unknowns.
- Mark proposed/future architecture.

## Failure Modes

- Flat diagrams with no data flow.
- Mixing current and desired state.
- Missing ownership boundaries.

## References

- Shortlist item: `architecture-diagrams`.
