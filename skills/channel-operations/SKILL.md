---
name: channel-operations
description: Concrete operations playbook for configuring, testing, and safely using Humungousaur chat channels.
---

# Channel Operations

## Tool Map

- `channel_catalog`
- `channel_manifest`
- `channel_setup_requirements`
- `channel_setup_save`
- `channel_setup_status`
- `channel_doctor`
- `channel_listener_status`
- `channel_listener_tick`
- `channel_webhook_ingest`
- `channel_message_prepare`
- `channel_message_send`
- `channel_outbox`

Use this skill when the task involves onboarding, diagnosing, or sending through any chat channel.

## First Checks

1. Call `channel_catalog` to see supported channels.
2. Call `channel_manifest` for the exact selected channel.
3. Call `channel_setup_requirements` to read required env vars, fields, direct-send support, and policy defaults.
4. Call `channel_doctor` before sending or declaring setup complete.
5. Call `channel_listener_status` before declaring the agent is listening.

## Setup State

Use `channel_setup_save` for:

- `enabled`
- `conversation_defaults`
- `allowlist`
- `group_allowlist`
- `secret_refs` such as `{"bot_token":"SLACK_BOT_TOKEN"}`
- notes

Do not put raw tokens, app secrets, OAuth refresh tokens, phone auth state, QR session files, or private keys in setup JSON.

## Testing A Channel

For a non-destructive smoke:

1. Prepare a message with `channel_message_prepare`.
2. Inspect `channel_outbox`.
3. For inbound harness smoke, pass an inbound channel message with explicit `requires_response:true`.
4. For webhook smoke, use `channel_webhook_ingest` with a structured provider payload.
5. For Telegram listener smoke, use `channel_listener_tick` after enabling the channel and configuring `TELEGRAM_BOT_TOKEN`.
6. Confirm a prepared reply exists only for non-ambient request messages.
7. For external send smoke, use `channel_message_send` only with approval and a test recipient or room.

## Group And Ambient Behavior

For shared rooms:

- Use allowlists.
- Require mentions by default.
- Enable ambient behavior only when the room should be quiet context.
- Ambient room events should not auto-post final text.
- When visible ambient replies are desired, the model should explicitly use a message tool or `channel_message_send`.

## Bot Loop Behavior

If the inbound payload says the sender is a bot:

- Default behavior is ignore.
- If bot messages are allowed, use bot-loop protection on supported channels.
- Suppress a pair that exceeds its event budget in the configured window.
- Keep loop facts based on structured bot identity fields, not sender display names.

## Delivery Truth

- Prepared outbox means "ready for trusted runtime", not sent.
- Direct send means the Humungousaur adapter called an official API and got a success response.
- Bridge-required channels stay prepared until a trusted local runtime is connected.
- Listener ready means the channel is enabled and either local polling or webhook ingress is available; it does not mean a public tunnel has been configured.
