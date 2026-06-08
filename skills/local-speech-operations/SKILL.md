---
name: local-speech-operations
description: Use local speech-to-text and text-to-speech providers, especially faster-whisper and Windows SAPI, for privacy-preserving voice workflows. Use when the assistant should avoid Deepgram, ElevenLabs, or other cloud voice services.
---

# Local Speech Operations

## Purpose

Run voice workflows locally whenever practical. This skill covers Humungousaur-native local Whisper transcription, Windows SAPI speech synthesis, and local-first smoke testing.

## When To Use

Use when the user asks why the agent depends on cloud speech, wants offline voice, tests local voice, or needs privacy-preserving speech input/output.

## Inputs And Evidence

- `voice_provider_status` output.
- Audio file path inside allowed read roots.
- Local Whisper model directory and provider environment variables.
- Windows SAPI availability.
- Smoke artifacts from local voice tests.

## Tool Map

- `voice_provider_status`
- `voice_transcribe`
- `voice_response_prepare`
- `voice_speak`
- `system_status`
- `capability_surface`

## Workflow

1. Call `voice_provider_status` and confirm `local-whisper` and `system` TTS readiness.
2. For STT, call `voice_transcribe` with `provider: local-whisper` unless another provider is explicitly requested.
3. For TTS artifacts, call `voice_response_prepare` with `tts_provider: system`.
4. For immediate speech, call `voice_speak` with `provider: system` and avoid playback in shared spaces.
5. Use cloud providers only as explicit alternatives, not as the default implementation.
6. When a local model is missing, report the missing native setup instead of importing upstream skill code.

## Safety

- Do not send private audio to cloud services without user intent.
- Do not write transcripts outside configured data directories.
- Do not speak private content aloud unless the user requested immediate local playback.

## Native Implementation Boundaries

- Use `voice_provider_status`, `voice_transcribe`, `voice_response_prepare`, and `voice_speak` as the native implementation path.
- Do not execute third-party voice scripts from upstream repositories as implementation.
- Treat missing local model files, missing `faster-whisper`, or unavailable Windows SAPI as setup findings, not as permission to silently switch to cloud providers.

## Verification

- A local STT test should produce a transcript or a clear missing-model error.
- A local TTS test should produce a `.wav` artifact with non-zero bytes.
- Complete voice smoke should pass with `--local-voice` before claiming end-to-end readiness.

## Failure Modes

- Confusing installed upstream models with active Humungousaur provider support.
- Claiming offline support when the local model path is absent.
- Speaking sensitive content aloud.

## References

- Shortlist item: `local-speech-operations`.
- Related existing skill: `speech-operations`.
- See [provider reference](references/PROVIDERS.md).
