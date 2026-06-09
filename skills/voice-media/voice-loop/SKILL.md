---
name: voice-loop
description: Run wake-word audio through STT, the interaction harness, and TTS response preparation or playback.
---

# Voice Loop

## Purpose

Run a complete voice interaction through native Humungousaur components: wake/activation evidence, transcription, cognitive response decision, agent execution, and spoken response preparation or playback.

## When To Use

Use this skill when the assistant receives wake-word activation, recorded audio, voice transcript input, voice response mode, or a request to test end-to-end voice interaction.

## Inputs And Evidence

- Transcript text, activation JSON, or audio file path.
- STT/TTS provider status and runtime secrets.
- Interaction harness decision, run status, tool results, and final response.
- Prepared voice response artifact or playback result.

## Tool Map

- `voice_provider_status`
- `voice_transcribe`
- `conversation_response_prepare`
- `voice_response_prepare`
- `voice_speak`
- `voice_responses`

## Workflow

1. Prefer an existing transcript when the activation already contains one.
2. If only audio is present, call `voice_transcribe` with the configured STT provider.
3. Route the transcript into the interaction harness as `voice_transcript`.
4. Let the cognitive decision provider decide whether to respond, analyze, observe, or ignore.
5. Use `voice_response_prepare` for speech artifacts and `voice_speak` only when immediate audible playback is desired.
6. Use `voice_provider_status` before live provider debugging.

## Safety

- Do not transcribe ambient audio unless the user explicitly enabled wake/listen behavior.
- Do not speak secrets, raw tokens, sensitive notes, or private meeting content aloud.
- Do not bypass normal approvals because input arrived through voice.

## Native Implementation Boundaries

- Use native voice, interaction harness, cognition, and runtime tools only.
- Do not implement voice-loop behavior by importing external reference, external reference, or external assistant runtime loops.
- Treat wake-word activation as a stimulus; cognition still decides whether to respond or observe.

## Verification

- Confirm Deepgram is configured before provider-backed STT.
- Confirm ElevenLabs has an API key and either a voice id or explicit voice lookup before provider-backed TTS.
- Confirm local provider readiness before claiming offline STT/TTS.
- Confirm the transcript, harness decision, run output, and voice artifact/playback status are all present for end-to-end readiness.
- Do not expose API keys in logs or user-facing responses.
