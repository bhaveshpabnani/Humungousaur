---
name: airtable-operations
description: Plan and perform Airtable record workflows only through native adapters or approved implementation plans, with schemas, filters, upserts, and approval boundaries.
---

# Airtable Operations

## Purpose

Use Airtable as a structured data surface when a native adapter exists or is being designed. The skill helps define tables, filters, records, and upserts safely.

## When To Use

Use for Airtable bases, record lookup, filters, updates, upserts, sync planning, and API wrapper design.

## Inputs And Evidence

- Base/table IDs, fields, filters, records, desired mutation, and auth status.
- Provided CSV/data or API docs.

## Tool Map

- `tool_search`
- `capability_surface`
- `agent-api-integration`
- `python_interpreter`
- `write_note`

## Workflow

1. Check whether a native Airtable adapter exists.
2. Define the table schema and operation contract.
3. For missing adapters, create an implementation plan or draft payloads.
4. For reads/writes through future adapters, validate fields and filters.
5. Require approval before mutating records.
6. Verify affected record IDs and fields.

## Native Implementation Boundaries

- Do not import Hermes Airtable scripts.
- Implement Airtable as Humungousaur-owned tools with tests.
- Keep tokens in secret storage.

## Safety And Approval

- Airtable records may be business-critical.
- Updates, deletes, and upserts need approval.
- Avoid broad filters that mutate too many records.

## Verification

- Record changes need IDs and response evidence.
- Draft payloads are not live changes.
- Missing adapter status should be explicit.

## Failure Modes

- Upserting duplicates because key fields were unclear.
- Updating the wrong base/table.
- Claiming API integration from a drafted plan.

## References

- Shortlist item: `airtable-operations`.
