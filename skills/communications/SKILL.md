---
name: communications
description: Parent skill for email, chat, channel operations, outbound drafts, social posts, message approvals, and communication gateway workflows.
---

# Communications

## Purpose

Use this parent skill when the user wants to read, draft, send, triage, summarize, route, or manage communication through email, chat, social, or channel gateways.

## Hierarchy Reading Rules

1. Identify the communication channel and whether the action is read-only, draft-only, or external-send.
2. Load the channel-specific child when channel semantics or tool contracts matter.
3. Use message approval policy before any outbound, broadcast, destructive, or account-changing action.
4. Keep drafts separate from sent messages unless tool output proves delivery.

## Tool Map

- `channel-gateway-operations`
- `channel-gateway`
- `channel-operations`
- `discord-operations`
- `email-operations`
- `internal-comms-writing`
- `message-approval-policy`
- `signal-operations`
- `slack-gif-creation`
- `slack-operations`
- `sms-operations`
- `social-media-drafting`
- `teams-operations`
- `telegram-operations`
- `whatsapp-operations`

## Child Skill Guide

- Use channel gateway and channel operations for cross-channel setup, doctors, listeners, policies, and routing.
- Use the platform child skill for Slack, Teams, Discord, Telegram, WhatsApp, Signal, SMS, or email-specific reads and writes.
- Use internal comms and social drafting when the core task is writing, tone, status, announcement, or post preparation.
- Use message approval policy before sending, scheduling, deleting, inviting, or changing channel/account state.

## Verification

- Report whether content is drafted, queued, prepared, sent, failed, or blocked.
- Never imply delivery without a channel tool result.
