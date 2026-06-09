---
name: sms-operations
description: Configure, prepare, and approval-send concise SMS messages through Humungousaur's native Twilio SMS channel adapter and strict phone-number allowlists.
---

# SMS Operations

## Purpose

Use SMS as a minimal, high-signal channel for urgent or simple text communication. Humungousaur's native catalog supports Twilio SMS setup, prepared outbox, and approval-gated direct sends.

## When To Use

Use for SMS onboarding, short outbound messages, phone-number channel diagnosis, urgent reminders, or deciding whether SMS is appropriate instead of chat/email.

## Inputs And Evidence

- E.164 recipient phone number as `conversation_id`.
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER` readiness.
- Exact message text and reason.
- Allowlist or pairing state.

## Tool Map

- `channel_manifest`
- `channel_setup_requirements`
- `channel_setup_status`
- `channel_doctor`
- `channel_message_prepare`
- `channel_message_send`
- `message-approval-policy`

## Workflow

1. Read the `sms` manifest and setup requirements.
2. Confirm the phone number is exact, intended, and allowlisted.
3. Keep SMS text short and avoid secrets, links when unnecessary, and long explanations.
4. Prepare the message first with `channel_message_prepare`.
5. Run `channel_doctor` if direct delivery is requested.
6. Use `channel_message_send` only after approval and configured Twilio credentials.

## Native Implementation Boundaries

- Use the Humungousaur Twilio SMS adapter only.
- Do not import external reference SMS plugins or third-party scripts as runtime implementation.
- MMS/media support must be treated according to the native manifest and adapter result.

## Safety And Approval

- SMS has weak identity guarantees; require strict allowlists.
- Never send auth codes, API keys, private links, or sensitive logs over SMS.
- Do not create conversational loops over SMS.

## Verification

- Missing Twilio env vars should appear in `channel_doctor`.
- Prepared messages have outbox paths.
- Sent messages require `status: sent` from `channel_message_send`.

## Failure Modes

- Sending a long response better suited to email or chat.
- Assuming a phone number belongs to a person without evidence.
- Claiming MMS support when only text was sent.

## References

- Shortlist item: `sms-operations`.
- Channel id: `sms`.
- Runtime source: Humungousaur native channel catalog.
