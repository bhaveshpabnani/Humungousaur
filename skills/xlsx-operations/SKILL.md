---
name: xlsx-operations
description: Clean, analyze, format, and plan spreadsheet workflows through native file/interpreter paths with explicit support boundaries for Excel artifacts.
---

# XLSX Operations

## Purpose

Support spreadsheet analysis and artifact planning. Humungousaur can use approved Python/interpreter workflows when packages are available; dedicated Excel adapters should be native and tested.

## When To Use

Use for spreadsheet analysis, CSV/XLSX cleaning, formulas, tables, summaries, workbook planning, and Excel tool implementation.

## Inputs And Evidence

- Spreadsheet path, schema, desired calculations, formatting, charts, and output path.
- Data quality constraints and formulas.

## Tool Map

- `read_file`
- `python_interpreter`
- `python_interpreter_artifact`
- `write_note`
- `data-analysis-notebook`
- `data-visualization`

## Workflow

1. Confirm file type and path boundary.
2. Determine whether analysis, cleanup, formatting, or artifact creation is needed.
3. Use approved Python for data inspection when appropriate.
4. Preserve formulas, headers, types, and source rows.
5. Verify outputs through artifact inspection or summaries.
6. Report missing native Excel adapter gaps.

## Native Implementation Boundaries

- Do not import Anthropic XLSX skill code or Hermes spreadsheet scripts.
- Use Humungousaur-owned interpreter/tool paths only.
- Add dedicated spreadsheet tools with schemas/tests when needed.

## Safety And Approval

- Spreadsheets may contain financial or personal data.
- Do not overwrite source workbooks without approval.
- Avoid silently changing formulas.

## Verification

- Validate row/column counts and key formulas.
- Confirm artifact path and generated file status.
- Report any package/tool limitations.

## Failure Modes

- Treating XLSX as plain CSV.
- Breaking formulas or formatting silently.
- Missing hidden sheets or filters.

## References

- Shortlist item: `xlsx-operations`.
