---
name: google-workspace
description: Plan and operate Gmail, Calendar, Drive, Docs, and Sheets workflows only through native configured adapters or approved browser/manual paths, with clear gap reporting.
---

# Google Workspace

## Purpose

Support Google Workspace as a major personal-assistant surface while keeping integration native. If Humungousaur lacks a Google adapter for a task, provide drafts/setup plans instead of pretending API access.

## When To Use

Use for Gmail, Calendar, Drive, Docs, Sheets, shared files, meeting invites, and Google account workflow planning.

## Inputs And Evidence

- Desired app, account, file/calendar/message target, permissions, and current adapter status.
- Provided email/docs/sheet evidence or browser-visible state.

## Tool Map

- `google_workspace_operation_prepare`
- `api_operation_inspect`
- `gmail_draft_prepare`
- `email_draft_prepare`
- `xlsx_workbook_create`
- `xlsx_workbook_inspect`
- `docx_document_create`
- `docx_document_inspect`
- `tool_search`
- `capability_surface`
- `email-operations`
- `live-browser-testing`
- `doc-coauthoring`
- `xlsx-operations`
- `message-approval-policy`

## Workflow

1. Identify which Google app and action are needed.
2. Use `google_workspace_operation_prepare` for Calendar, Drive, Docs, Sheets, and Gmail operation packets.
3. Use `api_operation_inspect` before reporting any prepared Google operation.
4. Use `gmail_draft_prepare` for Gmail message drafts when no direct Gmail packet is needed.
5. Use DOCX/XLSX native artifact tools for local Docs/Sheets-style work before remote Google upload/share.
6. For visible browser workflows, use observation-first browser tools.
7. For sends/calendar invites/shares/uploads/remote edits, require explicit approval and a configured adapter/browser path.
8. Report exact status: draft, prepared, not_executed, sent, scheduled, shared, uploaded, or gap.

## Native Implementation Boundaries

- Do not import external reference Google Workspace scripts.
- Gmail/Calendar/Drive/Docs/Sheets tools must be Humungousaur-owned adapters.
- OAuth tokens must use secret storage, not skill files.
- Native operation packets are local JSON artifacts and do not execute remote Google API calls.
- Live Google actions need a separate approved adapter or browser-assisted execution path.

## Safety And Approval

- Account data is sensitive.
- Sharing, emailing, inviting, deleting, or editing remote docs requires approval.
- Do not scrape accounts without user intent.

## Verification

- Live actions require native adapter or approved browser evidence.
- Drafts must be labeled unsent.
- Operation packets must show `live_execution_status: not_executed` until a live path proves otherwise.
- Inspect packets for provider, app operation, endpoint, OAuth scopes, approval requirement, and payload shape.
- Setup gaps should name missing adapter/credential.

## Failure Modes

- Claiming inbox/calendar access without a tool.
- Sharing files with wrong recipients.
- Confusing local draft with remote Google document.

## References

- Shortlist item: `google-workspace`.
