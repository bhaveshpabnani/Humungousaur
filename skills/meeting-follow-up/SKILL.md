---
name: meeting-follow-up
description: Convert meeting notes or transcripts into follow-up tasks, reminders, emails, channel replies, documents, and status updates with approval gates. Use after meeting transcription or when the user asks what to do next from meeting notes.
---

# Meeting Follow Up

## Purpose

Turn meeting outcomes into concrete next actions without losing approval boundaries. This skill connects meeting evidence to Humungousaur commitments, wakeups, notes, documents, and channel tools.

## When To Use

Use after a meeting summary, call transcript, standup, planning conversation, or when the user asks to send follow-ups or track meeting action items.

## Inputs And Evidence

- Meeting summary or transcript.
- Extracted action items, owners, dates, blockers, and open questions.
- Existing commitments and channel setup status.
- User instructions about which follow-ups to send or record.

## Tool Map

- `cognitive_commitment_record`
- `cognitive_commitment_update`
- `cognitive_trigger_record`
- `channel_message_prepare`
- `write_note`
- `memory_write`
- `voice_response_prepare`

## Workflow

1. Start from verified meeting evidence, not memory alone.
2. Separate internal tracking from external-visible follow-ups.
3. Record tasks or reminders only for explicit action items or user-approved follow-ups.
4. Draft messages with `channel_message_prepare`; do not send without approval and configured channel support.
5. Create notes or documents when the user wants a durable record.
6. End with a clear checklist of recorded, drafted, and still-unconfirmed items.

## Safety And Boundaries

- Do not send messages, emails, or channel replies automatically.
- Do not assign tasks to people unless meeting evidence or user instruction supports it.
- Do not use upstream meeting pipeline code as implementation.

## Verification

- Confirm each follow-up maps to a meeting evidence item.
- Verify commitment IDs, trigger IDs, or outbox entries.
- Mark drafts as not sent unless a send tool returns `sent`.

## Failure Modes

- Treating all meeting discussion as assigned tasks.
- Forgetting to create reminders for explicit due dates.
- Claiming an external message was delivered when only prepared.

## References

- Shortlist item: `meeting-follow-up`.
- Upstream inspiration: Hermes Teams meeting pipeline, Anthropic internal communications.
