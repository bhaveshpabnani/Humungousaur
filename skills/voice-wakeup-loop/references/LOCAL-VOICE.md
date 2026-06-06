# Local Voice Reference

## Native Path

Humungousaur's native wakeup path is:

1. Wake-word or activation file is produced by a trusted local integration.
2. `humungousaur.integrations.voice_wakeup` reads transcript or audio metadata.
3. `voice_transcribe` uses `local-whisper` by default for audio activations.
4. The interaction harness receives `source: voice_transcript`.
5. Cognition decides response mode and action.
6. `voice_response_prepare` writes speech artifacts or `voice_speak` plays audio.

## Provider Preference

Prefer local-first operation:

- STT: `local-whisper`.
- TTS artifact: Windows SAPI through `system`.
- Cloud speech providers only when explicitly configured and useful.

## Verification Command Shape

Use the complete smoke runner with `--local-voice` when validating the path. Do not treat upstream wake-word repositories as runtime dependencies for Humungousaur skills.
