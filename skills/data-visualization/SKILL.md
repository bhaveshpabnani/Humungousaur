---
name: data-visualization
description: Create charts, diagrams, canvases, and explanatory visuals from evidence using native interpreter or A2UI canvas tools with verification and provenance.
---

# Data Visualization

## Purpose

Make data and systems easier to understand through appropriate visuals. Use native canvas/interpreter artifacts and verify that visuals match the underlying evidence.

## When To Use

Use for charts, diagrams, architecture flows, KPI visuals, explanatory graphics, and visual summaries.

## Inputs And Evidence

- Data, desired message, audience, chart type constraints, and output format.
- Source files, analysis results, and visual artifact paths.

## Tool Map

- `chart_artifact_create`
- `chart_artifact_inspect`
- `csv_dataset_profile`
- `python_interpreter`
- `python_interpreter_artifact`
- `canvas_a2ui_create`
- `canvas_a2ui_render`
- `write_note`
- `business-reporting`

## Workflow

1. Identify what the visual should communicate.
2. Choose chart/diagram type based on data and audience.
3. Generate SVG charts with `chart_artifact_create` when structured data is available.
4. Label axes, units, sources, and caveats.
5. Inspect generated artifacts with `chart_artifact_inspect`.
6. Explain the finding without overstating certainty.

## Native Implementation Boundaries

- Use Humungousaur interpreter and canvas tools.
- Do not import Hermes diagram or Anthropic canvas skill code.
- Bar/line SVG chart generation and inspection are native; add richer chart generators as native tools if needed.

## Safety And Approval

- Do not visualize confidential data for public use without approval.
- Avoid misleading scales or cherry-picked data.
- Keep generated artifacts inside allowed paths.

## Verification

- Check visual values against data.
- Confirm artifact path and render output.
- State if the visual is a sketch, draft, or verified chart.

## Failure Modes

- Decorative chart that hides the answer.
- Wrong aggregation or axis.
- Claiming artifact exists without checking.

## References

- Shortlist item: `data-visualization`.
