---
name: telephony
description: Native Humungousaur skill for Telephony. Use when a task calls for telephony workflows, readiness checks, artifacts, or approval-gated local/provider actions.
---

# Telephony

This is a Humungousaur-native skill. It is authored inside this repository and uses only Humungousaur-owned tools, approval gates, artifacts, and optional dependency records.

## When To Use

Use this skill when the user asks for telephony planning, execution, verification, troubleshooting, or artifact creation inside Humungousaur.

## Tool Map

- `tool_search`
- `tool_describe`
- `capability_surface`
- `write_note`
- `native_security_policy`
- `tool_output_store`
- `telephony_call_prepare`
- `channel_message_prepare`
- `channel_message_send`
- `shopping_comparison_create`
- `shopping_comparison_inspect`
- `google_workspace_operation_prepare`
- `memory`
- `provider_registry`

## Workflow

1. Clarify the user's concrete telephony objective, target environment, credentials already configured, and expected artifact or action.
2. Use `tool_search` or `capability_surface` to find the native Humungousaur tools for the domain before choosing a path.
3. Run safe inspection/readiness steps first and write bounded notes or artifacts under the workspace or data directory.
4. Prepare drafts, comparisons, finance models, commerce plans, or channel messages as local artifacts before external submission.
5. Keep purchases, sends, telephony, and account actions approval-gated.
6. Summarize what ran, what was skipped, what remains blocked, and the exact files or records created.

## Safety And Boundaries

- Do not import, execute, or vendor upstream assistant code for this skill.
- Do not store raw secrets; store only environment variable names, secret references, or readiness booleans.
- Use approvals for writes, sends, purchases, desktop control, process launches, provider calls, and destructive operations.
- Treat personal data, messages, calendars, reminders, contacts, and location data as sensitive.

## Verification

- Record concrete evidence paths or tool outputs before claiming completion.
- Prefer dry-run or prepared artifacts when credentials, hardware, licenses, or live services are missing.
- If a provider-specific runtime is not configured, report the missing credential or binary by name and stop before live execution.
