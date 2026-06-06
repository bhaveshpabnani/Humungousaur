---
name: signal-operations
description: Prepare and diagnose Signal private or group messaging through Humungousaur's native signal-cli bridge contract, strict allowlists, and audited outbox envelopes.
---

# Signal Operations

## Purpose

Represent Signal as a privacy-focused native channel contract. Humungousaur catalogs Signal and can prepare audited outbox messages; actual account delivery requires a trusted local signal-cli bridge.

## When To Use

Use when the user asks about Signal onboarding, Signal private messages, group Signal chats, local bridge requirements, or privacy-preserving channel choices.

## Inputs And Evidence

- Phone number, Signal account reference, or group ID.
- `channel_manifest` for `signal`.
- signal-cli binary availability from `channel_doctor`.
- Allowlist and pairing state.
- Prepared outbox envelope.

## Tool Map

- `channel_manifest`
- `channel_setup_requirements`
- `channel_setup_status`
- `channel_doctor`
- `channel_message_prepare`
- `channel_outbox`
- `message-approval-policy`

## Workflow

1. Read the `signal` manifest and setup requirements.
2. Run `channel_doctor` to check whether `signal-cli` is available.
3. Confirm the exact recipient or group ID and allowlist status.
4. Prepare outbound messages through `channel_message_prepare`.
5. If a trusted local bridge is not active, report that delivery is prepared but not sent.
6. Keep Signal state and account pairing inside the trusted bridge boundary.

## Native Implementation Boundaries

- Humungousaur must own any signal-cli bridge adapter it uses.
- Do not install or call OpenClaw Signal plugins as implementation.
- Do not claim direct delivery until the native bridge returns a sent status.

## Safety And Approval

- Signal messages can be sensitive; never auto-send.
- Do not store Signal private keys or pairing artifacts in skill files or setup JSON.
- Use exact recipients, exact text, and explicit user approval.

## Verification

- `channel_doctor` should reveal binary/setup gaps.
- `channel_outbox` proves prepared envelopes.
- Direct send support remains blocked unless a native bridge is implemented and configured.

## Failure Modes

- Confusing prepared outbox with encrypted delivery.
- Sending to a phone number that was not allowlisted.
- Leaking Signal account metadata into unrelated memory records.

## References

- Shortlist item: `signal-operations`.
- Channel id: `signal`.
- Reference inspiration: OpenClaw Signal channel notes only.
