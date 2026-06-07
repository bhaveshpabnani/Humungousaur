---
name: notion-operations
description: Plan, draft, and perform Notion page/database workflows only through native Notion adapters or approved browser paths, with explicit setup and gap reporting.
---

# Notion Operations

## Purpose

Support Notion knowledge and project workflows without relying on upstream plugins. Current work should use drafts and setup planning unless a native Notion adapter is present.

## When To Use

Use for Notion pages, databases, task boards, notes, knowledge bases, and migration plans.

## Inputs And Evidence

- Workspace/page/database target, properties, content, integration token status, and desired action.
- Existing Notion content provided by the user or browser-observed state.

## Tool Map

- `tool_search`
- `capability_surface`
- `notion_operation_prepare`
- `api_operation_inspect`
- `write_note`
- `browser_live_open`
- `browser_live_observe`
- `knowledge-base-builder`

## Workflow

1. Determine the explicit Notion operation: create page, update page, append blocks, query database, or update database schema.
2. Use `notion_operation_prepare` with target IDs, properties, blocks, filters, schema, and reason to create an approval-safe local operation artifact.
3. Use `api_operation_inspect` to verify provider, endpoint, payload shape, approval requirement, and `not_executed` status.
4. Use approved browser tools only when the user wants manual UI assistance.
5. Avoid external-visible or shared updates without approval.
6. Verify created/updated content through a future approved live adapter or browser evidence; a prepared artifact is not a live write.

## Native Implementation Boundaries

- Do not import Hermes Notion scripts.
- Any Notion API integration must be Humungousaur-owned with schemas and tests.
- Store tokens only in approved secret locations.
- The current native adapter prepares and inspects operation artifacts; live Notion mutation must be added as a separate approval-gated tool.

## Safety And Approval

- Notion pages can contain private team data.
- Edits/deletes/shares require approval.
- Do not infer database schema from vague text.

## Verification

- Prepared operations need saved path plus `api_operation_inspect` evidence.
- Live writes need adapter/browser proof.
- Setup gaps should be explicit.

## Failure Modes

- Writing to the wrong database.
- Treating a draft as published.
- Missing required Notion properties.

## References

- Shortlist item: `notion-operations`.
