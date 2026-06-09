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
- `xlsx_workbook_create`
- `xlsx_workbook_inspect`
- `python_interpreter`
- `python_interpreter_artifact`
- `write_note`
- `data-analysis-notebook`
- `data-visualization`

## Workflow

1. Confirm file type and path boundary.
2. Determine whether analysis, cleanup, formatting, or artifact creation is needed.
3. Use `xlsx_workbook_create` for new Excel artifacts and `xlsx_workbook_inspect` for workbook verification before falling back to approved Python.
4. Preserve formulas, headers, types, and source rows.
5. Verify outputs through artifact inspection or summaries.
6. Report missing native Excel adapter gaps.

## Native Implementation Boundaries

- Do not import Anthropic XLSX skill code or external reference spreadsheet scripts.
- Use Humungousaur-owned interpreter/tool paths only.
- Use the Humungousaur-owned `xlsx_workbook_create` and `xlsx_workbook_inspect` tools for basic workbook creation and verification; add additional native spreadsheet tools with schemas/tests when needed.

## Safety And Approval

- Spreadsheets may contain financial or personal data.
- Do not overwrite source workbooks without approval.
- Avoid silently changing formulas.

## Verification

- Validate row/column counts and key formulas.
- Confirm artifact path and generated file status.
- Confirm workbook inspection reports expected sheet names, dimensions, sample rows, and formulas.
- Report any package/tool limitations.

## Failure Modes

- Treating XLSX as plain CSV.
- Breaking formulas or formatting silently.
- Missing hidden sheets or filters.

## References

- Shortlist item: `xlsx-operations`.
