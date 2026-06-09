---
name: bot-loop-protection
description: Prevent bot-to-bot reply loops by detecting bot-authored inbound messages, pair suppression, channel policy, and ambient context rules. Use when handling channels that may receive messages from other assistants or automation.
---

# Bot Loop Protection

## Purpose

Keep assistants from endlessly replying to each other. This skill adapts external reference bot-loop protection concepts to Humungousaur's native channel metadata and policy gates.

## When To Use

Use for Slack, Discord, Telegram, Teams, WebChat, SMS, or any channel where inbound messages may be bot-authored or automation-authored.

## Inputs And Evidence

- Inbound metadata: `bot_authored`, author type, sender ID, message ID, conversation ID, and channel ID.
- Channel manifest loop-protection support.
- Recent messages and outbox entries.
- Group/DM policy.

## Tool Map

- `channel_manifest`
- `channel_catalog`
- `channel_outbox`
- `activity_ingest`
- `cognitive_interaction_review`
- `channel_message_prepare`

## Workflow

1. Inspect inbound metadata before considering message content.
2. If the message is bot-authored and the channel does not allow bot-authored inbound handling, suppress response.
3. For supported bot-authored handling, check pair/session policy and recent outbox to avoid ping-pong.
4. Convert suppressed messages into passive context only when useful and safe.
5. Let model-led cognition review ambiguous cases; do not build hardcoded phrase triggers.
6. Record suppression reason for diagnostics.

## Safety

- Never let two bot accounts repeatedly call each other's message tools.
- Do not bypass bot-loop protection because the text appears urgent.
- Do not import external reference bot-loop code directly.

## Native Implementation Boundaries

- Use native channel metadata, outbox history, and cognitive review to distinguish bot-authored context from user intent.
- Use `activity_ingest` for safe passive context and `channel_message_prepare` only when policy allows a response.
- Treat missing bot metadata from an adapter as a channel implementation gap; do not infer bot identity from vague text patterns.

## Verification

- Suppressed events should show a reason such as bot-authored or pair suppression.
- Prepared replies should not target bot-authored messages unless policy explicitly allows it.
- Outbox should not show repeated alternating bot replies.

## Failure Modes

- Missing bot identity metadata from a channel adapter.
- Treating assistant-generated text as user intent.
- Suppressing all automation messages even when the user configured them as signals.

## References

- Shortlist item: `bot-loop-protection`.
- Upstream inspiration: external reference bot-loop protection.
