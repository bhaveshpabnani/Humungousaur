---
name: docx-operations
description: Plan, inspect, create, or edit Word document workflows through native file/interpreter paths and clearly report missing dedicated DOCX adapters.
---

# DOCX Operations

## Purpose

Support Word document work while respecting current native capability boundaries. Humungousaur can read/write local files and run approved Python analysis; a dedicated DOCX adapter should be implemented natively before claiming full Word automation.

## When To Use

Use for DOCX planning, drafting content for Word, reading provided document text, preparing conversion workflows, or implementing/reviewing a native DOCX tool.

## Inputs And Evidence

- DOCX path, desired edits, source text, formatting requirements, and output path.
- Available Python libraries or future native DOCX tool status.

## Tool Map

- `read_file`
- `write_note`
- `python_interpreter`
- `python_interpreter_artifact`
- `tool_search`
- `capability_surface`

## Workflow

1. Check whether a dedicated native DOCX tool exists.
2. If absent, draft content or plan an approved interpreter-based conversion/edit.
3. Keep document structure explicit: headings, tables, lists, styles, comments.
4. Use approved Python only when package support is available and the user wants artifact work.
5. Verify generated artifacts by file existence and, where possible, rendered/parsed content.
6. Report unsupported operations honestly.

## Native Implementation Boundaries

- Do not import Anthropic DOCX skill code or Hermes document scripts.
- Dedicated DOCX helpers must be Humungousaur-owned, tested, and schema-bound.
- Upstream document skills are reference evidence only.

## Safety And Approval

- Documents may contain private data.
- Do not overwrite source files without explicit instruction.
- Preserve formatting requirements and review output before delivery.

## Verification

- Confirm output path and artifact size/content.
- Note if visual/render verification was not available.
- Validate edits against the requested change list.

## Failure Modes

- Claiming Word formatting was preserved without inspection.
- Corrupting a DOCX by treating it as plain text.
- Hiding missing adapter support.

## References

- Shortlist item: `docx-operations`.
