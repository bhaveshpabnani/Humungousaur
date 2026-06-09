---
name: agent-access-control
description: Apply user, stranger, group, channel, and action access tiers using native channel policy, allowlists, approvals, and cognitive review.
---

# Agent Access Control

## Purpose

Ensure the assistant responds and acts only for authorized people and contexts. Access control covers channel identity, groups, strangers, and high-risk actions.

## When To Use

Use for channel onboarding, group chats, unknown senders, shared rooms, bot messages, external requests, and permission-sensitive tools.

## Inputs And Evidence

- Sender ID, channel ID, conversation type, allowlists, pairing state, and requested action.
- Channel manifest and setup status.

## Tool Map

- `channel_manifest`
- `channel_setup_status`
- `channel_doctor`
- `ambient-room-context`
- `bot-loop-protection`
- `message-approval-policy`

## Workflow

1. Identify actor, channel, and conversation context.
2. Check allowlist/pairing/group policy.
3. Classify action risk and external visibility.
4. Let model-led cognition decide response posture within policy.
5. Suppress or draft rather than act when identity is uncertain.
6. Record setup gaps or policy needs.

## Native Implementation Boundaries

- Use Humungousaur channel policy and approval tools.
- Do not import external reference agent-access-control code.
- Do not make semantic access decisions with keyword matching.

## Safety And Approval

- Unknown users get limited or no action.
- High-risk tools need approval even for trusted users.
- Group contexts require stricter visible-reply policy.

## Verification

- Channel manifest/status proves policy support.
- Prepared/suppressed outcomes should have reasons.
- Send claims require native send status.

## Failure Modes

- Treating display names as identity proof.
- Giving group members DM-level access.
- Ignoring bot-loop signals.

## References

- Shortlist item: `agent-access-control`.
