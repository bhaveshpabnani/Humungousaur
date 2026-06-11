# Activity Skill Pack: Communication Reply

## Summary

Use when the user is reading, drafting, replying to, triaging, or following up on
human communication. Optimize for timing, commitments, and safe draft support.

## Signals

- Message, email, comment, channel, thread, mention, direct-message, or inbox
  activity.
- Draft started, reply sent, thread opened, unread changed, reminder created, or
  follow-up deferred.
- Communication clustered with a document, issue, meeting, decision, or active
  task.

## Helpful Moments

- The user returns to an unresolved thread after a gap.
- A reply draft is started and the user asks for tone, clarity, or context.
- A commitment, question, blocker, or deadline is explicit in safe metadata or
  user-provided context.
- A sent reply or deferral should update task memory.

## Stay Silent When

- Only presence, badge counts, typing indicators, or background sync changed.
- The thread is private, muted, policy-blocked, or outside the user's allowed
  scope.
- Assistance would require reading message bodies, participant identities,
  subjects, attachments, or private channel names without approval.
- The user appears to be rapidly reading or composing without asking.

## Deep Dive Triggers

- Reading message bodies, subjects, participants, attachments, linked documents,
  or prior conversation history.
- Drafting or rewriting a reply from private context.
- Sending, scheduling, reacting to, or otherwise modifying communication.

## Memory Guidance

- Store redacted thread/entity hashes, broad channel type, safe relation to the
  active task, reply state, deferral state, and explicit follow-up commitments.
- Keep tone preferences or recurring collaboration preferences only when the user
  states them or approves inference.
- Do not retain message text, names, emails, subjects, attachments, or private
  channel titles without approval.

## Privacy Notes

- Default to silent triage from metadata.
- Ask before reading, drafting from, or sending communication content.
- Treat people, relationships, and message contents as sensitive.
