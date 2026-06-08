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
- `transcript_summary_create`
- `transcript_summary_inspect`
- `summarize_pdfs`
- `write_note`
- `memory_write`
- `cognitive_commitment_record`
- `tool_search`

## Workflow

1. Determine whether transcription is needed or text is already available.
2. For local audio, transcribe with `local-whisper` by default.
3. Preserve source metadata and transcript provenance.
4. Use `transcript_summary_create` for the local structured artifact: summary, key points, decisions, tasks, risks, quotes, open questions, timestamps, and limitations.
5. Use `transcript_summary_inspect` before reporting completion or passing the artifact to notes/memory tools.
6. Record durable memory or commitments only when supported and desired.

## Safety

- Do not summarize copyrighted media by reproducing long verbatim sections.
- Do not send private audio to cloud transcription without explicit choice.
- Do not run upstream media tools directly as implementation.

## Native Implementation Boundaries

- Use `voice_transcribe` for audio-to-text and `transcript_summary_create` / `transcript_summary_inspect` for structured summary artifacts.
- The native summary tool accepts provided transcripts or allowed local transcript files; audio transcription remains provider-mediated through `voice_transcribe`.
- Use `write_note`, `memory_write`, and `cognitive_commitment_record` only after the summary artifact has been inspected.

## Verification

- Confirm transcript source and provider.
- Inspect the transcript summary artifact and report its path, source, and limitations.
- Check that summary preserves important caveats and speaker uncertainty.
- Verify any saved note or memory entry.

## Failure Modes

- Over-compressing technical content.
- Treating transcript errors as facts.
- Losing timestamps needed for follow-up.

## References

- Shortlist item: `audio-content-summary`.
- Upstream inspiration: Hermes `youtube-content`, `songsee`.
