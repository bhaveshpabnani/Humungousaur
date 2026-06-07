---
name: speech-operations
description: Operate speech-to-text, text-to-speech, wake-word, voice response, and voice-call flows with Deepgram, ElevenLabs, OpenAI, and local Windows speech.
---

# Speech Operations

## Tool Map

- `voice_provider_status`
- `voice_transcribe`
- `voice_response_prepare`
- `voice_speak`
- `voice_responses`

Use this skill when the task involves STT, TTS, voice wakeup, spoken responses, voice calls, or audio files.

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
