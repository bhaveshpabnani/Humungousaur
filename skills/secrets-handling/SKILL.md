---
name: secrets-handling
description: Prevent leakage of API keys, tokens, credentials, private keys, personal data, and sensitive clipboard/env/log content across tools and channels.
---

# Secrets Handling

## Purpose

Protect secrets in prompts, logs, files, screenshots, clipboard, shell commands, provider configs, and external messages.

## When To Use

Use when reading env/config/logs, debugging providers, handling clipboard/screenshots, writing docs, sending messages, or integrating APIs.

## Inputs And Evidence

- Secret-bearing source, redaction requirements, destination, and tool risk.
- Provider status or config output.

## Tool Map

- `system_status`
- `voice_provider_status`
- `read_file`
- `os_clipboard_read`
- `screen_captures`
- `message-approval-policy`
- `agent_skill_script_catalog`
- `agent_skill_script_run`

## Native Scripts

- `scripts/redact_text.py`: mechanically redacts likely tokens, private keys, and credential assignments from supplied text. This is a redaction helper, not semantic intent routing.

## Workflow

1. Identify likely secret-bearing sources.
2. Minimize reading and copying.
3. Redact values in responses and notes.
4. Store secrets only in approved env/secret providers.
5. Prevent external-visible sends with secrets.
6. Report presence/missing rather than raw values.

## Native Implementation Boundaries

- Use Humungousaur redaction/status/policy tools.
- Do not import external secret scanners as implementation unless wrapped natively.
- Add scanners as Humungousaur-owned tools if needed.

## Safety And Approval

- Never print full tokens or private keys.
- Treat clipboard and screenshots as sensitive.
- Do not commit secrets.

## Verification

- Check outputs are redacted.
- Confirm secret setup by presence flags, not values.
- Run dependency/security checks when relevant.

## Failure Modes

- Echoing `.env` values.
- Sending logs with tokens to channels.
- Saving secrets in notes.

## References

- Shortlist item: `secrets-handling`.
