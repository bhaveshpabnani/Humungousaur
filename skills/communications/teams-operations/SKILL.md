---
name: teams-operations
description: Configure and operate Microsoft Teams webhook or Bot Framework style workflows through Humungousaur's native channel catalog, setup checks, message preparation, and approval-gated sends.
---

# Teams Operations

## Purpose

Use Microsoft Teams as an enterprise communication surface without depending on external reference or external reference runtime code. Humungousaur currently supports Teams catalog/setup and webhook text sends through native channel adapters, with full Bot Framework behavior represented as a trusted-runtime contract.

## When To Use

Use for Teams channel onboarding, Teams webhook sends, meeting follow-ups, Teams-style group messages, enterprise status updates, or diagnosing Teams Gateway readiness.

## Inputs And Evidence

- Teams channel or conversation ID.
- `TEAMS_WEBHOOK_URL` readiness or Bot Framework credential references.
- Meeting summary, follow-up message, or status update draft.
- Channel manifest and doctor output.

## Tool Map

- `channel_manifest`
- `channel_setup_requirements`
- `channel_setup_status`
- `channel_doctor`
- `channel_message_prepare`
- `channel_message_send`
- `meeting-follow-up`
- `message-approval-policy`

## Workflow

1. Read `channel_manifest` for `msteams`.
2. Run `channel_setup_requirements` and confirm whether simple webhook or full bot behavior is intended.
3. Use `channel_doctor` to check `TEAMS_WEBHOOK_URL` for native direct text send readiness.
4. Draft meeting follow-ups or status updates with clear recipients and channel context.
5. Prepare messages first with `channel_message_prepare`.
6. Use `channel_message_send` only after approval and only when the webhook adapter is configured.
7. Mark Bot Framework inbound/listener needs as implementation gaps unless a native trusted runtime is present.

## Native Implementation Boundaries

- Use Humungousaur's `msteams` catalog entry and native webhook sender.
- Do not import external reference Teams plugins or external reference Teams pipeline code.
- Use meeting skills for summarization/follow-up logic, not upstream Teams scripts.

## Safety And Approval

- Teams rooms are external-visible workspaces; always require approval before sending.
- Keep confidential meeting notes out of broad channels unless the user confirms audience.
- Treat Teams webhook URLs as secrets.

## Verification

- `channel_doctor {"channel_id":"msteams"}` should show whether webhook credentials exist.
- Direct delivery is proven only by `channel_message_send` returning `sent`.
- Prepared drafts are proven by outbox message IDs and paths.

## Failure Modes

- Treating a Teams meeting transcript as permission to message everyone.
- Claiming Bot Framework inbound support when only webhook sending is configured.
- Sending a broad update that should have been a private DM or draft.

## References

- Shortlist item: `teams-operations`.
- Channel id: `msteams`.
- Upstream inspiration: external reference Teams channel and external reference meeting patterns as reference only.
