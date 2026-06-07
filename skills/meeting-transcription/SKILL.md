---
name: meeting-transcription
description: Transcribe meeting audio or provided meeting transcripts, extract participants, topics, decisions, action items, blockers, and follow-ups. Use when the user supplies meeting audio, notes, Teams summaries, or asks to summarize a conversation.
---

# Meeting Transcription

## Purpose

Turn meeting audio or transcript evidence into structured, actionable knowledge. This skill adapts Hermes Teams meeting pipeline and OpenClaw speech/transcription patterns into Humungousaur-native transcription and cognition workflows.

## When To Use

Use for meeting recordings, voice notes, call transcripts, Teams/Zoom notes, standup summaries, or requests to extract decisions and tasks from spoken conversation.

## Inputs And Evidence

- Audio file or transcript text.
- Speaker names, timestamps, agenda, or meeting metadata if supplied.
- Existing commitments or project context.
- User's requested output format.

## Tool Map

- `voice_transcribe`
- `read_file`
- `transcript_summary_create`
- `transcript_summary_inspect`
- `write_note`
- `memory_write`
- `cognitive_commitment_record`
- `cognitive_commitment_review`
- `voice_response_prepare`

## Workflow

1. Decide whether the input is audio, transcript text, or a meeting summary artifact.
2. For audio, use `voice_transcribe` with local STT by default.
3. Preserve transcript path, provider, language, and confidence when available.
4. Use `transcript_summary_create` to preserve topics, decisions, action items, owners, due dates, blockers, unresolved questions, follow-ups, timestamps, and limitations.
5. Use `transcript_summary_inspect` before writing a note, recording commitments, or preparing a spoken summary.
6. Record commitments only when action items are explicit enough and user intent allows it.

## Safety And Boundaries

- Do not transcribe private meeting audio without user permission.
- Do not infer owners or due dates from ambiguous statements.
- Do not depend on Hermes Teams pipeline code; implement meeting workflows through Humungousaur tools.
- Transcript-summary artifacts remain prepared locally until the user asks to share, send, or persist derived commitments.

## Verification

- Confirm transcript source and STT provider.
- Check action items against exact transcript evidence.
- Inspect the transcript summary artifact and verify decision/action/open-question counts.
- Verify saved notes or commitments exist before reporting them.

## Failure Modes

- Confusing a discussion point with a decision.
- Dropping dissent or unresolved questions.
- Recording commitments that the user did not authorize.

## References

- Shortlist item: `meeting-transcription`.
- Upstream inspiration: Hermes `teams-meeting-pipeline`, OpenClaw speech/transcription category.
- See [meeting summary reference](references/MEETING-SUMMARY.md).
