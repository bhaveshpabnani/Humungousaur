---
name: webchat-operations
description: Operate Humungousaur WebChat-style browser conversations through native channel manifests, WebSocket/runtime contracts, outbox preparation, and interaction-harness routing.
---

# WebChat Operations

## Purpose

Treat WebChat as the local/browser-facing user interface channel. This skill supports WebChat setup, event routing, user-visible replies, and debugging without depending on OpenClaw WebChat code.

## When To Use

Use when building or diagnosing the browser chat UI, WebSocket events, local Gateway messages, WebChat onboarding, or user-facing channel previews.

## Inputs And Evidence

- WebChat session ID, user ID, conversation ID, or browser runtime metadata.
- Channel manifest for `webchat`.
- Local UI/server status.
- Outbox entries or interaction harness run IDs.

## Tool Map

- `channel_manifest`
- `channel_setup_status`
- `channel_message_prepare`
- `channel_outbox`
- `activity_ingest`
- `cognitive_interaction_review`
- `browser_live_open`
- `browser_live_observe`

## Workflow

1. Read the WebChat manifest and determine whether the local UI/runtime is active.
2. Route inbound WebChat text as structured channel stimuli with session metadata.
3. Use the same cognitive decision path as voice and other channels.
4. Prepare outbound messages when the runtime consumes outbox envelopes.
5. If testing the UI, use live browser tools to observe the local WebChat page.
6. Keep WebChat delivery claims tied to runtime acknowledgement, not only message preparation.

## Native Implementation Boundaries

- Implement WebChat runtime and WebSocket behavior in Humungousaur-owned code.
- Do not import OpenClaw WebChat UI or Gateway implementation.
- If only the outbox contract exists, say the UI/runtime handoff is pending.

## Safety And Approval

- WebChat may expose local files, logs, and tool results; redact secrets before display.
- Keep external channel sends separate from WebChat local replies.
- Do not assume a WebChat user is authenticated unless the runtime supplies identity evidence.

## Verification

- Confirm manifest and setup status.
- Confirm browser UI state when testing local WebChat.
- Confirm outbox or runtime acknowledgement for any visible reply.

## Failure Modes

- Treating local preview messages as messages sent to Slack/WhatsApp.
- Losing session identity across WebSocket reconnects.
- Displaying sensitive tool logs in the chat panel.

## References

- Shortlist item: `webchat-operations`.
- Channel id: `webchat`.
- Reference inspiration: OpenClaw WebChat as design evidence only.
