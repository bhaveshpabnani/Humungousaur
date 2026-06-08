---
name: telegram-operations
description: Configure and operate Telegram bot DMs, groups, topics, markdown-image media conversion, and approval-gated sends.
---

# Telegram Operations

## Tool Map

- `channel_manifest`
- `channel_setup_requirements`
- `channel_setup_save`
- `channel_setup_status`
- `channel_doctor`
- `channel_listener_status`
- `channel_listener_tick`
- `channel_webhook_ingest`
- `channel_message_prepare`
- `channel_action_prepare`
- `channel_message_send`
- `channel_outbox`

Use this skill when Telegram bot setup, Telegram groups, topics, media conversion, or Telegram sends are involved.

## Setup

1. Create a bot with BotFather.
2. Set `TELEGRAM_BOT_TOKEN`.
3. Use numeric chat IDs as `conversation_id`.
4. For supergroups, IDs usually start with `-100`.
5. Save non-secret setup refs with `channel_setup_save`.
6. Run `channel_doctor` for `telegram`.

## Workflow

1. Use `channel_setup_requirements` for Telegram's bot token, numeric chat ID rules, media conversion flag, and listener mode.
2. Save enabled state, default chat ID, allowlists, group allowlists, and secret references with `channel_setup_save`.
3. Run `channel_setup_status`, `channel_doctor`, and `channel_listener_status`.
4. Use `channel_integration_smoke` for prepared envelope and dry-run send readiness.
5. Use `channel_listener_tick` for Telegram long-polling smoke when `TELEGRAM_BOT_TOKEN` is configured.
6. Use `channel_webhook_ingest` for webhook payload smoke when testing a posted update.
7. Use `channel_message_prepare` and `channel_action_prepare` before any visible message, media send, reaction, topic reply, typing indicator, or read receipt.

## Group Rules

For groups:

- Put group chat IDs in group allowlists.
- Put human sender IDs in sender allowlists.
- Do not confuse negative group IDs with user IDs.
- Require mentions by default.
- Disable BotFather privacy mode or make the bot admin only when ambient group messages should be visible.

## Topics

Represent topic-scoped conversations with structured metadata or a conversation id convention supplied by the runtime. Keep topic and base group context isolated.

## Markdown Images

Telegram supports outbound media. Humungousaur mechanically extracts markdown image syntax from prepared messages when the channel manifest says `markdown_image_to_media:true`.

Example text:

```text
Here is the chart: ![chart](https://example.com/chart.png)
```

The prepared envelope should contain a `media` entry with kind `image`.

## Sending

Use `channel_message_prepare` for previews. Use `channel_message_send` only after approval and only when `TELEGRAM_BOT_TOKEN` is configured.

Use `channel_action_prepare` for Telegram reactions, topic/thread replies, media/file-share requests, typing indicators, and read receipts. Keep prepared actions local until the trusted bot adapter executes them.

## Safety And Approval

- Require exact numeric chat IDs; never send based only on display names.
- Treat negative supergroup IDs and user IDs as different target classes.
- Require mentions in groups unless the room is explicitly trusted for ambient context.
- Keep `TELEGRAM_BOT_TOKEN` and webhook secrets in runtime secrets or encrypted desktop settings.
- Do not claim Telegram delivery until `channel_message_send` returns `sent` or the trusted bot runtime reports execution.

## Native Implementation Boundaries

- Humungousaur natively prepares Telegram messages/actions, normalizes webhook and polling updates, tracks listener state, and performs approval-gated Bot API text sends when credentials are present.
- Long polling is available through `channel_listener_tick`; production webhooks still require a reachable public endpoint or tunnel.
- Markdown-image media extraction is represented in prepared envelopes; real media upload depends on the trusted Telegram adapter.
- Topic-specific routing must preserve topic metadata or a runtime-supplied conversation convention.

## Troubleshooting

- No DM response: check token, pairing/allowlist, and bot status.
- No group messages: check group allowlist, mention policy, BotFather privacy, and admin status.
- Direct send blocked: check `TELEGRAM_BOT_TOKEN`.

## Verification

- Run `channel_integration_smoke` for `telegram`; expect one Telegram result, prepared outbox ready, dry-run send ready, and no live send.
- Run `channel_webhook_ingest` with a Telegram update containing `message.chat.id`, `message.from.id`, and `message.text`; expect one normalized inbound message.
- When credentials are present, run `channel_listener_tick` with a small limit and confirm update offsets advance without duplicate replies.
- Inspect `channel_outbox` for Telegram message and action envelopes before claiming any bot-runtime action is available.
