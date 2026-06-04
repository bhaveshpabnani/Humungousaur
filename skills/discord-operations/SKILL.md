---
name: discord-operations
description: Configure and operate Discord bot DMs, guild channels, threads, ambient rooms, reactions, and bot-loop-safe events.
---

# Discord Operations

Use this skill when Discord setup, guild channels, DMs, threads, forum threads, reactions, voice, or bot-authored events are involved.

## Setup

1. Create a Discord application and bot.
2. Enable Message Content Intent when guild messages should be read.
3. Set `DISCORD_BOT_TOKEN`.
4. Use channel, thread, forum thread, or DM channel id as `conversation_id`.
5. Save non-secret setup refs with `channel_setup_save`.
6. Run `channel_doctor` for `discord`.

## Permissions

Minimum practical permissions:

- View Channels
- Send Messages
- Read Message History
- Embed Links
- Attach Files when media is needed
- Add Reactions when acknowledgement or approval reactions are needed
- Send Messages in Threads when thread/forum workflows are needed

## Guild Channels

Use guild/channel allowlists. Require mentions by default. Ambient rooms are appropriate for private trusted servers where the assistant should quietly track context.

## DMs

DMs should use pairing or explicit allowlists. If pairing fails, check that the user allows DMs from server members.

## Bot Loop Safety

Discord bot-authored messages should be ignored unless `allow_bot_message:true` is explicitly present in structured metadata. When allowed, bot-loop protection tracks the bot pair by structured IDs and suppresses runaway exchanges.

## Sending

Use `channel_message_prepare` first. Use `channel_message_send` only after approval and only when `DISCORD_BOT_TOKEN` is configured.

## Troubleshooting

- No guild messages: check Message Content Intent and channel permissions.
- Direct send blocked: check `DISCORD_BOT_TOKEN`.
- Thread send fails: check thread permissions and use the thread id as target.
