---
name: voice-media
description: Parent skill for speech, voice loops, wake word flows, audio, video, image generation, music, YouTube summaries, and media creation or analysis.
---

# Voice Media

## Purpose

Use this parent skill for voice input/output, audio or video workflows, media summaries, image generation, music/sound generation, voice wakeups, and spoken response behavior.

## Hierarchy Reading Rules

1. Identify whether the task is speech, voice loop, media generation, media analysis, or spoken style.
2. Load provider-specific or format-specific child skills before invoking media tools.
3. Keep generation, playback, recording, and external provider calls approval-aware when tool policy requires it.
4. Verify produced or analyzed media with available metadata, transcripts, previews, or artifact checks.

## Tool Map

- `algorithmic-art`
- `audio-content-summary`
- `image-generation-workflow`
- `local-speech-operations`
- `music-and-sound-generation`
- `speech-operations`
- `spoken-response-style`
- `video-generation-workflow`
- `voice-call-gateway`
- `voice-loop`
- `voice-wakeup-loop`
- `youtube-content-summary`

## Child Skill Guide

- Use speech, local speech, spoken style, voice loop, voice wakeup, and voice call gateway for conversational audio workflows.
- Use audio, YouTube, video, image, music, sound, and algorithmic art skills for media analysis or generation.
- Prefer existing transcripts, metadata, and previews before expensive generation or reprocessing.

## Verification

- Confirm artifact paths, durations, transcripts, provider status, and generation settings when available.
- State when media could not be played, rendered, or inspected.
