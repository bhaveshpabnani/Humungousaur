---
name: voice-loop
description: Run wake-word audio through STT, the interaction harness, and TTS response preparation or playback.
---

# Voice Loop

Use this skill when the assistant receives a wake-word activation, recorded audio, voice transcript, or request to respond aloud.

Workflow:

1. Prefer an existing transcript when the activation already contains one.
2. If only audio is present, call `voice_transcribe` with the configured STT provider.
3. Route the transcript into the interaction harness as `voice_transcript`.
4. Let the cognitive decision provider decide whether to respond, analyze, observe, or ignore.
5. Use `voice_response_prepare` for speech artifacts and `voice_speak` only when immediate audible playback is desired.
6. Use `voice_provider_status` before live provider debugging.

Verification:

- Confirm Deepgram is configured before provider-backed STT.
- Confirm ElevenLabs has an API key and either a voice id or explicit voice lookup before provider-backed TTS.
- Do not expose API keys in logs or user-facing responses.
