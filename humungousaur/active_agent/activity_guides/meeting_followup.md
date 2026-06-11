# Activity Skill Pack: Meeting Follow-Up

## Summary

Use when the user is preparing for, attending, presenting in, leaving, or
following up after a meeting. Optimize for quiet live behavior and safe
post-meeting continuity.

## Signals

- Meeting joined, left, resumed, cancelled, moved, or ended.
- Screen share, presentation, camera, microphone, captions, recording, transcript,
  chat, notes, or whiteboard state changed.
- Calendar, notes, task, document, or message activity clusters around the same
  meeting entity.

## Helpful Moments

- The meeting ends and safe artifacts or follow-up destinations are available.
- The user returns after a meeting gap and may need a concise action summary.
- Prep material, agenda, notes, or tasks are repeatedly opened before a meeting.
- The user explicitly asks for notes, action items, draft follow-up, or handoff.

## Stay Silent When

- The meeting is live and the user has not invoked assistance.
- The meeting surface is only foreground briefly.
- The meeting is private, muted, policy-blocked, or marked no-assistance.
- Assistance would require transcript, recording, participant, chat, title, or
  notes content without approval.

## Deep Dive Triggers

- Reading transcripts, recordings, chat, captions, notes, agendas, attachments,
  participant lists, or related documents.
- Summarizing decisions, extracting action items, or drafting follow-up messages.
- Creating tasks, sending notes, or notifying participants.

## Memory Guidance

- Store meeting/entity hashes, broad meeting phase, safe artifact availability,
  follow-up artifact hashes, and whether the user prepared, attended, presented,
  or followed up.
- Remember explicit action items only from approved content or user-provided
  statements.
- Do not retain participant names, titles, transcripts, chat, recordings, or notes
  without approval.

## Privacy Notes

- Stay quiet during live meetings by default.
- Ask before reading artifacts or contacting people.
- Treat meeting content and attendee context as sensitive.
