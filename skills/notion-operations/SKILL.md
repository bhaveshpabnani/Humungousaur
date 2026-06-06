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
- `write_note`
- `browser_live_open`
- `browser_live_observe`
- `knowledge-base-builder`

## Workflow

1. Check for native Notion adapter support.
2. If absent, draft content or setup requirements.
3. Define page/database schema before writing records.
4. Use approved browser tools only when the user wants manual UI assistance.
5. Avoid external-visible or shared updates without approval.
6. Verify created/updated content through adapter/browser evidence.

## Native Implementation Boundaries

- Do not import Hermes Notion scripts.
- Any Notion API integration must be Humungousaur-owned with schemas and tests.
- Store tokens only in approved secret locations.

## Safety And Approval

- Notion pages can contain private team data.
- Edits/deletes/shares require approval.
- Do not infer database schema from vague text.

## Verification

- Live writes need adapter/browser proof.
- Draft notes need saved path.
- Setup gaps should be explicit.

## Failure Modes

- Writing to the wrong database.
- Treating a draft as published.
- Missing required Notion properties.

## References

- Shortlist item: `notion-operations`.
