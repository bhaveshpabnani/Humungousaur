---
name: telegram-operations
description: Configure and operate Telegram bot DMs, groups, topics, markdown-image media conversion, and approval-gated sends.
---

# Telegram Operations

Use this skill when Telegram bot setup, Telegram groups, topics, media conversion, or Telegram sends are involved.

## Setup

1. Create a bot with BotFather.
2. Set `TELEGRAM_BOT_TOKEN`.
3. Use numeric chat IDs as `conversation_id`.
4. For supergroups, IDs usually start with `-100`.
5. Save non-secret setup refs with `channel_setup_save`.
6. Run `channel_doctor` for `telegram`.

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

## Troubleshooting

- No DM response: check token, pairing/allowlist, and bot status.
- No group messages: check group allowlist, mention policy, BotFather privacy, and admin status.
- Direct send blocked: check `TELEGRAM_BOT_TOKEN`.
