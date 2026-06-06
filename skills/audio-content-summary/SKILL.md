---
name: audio-content-summary
description: Summarize audio, video transcripts, voice notes, and spoken content into useful notes, decisions, tasks, and knowledge records. Use when the user provides audio files, transcript files, or video transcript text.
---

# Audio Content Summary

## Purpose

Turn spoken media into usable knowledge. This adapts Hermes YouTube content and audio analysis inspirations into Humungousaur-native transcription, reading, summarization, memory, and note tools.

## When To Use

Use for podcast notes, voice memos, recorded calls, YouTube transcripts, training videos, lectures, demos, or any transcript-like spoken media.

## Inputs And Evidence

- Audio file path, transcript file, or pasted transcript.
- Source metadata such as title, speaker, URL, date, duration, or language.
- User's desired output: summary, tasks, blog, notes, thread, or memory.

## Tool Map

- `voice_transcribe`
- `read_file`
- `summarize_pdfs`
- `write_note`
- `memory_write`
- `cognitive_commitment_record`
- `tool_search`

## Workflow

1. Determine whether transcription is needed or text is already available.
2. For local audio, transcribe with `local-whisper` by default.
3. Preserve source metadata and transcript provenance.
4. Summarize at the requested level: brief, detailed, action-oriented, or publishable.
5. Extract decisions, tasks, risks, quotes, and open questions when useful.
6. Record durable memory or commitments only when supported and desired.

## Safety And Boundaries

- Do not summarize copyrighted media by reproducing long verbatim sections.
- Do not send private audio to cloud transcription without explicit choice.
- Do not run upstream media tools directly as implementation.

## Verification

- Confirm transcript source and provider.
- Check that summary preserves important caveats and speaker uncertainty.
- Verify any saved note or memory entry.

## Failure Modes

- Over-compressing technical content.
- Treating transcript errors as facts.
- Losing timestamps needed for follow-up.

## References

- Shortlist item: `audio-content-summary`.
- Upstream inspiration: Hermes `youtube-content`, `songsee`.
