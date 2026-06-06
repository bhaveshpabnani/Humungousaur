---
name: spoken-response-style
description: Shape assistant replies for speech: concise, natural, privacy-aware, and appropriate for voice_prepare versus voice_speak. Use when the agent must answer aloud or prepare spoken response artifacts.
---

# Spoken Response Style

## Purpose

Make voice replies useful in real life. Spoken responses should be shorter than text, avoid exposing secrets, and preserve user control over playback.

## When To Use

Use when response mode is `voice_prepare` or `voice_speak`, after wake-word activations, during voice-call style workflows, or when generating audio artifacts.

## Inputs And Evidence

- User request and response mode.
- Channel/environment context such as shared room, call, or private workspace.
- Final agent result and any sensitive content.
- TTS provider status and artifact path.

## Tool Map

- `voice_response_prepare`
- `voice_speak`
- `voice_provider_status`
- `cognitive_interaction_review`
- `memory_profile`

## Workflow

1. Decide whether speech should be a summary, acknowledgement, question, or full answer.
2. Keep spoken output concise; move details into text notes or artifacts when needed.
3. Remove secrets, long paths, raw tokens, or sensitive data from speech.
4. Prefer `voice_response_prepare` for artifacts; use `voice_speak` only when immediate playback is intended.
5. If the task is still running or blocked, speak status rather than pretending completion.
6. Verify the voice tool returned success or an artifact path.

## Safety And Boundaries

- Do not speak private or embarrassing information in shared contexts.
- Do not use ElevenLabs or cloud TTS unless configured and chosen.
- Do not bypass text response requirements when the user also needs details.

## Verification

- Confirm response mode and provider.
- Confirm prepared artifact path exists for voice artifacts.
- Ensure spoken text is short enough and does not include secrets.

## Failure Modes

- Reading a full log or code block aloud.
- Speaking a claim that differs from the text result.
- Playing audio when the user requested only preparation.

## References

- Shortlist item: `spoken-response-style`.
- Humungousaur tools: voice response and voice speak.
