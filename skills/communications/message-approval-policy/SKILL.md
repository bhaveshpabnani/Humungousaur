---
name: message-approval-policy
description: Enforce human approval, evidence checks, redaction, and delivery-status honesty for every external-visible message or social/channel action.
---

# Message Approval Policy

## Purpose

Keep the assistant trustworthy when it can speak through real channels. This skill defines the approval and verification discipline for messages, emails, social posts, SMS, chat replies, voice calls, and other external-visible communication.

## When To Use

Use before sending any message to another person, room, phone number, work channel, social platform, email recipient, or call participant. Also use when reviewing prepared outbox messages or diagnosing whether something was sent.

## Inputs And Evidence

- Exact recipient or conversation ID.
- Exact message text and media attachments.
- Channel manifest, setup status, and approval state.
- Reason for sending and supporting evidence.
- Tool result status: prepared, blocked, sent, failed, or dry run.

## Tool Map

- `channel_manifest`
- `channel_setup_status`
- `channel_message_prepare`
- `channel_message_send`
- `channel_outbox`
- `cognitive_interaction_review`
- `tool_describe`
- `write_note`

## Workflow

1. Classify the action as draft, prepare, send, post, speak, or call.
2. Confirm recipient, audience, and message text.
3. Check whether the channel has native direct send support or only prepared outbox support.
4. Redact secrets, private logs, personal data, and unsupported claims.
5. Prepare first when review is needed or credentials/runtime are missing.
6. Send only through an approval-gated native tool and only after explicit approval.
7. Report the exact final status and never blur "prepared" into "sent".

## Native Implementation Boundaries

- Approval policy is enforced through Humungousaur risk levels, approval queue, channel tools, workflow tools, and audit logs.
- Do not use upstream AgentGate/Passport/external reference policy code directly.
- If a new external action tool is added, make it Humungousaur-owned, schema-bound, and approval-gated.

## Safety And Approval

- The user owns final approval for external-visible communication.
- High-risk content includes money, legal, medical, hiring, firing, secrets, reputation-sensitive posts, purchases, and irreversible public messages.
- Keep a durable audit trail for sent or prepared messages.

## Verification

- `channel_message_prepare` proves a draft envelope exists.
- `channel_message_send` status `sent` proves native send success.
- Approval queue records prove human approval where required.
- If status is blocked or missing credentials, report the exact gap.

## Failure Modes

- Auto-sending because the draft looked obvious.
- Misidentifying a group chat as a private DM.
- Saying "I messaged them" when the message is waiting in outbox.

## References

- Shortlist item: `message-approval-policy`.
- Runtime source: Humungousaur approval queue, risk levels, and channel tools.
