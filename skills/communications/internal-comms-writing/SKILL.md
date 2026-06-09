---
name: internal-comms-writing
description: Draft clear internal updates, FAQs, incident notes, newsletters, launch announcements, and team communications using evidence, audience context, and approval gates.
---

# Internal Comms Writing

## Purpose

Help the user communicate inside teams with clarity, context, and appropriate tone. This skill adapts internal-communications writing patterns into Humungousaur-native drafting, notes, channel preparation, and approval workflows.

## When To Use

Use for team updates, exec summaries, incident notes, rollout announcements, FAQ drafts, policy notes, newsletters, planning messages, and post-meeting communications.

## Inputs And Evidence

- Audience, channel, purpose, deadline, desired tone, and length.
- Source evidence such as meeting notes, task status, logs, docs, or user bullets.
- Sensitive details that must be included, excluded, or anonymized.
- Delivery channel setup and approval state.

## Tool Map

- `writing_draft_create`
- `writing_draft_inspect`
- `read_file`
- `write_note`
- `memory_write`
- `channel_message_prepare`
- `voice_response_prepare`
- `cognitive_interaction_review`
- `message-approval-policy`

## Workflow

1. Identify audience and purpose before drafting.
2. Separate verified facts from assumptions and open questions.
3. Choose a format: short update, FAQ, incident note, announcement, newsletter, or decision memo.
4. Draft in a concise, direct style with clear next actions.
5. Save a durable unsent draft with `writing_draft_create` when persistence is useful.
6. Prepare a channel message or note when delivery/persistence is requested.
7. Use approval gates before external-visible or team-visible posting.

## Native Implementation Boundaries

- Use Humungousaur document, note, channel, and cognition tools.
- Do not import Anthropic or Hermes communication skill code as implementation.
- Use upstream writing examples only as reference inspiration.

## Safety And Approval

- Do not overstate certainty, blame individuals, or disclose private data.
- Incident and executive comms should preserve uncertainty and known scope.
- User approval is required before posting.

## Verification

- Confirm each claim maps to evidence or is clearly framed as a draft assumption.
- Confirm audience and channel match the user's request.
- Confirm a prepared message is not described as sent.

## Failure Modes

- Marketing-style fluff instead of useful internal signal.
- Missing decisions, owners, or dates.
- Sending broad comms without approval.

## References

- Shortlist item: `internal-comms-writing`.
- Upstream inspiration: Anthropic internal communications skill as reference only.
