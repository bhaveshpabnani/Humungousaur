---
name: speech-operations
description: Operate speech-to-text, text-to-speech, wake-word, voice response, and voice-call flows with Deepgram, ElevenLabs, OpenAI, and local Windows speech.
---

# Speech Operations

## Purpose

Operate the full speech surface through Humungousaur-native providers: speech-to-text, text-to-speech, wake-word response preparation, and voice response artifacts. This skill is the shared voice capability wrapper for local, OpenAI, Deepgram, ElevenLabs, and Windows speech paths.

## When To Use

Use this skill when the task involves STT, TTS, voice wakeup, spoken responses, voice calls, recorded audio, or voice response mode selection.

## Tool Map

- `voice_provider_status`
- `voice_transcribe`
- `voice_response_prepare`
- `voice_speak`
- `voice_responses`

## Inputs And Evidence

- Audio path, transcript text, or wake-word activation payload.
- Requested response mode: `text`, `voice_prepare`, `voice_speak`, or `silent`.
- Provider settings and runtime secrets from the app/API request.
- Voice provider status, transcript output, response artifact path, and playback status.

## Providers

Speech-to-text:

- Deepgram when `DEEPGRAM_API_KEY` is configured.
- OpenAI transcription when `OPENAI_API_KEY` is configured.
- Local/offline providers when installed and exposed by tools.

Text-to-speech:

- ElevenLabs when `ELEVENLABS_API_KEY` or `XI_API_KEY` is configured.
- Windows system speech for local fallback.
- Artifact-only response preparation when playback is not desired.

## Status

Start with `voice_provider_status`.

Check:

- STT configured providers.
- TTS configured providers.
- wake-word availability.
- output paths for prepared audio.

## Workflow

1. Inspect the input modality and response mode before choosing a provider.
2. Call `voice_provider_status` for provider readiness when testing or debugging speech.
3. For audio input, call `voice_transcribe` with the requested provider or the configured local/cloud default.
4. Route transcripts as `source: "voice_transcript"` so cognition decides whether to respond, analyze, observe, or ignore.
5. Use `voice_response_prepare` for audio artifacts and `voice_speak` only when immediate playback is appropriate.
6. Use `voice_responses` to inspect generated responses before claiming voice readiness.

## Harness Behavior

Voice transcript stimuli should use `source:"voice_transcript"`.

Response modes:

- `voice_prepare`: generate a voice response artifact without playback.
- `voice_speak`: generate and play or speak aloud.
- `text`: normal response.
- `silent`: record/analyze without speaking.

## Wake Word

Wake-word events should produce structured stimuli with:

- transcript text;
- source device;
- confidence;
- timestamp;
- response mode;
- whether the user explicitly addressed the assistant.

The cognitive decision provider decides whether to respond, observe, analyze, or ignore.

## Safety

- Do not transcribe private ambient audio unless the user enabled that workflow.
- Avoid speaking secrets aloud.
- For shared spaces, default to `voice_prepare` unless playback is clearly desired.
- For phone calls, use strict allowlists.

## Native Implementation Boundaries

- Use Humungousaur voice tools and provider clients; do not import Hermes, OpenClaw, or other upstream speech implementations directly.
- Treat cloud provider use as configured runtime capability, not as a hardcoded default.
- Report missing keys, voice IDs, local models, or unavailable playback as explicit setup findings.

## Verification

- Confirm provider readiness with `voice_provider_status` for the requested STT/TTS path.
- Confirm `voice_transcribe` returns non-empty transcript text or a provider-specific setup/error result.
- Confirm `voice_response_prepare` or `voice_speak` returns a success status and an audio artifact path when audio is prepared.
- Confirm user-facing responses do not expose raw API keys, full tokens, or sensitive ambient audio.
