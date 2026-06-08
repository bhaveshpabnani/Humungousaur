---
name: voice-wakeup-loop
description: Operate wake-word activation from local audio through transcription, interaction harness cognition, agent execution, and voice response preparation. Use when testing or wiring always-on voice activation, wake-word JSON, or recorded activation audio.
---

# Voice Wakeup Loop

## Purpose

Handle the complete wakeup path from stimulus to response without relying on upstream Hermes or OpenClaw runtime code. This skill uses Humungousaur-native voice, activation, cognition, and response tools.

## When To Use

Use when the user asks to test voice wakeup, process activation JSON, transcribe a wakeup recording, debug why the agent did or did not respond aloud, or verify the always-on assistant loop.

## Inputs And Evidence

- Activation JSON with `transcript`, `transcript_path`, `audio_path`, `stt_provider`, language, device, timestamp, or confidence.
- `voice_provider_status` output.
- Local wake-word daemon output or recorded `.wav` files.
- Interaction harness result and prepared voice response artifact.

## Tool Map

- `voice_provider_status`
- `voice_transcribe`
- `voice_response_prepare`
- `voice_speak`
- `cognitive_state`
- `cognitive_interaction_review`
- `memory_write`

## Workflow

1. Inspect the activation payload and prefer an explicit transcript when present.
2. If only audio is present, use `voice_transcribe`; default to `local-whisper` unless the activation or user specifies another configured provider.
3. Route the transcript as a `voice_transcript` stimulus so cognition decides whether to respond, analyze, observe, or ignore.
4. Execute the model-selected plan through normal tools; do not special-case voice text.
5. Prepare a spoken response artifact with `voice_response_prepare`; use `voice_speak` only when immediate playback is appropriate.
6. Review the activation, transcription, run, and voice artifact when debugging.

## Safety

- Do not transcribe ambient audio unless the user enabled that workflow.
- Do not speak secrets aloud.
- Do not bypass cognitive decision or approval policy because input came from voice.

## Native Implementation Boundaries

- Use Humungousaur-native activation, voice, cognition, runtime, and response tools for the wakeup path.
- Do not import Hermes/OpenClaw wake-word code; use Humungousaur-native adapters or the local voice-wakeup module only through approved integration paths.
- Treat wakeup JSON, recorded audio, and transcripts as stimuli with provenance; do not hardcode wake phrase behavior into the skill.

## Verification

- Verify STT provider readiness before live transcription.
- Confirm the transcript is non-empty and tied to the activation file.
- Confirm a run was created only when cognition chose action.
- Confirm prepared audio exists before claiming voice response readiness.

## Failure Modes

- Treating wake-word detection as proof the user requested action.
- Falling back to cloud STT without explicit provider readiness.
- Speaking a long or private final response in a shared environment.

## References

- Shortlist item: `voice-wakeup-loop`.
- Related existing skills: `voice-loop`, `speech-operations`.
- See [local voice reference](references/LOCAL-VOICE.md).
