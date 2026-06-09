---
name: apple-reminders
description: Native Humungousaur skill for Apple Reminders. Use when a task calls for apple reminders workflows, readiness checks, artifacts, or approval-gated local/provider actions.
---

# Apple Reminders

This is a Humungousaur-native skill. It is authored inside this repository and uses only Humungousaur-owned tools, approval gates, artifacts, and optional dependency records.

## When To Use

Use this skill when the user asks for apple reminders planning, execution, verification, troubleshooting, or artifact creation inside Humungousaur.

## Tool Map

- `tool_search`
- `tool_describe`
- `capability_surface`
- `write_note`
- `native_security_policy`
- `tool_output_store`
- `apple_reminders_list`
- `apple_reminders_create`
- `apple_reminders_complete_prepare`
- `computer_use`
- `os_apps`
- `os_launch_app`
- `os_observe_ui`
- `os_click_element`
- `os_type_text`
- `os_send_keys`
- `screenshot_capture`
- `credential_file_policy`

## Workflow

1. Clarify the user's concrete apple reminders objective, target environment, credentials already configured, and expected artifact or action.
2. Use `tool_search` or `capability_surface` to find the native Humungousaur tools for the domain before choosing a path.
3. Run safe inspection/readiness steps first and write bounded notes or artifacts under the workspace or data directory.
4. Use macOS app/control tools and screenshots for local Apple app workflows; do not rely on private Apple APIs unless the user explicitly configures an approved bridge.
5. For messages, reminders, notes, or location workflows, prepare approval-gated actions and require user confirmation before sending, deleting, or changing personal data.
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
