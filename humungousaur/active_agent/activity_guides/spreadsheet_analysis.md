# Activity Skill Pack: Spreadsheet Analysis

## Summary

Use when the user is importing, cleaning, calculating, validating, charting, or
summarizing tabular data. Optimize for analysis continuity, error detection, and
privacy-preserving metadata.

## Signals

- Spreadsheet, table, data file, formula, pivot, filter, sort, chart, import, or
  export activity.
- Repeated edits to formulas, ranges, sheets, columns, named tables, or validation
  rules.
- Switching between data sources, reference material, charts, and a report or
  presentation.

## Helpful Moments

- Formula errors, refresh failures, inconsistent totals, or repeated recalculation
  loops appear.
- The user returns after a gap and may need the last analysis state.
- Export, chart creation, or summary writing suggests a deliverable boundary.
- The user explicitly asks for analysis, formulas, cleanup, validation, or charts.

## Stay Silent When

- The spreadsheet is only previewed or background-synced.
- Data appears financial, payroll, personal, health, credential, customer, or
  otherwise sensitive and no approval exists.
- Assistance would require reading cell values, headers, sheet names, formulas, or
  imported records without approval.
- The user is entering data continuously without a safe pause.

## Deep Dive Triggers

- Reading workbook contents, cell values, formulas, headers, sheet names, charts,
  imports, or exported files.
- Running calculations, validating totals, creating formulas, producing charts, or
  summarizing findings from data.
- Connecting to external data sources or refreshing private datasets.

## Memory Guidance

- Store redacted workbook/entity hashes, broad data type, safe row/column scale,
  operation categories, validation state, export state, and user-declared goal.
- Remember formula/error categories and final deliverable state without raw data.
- Do not retain cell values, headers, formulas, account names, customer records, or
  exact file names without approval.

## Privacy Notes

- Treat tabular data as sensitive by default.
- Ask before reading values, formulas, or connected data.
- Prefer structural metadata and outcome summaries over raw spreadsheet content.
