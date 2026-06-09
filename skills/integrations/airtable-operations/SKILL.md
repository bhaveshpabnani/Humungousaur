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
- `airtable_operation_prepare`
- `api_operation_inspect`
- `agent-api-integration`
- `python_interpreter`
- `write_note`

## Workflow

1. Determine the explicit Airtable operation: list, create, update, upsert, or delete records.
2. Define the table schema, base ID, table ID/name, filters, records, and upsert key fields.
3. Use `airtable_operation_prepare` to create a local operation artifact with endpoint, method, payload, approval requirement, and `not_executed` status.
4. Use `api_operation_inspect` before reporting the artifact or handing it to a future live adapter.
5. Require approval before mutating records.
6. Verify affected record IDs and fields through a future approved live adapter; a prepared artifact is not a live change.

## Native Implementation Boundaries

- Do not import external reference Airtable scripts.
- Implement Airtable as Humungousaur-owned tools with tests.
- Keep tokens in secret storage.
- The current native adapter prepares and inspects operation artifacts; live Airtable mutation must be added as a separate approval-gated tool.

## Safety And Approval

- Airtable records may be business-critical.
- Updates, deletes, and upserts need approval.
- Avoid broad filters that mutate too many records.

## Verification

- Prepared operations need saved path plus `api_operation_inspect` evidence.
- Record changes need IDs and response evidence.
- Missing adapter status should be explicit.

## Failure Modes

- Upserting duplicates because key fields were unclear.
- Updating the wrong base/table.
- Claiming API integration from a drafted plan.

## References

- Shortlist item: `airtable-operations`.
