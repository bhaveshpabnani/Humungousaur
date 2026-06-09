---
name: music-and-sound-generation
description: Plan and draft prompts for music, sound, and audio-generation workflows while keeping execution native, approved, and provider-aware. Use when the user asks for songs, sound effects, music prompts, or audio generation concepts.
---

# Music And Sound Generation

## Purpose

Help the user create music or sound concepts through prompt craft, structure, lyrics, style constraints, and provider planning. external reference AudioCraft, HeartMuLa, and songwriting skills are reference inspiration only; Humungousaur must use native or explicitly configured adapters for execution.

## When To Use

Use when the user asks to write a song, generate a music prompt, create sound effects, prepare lyrics, or plan a local/cloud audio generation workflow.

## Inputs And Evidence

- Genre, mood, tempo, instrumentation, voice, language, duration, and intended use.
- Lyrics, scene description, or reference constraints.
- Available native generation tools or missing capability status.
- Copyright and style constraints.

## Tool Map

- `write_note`
- `sound_spec_create`
- `sound_spec_inspect`
- `memory_write`
- `tool_search`
- `capability_surface`
- `voice_response_prepare`

## Workflow

1. Clarify whether the deliverable is lyrics, prompt, sound design brief, or generated audio.
2. If generated audio is requested, inspect native capability surface first.
3. Use `sound_spec_create` for a reusable local specification with arrangement, lyrics, sound-design notes, prompt, negative prompt, licensing constraints, and provider boundary.
4. Use `sound_spec_inspect` to verify the artifact before reporting completion.
5. If generated audio is requested and no native generator exists, label the output as a prepared spec rather than generated audio.
6. Save prompts or drafts when the user wants reusable assets.

## Safety

- Do not imitate living artists' voices or copyrighted songs too closely.
- Do not execute third-party generation scripts from external reference or external reference directly.
- Do not claim audio was generated unless a native tool actually produced an artifact.

## Native Implementation Boundaries

- Use `sound_spec_create` and `sound_spec_inspect` as the native implementation path for music and sound planning.
- `sound_spec_create` creates local specs only; it does not generate, upload, or publish audio.
- Use `capability_surface` or `tool_search` before claiming an audio generation provider is available.

## Verification

- Check whether the output is a prompt/spec or generated artifact.
- Confirm any artifact path before reporting generated audio.
- Inspect the sound spec and report `prepared_not_generated` when no audio file was rendered.
- Verify style constraints and licensing-sensitive requests are handled safely.

## Failure Modes

- Claiming a provider exists when only reference skills exist.
- Producing vague prompts without arrangement details.
- Copying protected lyrics or artist-identifiable style too directly.

## References

- Shortlist item: `music-and-sound-generation`.
- Upstream inspiration: external reference AudioCraft, HeartMuLa, songwriting-and-ai-music.
