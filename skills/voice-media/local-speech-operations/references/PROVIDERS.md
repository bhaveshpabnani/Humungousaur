# Local Speech Provider Reference

## Environment Knobs

- `HUMUNGOUSAUR_STT_PROVIDER` or `VOICE_STT_PROVIDER`: default STT provider.
- `HUMUNGOUSAUR_LOCAL_WHISPER_MODEL`: local faster-whisper model name.
- `HUMUNGOUSAUR_LOCAL_WHISPER_MODEL_DIR`: explicit local model directory.
- `HUMUNGOUSAUR_LOCAL_WHISPER_DEVICE`: usually `cpu` on this laptop.
- `HUMUNGOUSAUR_LOCAL_WHISPER_COMPUTE_TYPE`: usually `int8`.
- `HUMUNGOUSAUR_TTS_PROVIDER` or `VOICE_TTS_PROVIDER`: default TTS provider.

## Native Implementations

- `local-whisper`: implemented in `humungousaur.tools.voice.providers`.
- `system`: Windows SAPI implementation in Humungousaur voice provider code.

Do not use external reference/external reference speech scripts as runtime implementations.
