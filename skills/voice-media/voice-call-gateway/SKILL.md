---
name: voice-call-gateway
description: Handle telephony or voice-call channel workflows with strict consent, allowlists, transcription, turn handling, and audited responses. Use when designing or operating phone-call style assistant interactions.
---

# Voice Call Gateway

## Purpose

Represent voice-call capability as a safe Humungousaur channel workflow. OpenClaw voice-call entries are reference evidence only; Humungousaur must use native channel adapters or clearly report missing implementation.

## When To Use

Use when the user asks about phone calls, voice-call channel setup, call transcription, call replies, or live spoken conversation through a telephony provider.

## Inputs And Evidence

- Channel manifest and setup requirements.
- Caller identity, allowlist status, call direction, transcript segments, and consent state.
- STT/TTS readiness.
- Outbound message or speech policy.

## Tool Map

- `channel_catalog`
- `channel_manifest`
- `channel_setup_requirements`
- `channel_doctor`
- `voice_transcribe`
- `voice_response_prepare`
- `channel_message_prepare`

## Workflow

1. Check whether a Humungousaur-native voice-call adapter exists in the channel catalog.
2. If missing, report the native implementation gap and do not pretend OpenClaw voice-call code is available.
3. For supported calls, validate caller allowlist and consent before transcription or response.
4. Route transcript turns through the interaction harness as voice/channel stimuli.
5. Prepare responses as voice artifacts or call-channel messages according to the adapter contract.
6. Audit every external-visible call action.

## Safety

- Phone calls require strict identity, consent, and loop protection.
- Do not record or transcribe calls without permission.
- Do not import OpenClaw telephony plugins directly.

## Native Implementation Boundaries

- Use `channel_catalog`, `channel_manifest`, `channel_setup_requirements`, and `channel_doctor` to prove whether a native call-capable adapter exists.
- Use Humungousaur STT/TTS and channel tools for transcript turns and prepared replies.
- If no native call adapter exists, report the implementation gap and prepare setup/design artifacts only.

## Verification

- Confirm channel manifest supports voice-call behavior.
- Confirm credentials and allowlists through setup/status tools.
- Confirm outbound call speech was prepared or sent according to returned status.

## Failure Modes

- Treating a planned adapter as live support.
- Speaking to unknown callers.
- Failing to distinguish transcript preparation from live call delivery.

## References

- Shortlist item: `voice-call-gateway`.
- Upstream inspiration: OpenClaw voice-call plugin references.
