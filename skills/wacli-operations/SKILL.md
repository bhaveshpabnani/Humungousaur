---
name: wacli-operations
description: WhatsApp CLI companion workflow for explicitly requested third-party sends, history sync, and message search.
---

# WhatsApp CLI Companion

## Tool Map

- `external_integrations_status`
- `run_shell_command`
- `channel_manifest`
- `channel_message_prepare`
- `channel_outbox`

Use this skill only when the user explicitly asks to message someone else on WhatsApp or asks to sync/search WhatsApp history through a local CLI.

Do not use this for normal active WhatsApp chats with the assistant. Those go through the Humungousaur channel gateway.

## Setup

1. Check for `wacli`.
2. Authenticate with QR pairing outside the prompt:
   - `wacli auth`
   - `wacli doctor`
3. For history, run:
   - `wacli sync --follow`

## Safety

- Require exact recipient and message text.
- Confirm before sending.
- Use `wacli chats list` to resolve a JID, but do not guess from fuzzy names.
- Keep QR/session state in the CLI store, not in Humungousaur setup JSON.

## Search

```bash
wacli chats list --limit 20 --query "name or number"
wacli messages search "invoice" --limit 20 --chat <jid>
wacli messages search "invoice" --after 2026-01-01 --before 2026-12-31
```

## Backfill

```bash
wacli history backfill --chat <jid> --requests 2 --count 50
```

## Send

Text:

```bash
wacli send text --to "+14155551212" --message "Hello. Are you free at 3pm?"
```

Group:

```bash
wacli send text --to "1234567890-123456789@g.us" --message "Running 5 min late."
```

File:

```bash
wacli send file --to "+14155551212" --file C:\path\agenda.pdf --caption "Agenda"
```
