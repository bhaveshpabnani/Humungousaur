---
name: youtube-content-summary
description: Summarize YouTube or video transcript content into notes, tasks, blogs, or threads using provided transcripts, web evidence, or native audio summarization paths.
---

# YouTube Content Summary

## Purpose

Turn video content into useful knowledge without downloading or transcribing through upstream tools. Use provided transcripts, web-visible transcript evidence, or native audio/transcript workflows.

## When To Use

Use for YouTube videos, talks, tutorials, demos, lectures, podcasts with video, and transcript-to-note workflows.

## Inputs And Evidence

- Video URL, title, transcript, audio file, desired summary depth, and output format.
- Source metadata and timestamps when available.

## Tool Map

- `fetch_webpage`
- `browser_live_open`
- `browser_live_observe`
- `audio-content-summary`
- `voice_transcribe`
- `write_note`

## Workflow

1. Determine whether transcript text is available.
2. If only audio/video file is provided, use native transcription where supported.
3. Preserve title, URL, timestamps, and transcript provenance.
4. Summarize into the requested format: notes, tasks, blog, thread, or study guide.
5. Avoid long verbatim reproduction.
6. Save reusable notes when requested.

## Native Implementation Boundaries

- Do not import Hermes YouTube content scripts.
- Do not use unofficial downloaders unless the user explicitly approves and policy allows.
- Add transcript/video adapters natively if needed.

## Safety And Approval

- Respect copyright and platform terms.
- Do not claim full-video analysis if only metadata/transcript excerpt was inspected.
- Treat transcript errors as possible.

## Verification

- State transcript source and whether full transcript was available.
- Include timestamps when provided.
- Note limitations when transcript access failed.

## Failure Modes

- Summarizing from title only.
- Copying long transcript passages.
- Losing technical details through over-compression.

## References

- Shortlist item: `youtube-content-summary`.
