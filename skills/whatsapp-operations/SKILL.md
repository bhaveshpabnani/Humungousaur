---
name: whatsapp-operations
description: Configure and operate WhatsApp through Humungousaur's Cloud API sender and prepared QR-bridge contract.
---

# WhatsApp Operations

## Tool Map

- `channel_manifest`
- `channel_setup_requirements`
- `channel_setup_save`
- `channel_setup_status`
- `channel_doctor`
- `channel_listener_status`
- `channel_webhook_ingest`
- `channel_message_prepare`
- `channel_message_send`
- `channel_outbox`

Use this skill when the task involves WhatsApp onboarding, WhatsApp outbound messages, WhatsApp inbound gateway events, or deciding between Cloud API and personal-account bridge modes.

## Modes

Humungousaur owns two WhatsApp paths:

1. Cloud API text sending through `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID`.
2. Prepared outbox envelopes for trusted local QR bridges or personal-account experimentation.

No third-party package is assumed by this skill.

## Cloud API Setup

1. Create a Meta WhatsApp Business app and phone number.
2. Set `WHATSAPP_ACCESS_TOKEN`.
3. Set `WHATSAPP_PHONE_NUMBER_ID`.
4. Use the recipient E.164 phone number as `conversation_id`.
5. Save non-secret setup refs with `channel_setup_save`.
6. Run `channel_doctor` for `whatsapp`.

## Personal QR Bridge Contract

Use this only when the user intentionally wants personal-account behavior.

Rules:

- Pairing state stays in the trusted bridge runtime, not in Humungousaur setup JSON.
- Humungousaur prepares outbox messages until the bridge is installed and trusted.
- Do not broadcast raw WhatsApp inbound content to unrelated plugins unless the user opts in.
- Use strict allowlists and separate test numbers/chats when possible.

## Sending

Use `channel_message_prepare` for review, group sends, media sends, and bridge-required sends.

Use `channel_message_send` only for Cloud API text messages and only after approval.

Never claim a message was delivered unless the result status is `sent`.

## Safety

- Require exact recipient and exact message text.
- Confirm before messaging someone other than the user.
- Do not send secrets, auth codes, or private keys.
- Keep group messaging in prepared mode unless a trusted bridge reports direct support.
