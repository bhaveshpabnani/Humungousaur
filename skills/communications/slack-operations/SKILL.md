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
- `channel_action_prepare`
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

## Workflow

1. Use `channel_setup_requirements` to confirm Slack required fields, required secrets, delivery mode, and listener policy.
2. Save only non-secret setup state, allowlists, group allowlists, and secret references with `channel_setup_save`.
3. Run `channel_setup_status`, `channel_doctor`, and `channel_listener_status` before claiming Slack is ready.
4. Use `channel_integration_smoke` for a non-sending readiness check.
5. Use `channel_webhook_ingest` with a representative Slack Events payload to verify inbound normalization and prepared replies.
6. Use `channel_message_prepare` and `channel_action_prepare` to inspect messages, thread replies, reactions, file-share requests, pins, typing indicators, or read receipts.
7. Use `channel_message_send` only after approval and only when `SLACK_BOT_TOKEN` is configured.

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

Use `channel_action_prepare` for Slack reactions, file-share requests, thread replies, pins, unpins, typing indicators, and read receipts. The prepared action remains local until a trusted adapter executes it.

## Groups And Ambient Rooms

Slack MPIMs route as group chats. Apply group allowlists, mention policy, and ambient-room behavior.

For always-on rooms:

- keep `requireMention` false only for trusted rooms;
- set visible replies to message-tool behavior in policy;
- do not auto-post final text from ambient events.

## Bot Loop Safety

Slack bot-authored events must include structured bot identity such as `sender_is_bot:true`, `bot_id`, or equivalent metadata. Default is block. If allowed, bot-loop protection tracks the bot pair in the channel and suppresses runaway exchanges.

## Safety And Approval

- Require exact Slack channel, DM, or MPIM ID before sending; do not infer targets from display names.
- Treat MPIMs as group chats and apply group policy, mention behavior, and allowlists.
- Use prepared outbox mode for files, pins, reactions, and thread actions unless a trusted adapter has explicit support.
- Never claim a Slack message, reaction, pin, or upload happened until the native result says `sent` or the trusted adapter confirms execution.
- Keep `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET`, and `SLACK_USER_TOKEN` in runtime secrets or encrypted desktop settings, not setup JSON.

## Native Implementation Boundaries

- Humungousaur owns manifest, setup persistence, doctor checks, listener status, webhook normalization, prepared outbox envelopes, dry-run smoke, and approval-gated direct text send contracts.
- Socket Mode event streaming and HTTP signature verification require configured Slack credentials and runtime deployment.
- Prepared actions are local execution contracts until a trusted Slack adapter performs the Slack Web API call.
- Ambient room context is quiet memory/context unless the model explicitly prepares or sends a visible message.

## Troubleshooting

- If direct send is blocked, check `SLACK_BOT_TOKEN`.
- If inbound does not arrive, check Socket Mode app token or HTTP signing secret.
- If channel messages are ignored, check group policy, channel ID allowlist, mention policy, and sender allowlist.
- If file analysis is expected, confirm file scopes and size limits.
- If a reaction or pin is expected, confirm the action outbox item exists before claiming it was executed.

## Verification

- Run `channel_integration_smoke` for `slack`; expect one Slack result, `live_send_performed:false`, prepared outbox ready, and dry-run send ready.
- Run `channel_webhook_ingest` with a Slack event containing `event.channel`, `event.channel_type`, `event.user`, and `event.text`; expect one normalized message and a prepared reply for DM/request events.
- Inspect `channel_outbox` for both a Slack message item and Slack action item after smoke.
- For live send smoke, use an allowlisted Slack test channel or DM, explicit approval, and verify the returned status is `sent`.
