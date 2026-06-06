---
name: business-reporting
description: Prepare business reports, executive summaries, KPI narratives, and BI-style findings from structured evidence with charts or tables when native tools support them.
---

# Business Reporting

## Purpose

Turn business data and context into clear reports. This skill combines data analysis, document drafting, visualization, and status-update discipline.

## When To Use

Use for KPI reports, executive summaries, weekly/monthly business reviews, sales/ops/finance reports, and structured decision memos.

## Inputs And Evidence

- Data files, metrics, period, audience, business question, source systems, and desired format.
- Prior reports, charts, and constraints.

## Tool Map

- `read_file`
- `python_interpreter`
- `write_note`
- `data-analysis-notebook`
- `data-visualization`
- `doc-coauthoring`

## Workflow

1. Clarify business question and audience.
2. Inspect data provenance and quality.
3. Compute metrics through native interpreter/tool paths when approved.
4. Write insights with evidence, caveats, and recommendations.
5. Create charts/tables when native tools support them.
6. Verify totals, filters, and time periods.

## Native Implementation Boundaries

- Do not import OpenClaw business-reporting plugins.
- Use Humungousaur-owned analysis/artifact tools.
- External BI connectors need native adapters.

## Safety And Approval

- Business data can be confidential.
- Do not publish or send reports without approval.
- Avoid unsupported causal claims.

## Verification

- Metrics should tie to source rows/files.
- Report assumptions and data gaps.
- Confirm saved artifacts.

## Failure Modes

- Pretty report with wrong numbers.
- Mixing time periods.
- Ignoring missing/null data.

## References

- Shortlist item: `business-reporting`.
