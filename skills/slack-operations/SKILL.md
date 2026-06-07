---
name: slack-operations
description: Configure and operate Slack as a Humungousaur channel, including Socket Mode, HTTP events, MPIM group policy, files, reactions, and approvals.
---

# Slack Operations

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

Use this skill when Slack setup, diagnosis, inbound events, outbound messages, files, reactions, channels, DMs, or MPIMs are involved.

## Setup

1. Read `channel_manifest` for `slack`.
2. Create a Slack app with the scopes needed for the workflow.
3. Set `SLACK_BOT_TOKEN` for outbound messages.
4. Set `SLACK_APP_TOKEN` for Socket Mode inbound, or `SLACK_SIGNING_SECRET` for HTTP Events API verification.
5. Save non-secret state with `channel_setup_save`.
6. Run `channel_doctor` for `slack`.

## Minimum Scopes

For basic DMs and channels:

- `chat:write`
- `im:read`
- `im:write`
- `im:history`
- `channels:read`
- `channels:history`
- `groups:read`
- `groups:history`
- `app_mentions:read`

For richer behavior:

- `files:read`
- `files:write`
- `reactions:read`
- `reactions:write`
- `pins:read`
- `pins:write`
- `mpim:read`
- `mpim:history`
- `mpim:write`

## Conversation IDs

Use Slack IDs, not display names:

- Public channel: `C...`
- Private channel: `G...`
- DM: `D...`
- MPIM: Slack MPIM id, treated as a group chat.

## Sending

Use `channel_message_prepare` for safe preview. Use `channel_message_send` only after approval when `SLACK_BOT_TOKEN` is configured.

When replying in a thread, include metadata:

```json
{"thread_ts":"1712023032.1234"}
```

## Groups And Ambient Rooms

Slack MPIMs route as group chats. Apply group allowlists, mention policy, and ambient-room behavior.

For always-on rooms:

- keep `requireMention` false only for trusted rooms;
- set visible replies to message-tool behavior in policy;
- do not auto-post final text from ambient events.

## Bot Loop Safety

Slack bot-authored events must include structured bot identity such as `sender_is_bot:true`, `bot_id`, or equivalent metadata. Default is block. If allowed, bot-loop protection tracks the bot pair in the channel and suppresses runaway exchanges.

## Troubleshooting

- If direct send is blocked, check `SLACK_BOT_TOKEN`.
- If inbound does not arrive, check Socket Mode app token or HTTP signing secret.
- If channel messages are ignored, check group policy, channel ID allowlist, mention policy, and sender allowlist.
- If file analysis is expected, confirm file scopes and size limits.
