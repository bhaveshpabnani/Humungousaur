# Activity Guide: Data Analysis

## Summary
Use this guide when activity suggests the user is exploring datasets, running queries, updating dashboards, analyzing spreadsheets, or preparing analytical findings.

## Signals
- Query, dashboard, notebook, chart, dataset, warehouse, spreadsheet, pivot, or export metadata appears.
- Analysis activity alternates between data tools, notes, docs, and communication surfaces.
- Repeated entity refs point to the same dataset, dashboard, workbook, or query session.

## Helpful Moments
- Prepare a quiet analysis summary, next-step checklist, or validation questions.
- Offer to explain failures, create charts, or draft findings after user approval.
- Ask when the user appears stuck across repeated failed runs.

## Stay Silent When
- Activity is only background refresh or passive dashboard viewing.
- Data may contain private, financial, customer, or production details.
- The evidence is only a single transient query/dashboard event.

## Deep Dive Triggers
- SQL text, result rows, schema details, cell values, dashboard screenshots, and exports require approval.
- Running or modifying queries requires explicit approval.

## Memory Guidance
- Store reusable analysis preferences and safe dataset/dashboard refs only after helpful feedback.
- Do not store raw data, formulas, SQL, rows, or customer facts by default.

## Privacy Notes
- Treat data tooling as sensitive even when only metadata is visible.
- Keep summaries coarse and entity refs hashed.
