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

- `tool_search`
- `capability_surface`
- `email-operations`
- `browser-live-testing`
- `doc-coauthoring`
- `xlsx-operations`
- `message-approval-policy`

## Workflow

1. Identify which Google app and action are needed.
2. Check for native adapter/tool availability.
3. If missing, prepare drafts, setup requirements, or approved browser-assisted steps.
4. For visible browser workflows, use observation-first browser tools.
5. For sends/calendar invites/shares, require explicit approval.
6. Report exact status: draft, prepared, sent, scheduled, or gap.

## Native Implementation Boundaries

- Do not import Hermes Google Workspace scripts.
- Gmail/Calendar/Drive/Docs/Sheets tools must be Humungousaur-owned adapters.
- OAuth tokens must use secret storage, not skill files.

## Safety And Approval

- Account data is sensitive.
- Sharing, emailing, inviting, deleting, or editing remote docs requires approval.
- Do not scrape accounts without user intent.

## Verification

- Live actions require native adapter or approved browser evidence.
- Drafts must be labeled unsent.
- Setup gaps should name missing adapter/credential.

## Failure Modes

- Claiming inbox/calendar access without a tool.
- Sharing files with wrong recipients.
- Confusing local draft with remote Google document.

## References

- Shortlist item: `google-workspace`.
