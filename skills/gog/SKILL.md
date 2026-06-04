---
name: gog
description: Google Workspace CLI operations for Gmail, Calendar, Drive, Contacts, Sheets, and Docs through a local authenticated `gog` binary.
---

# gog

Use this skill when the user asks for Gmail, Calendar, Drive, Contacts, Sheets, or Docs work and a local `gog` CLI is available.

## Setup

1. Check `gog` with a shell status command such as `gog auth list`.
2. If not configured, the user must complete OAuth setup:
   - `gog auth credentials <client_secret.json>`
   - `gog auth add <account> --services gmail,calendar,drive,contacts,docs,sheets`
3. Set `GOG_ACCOUNT=<email>` to avoid repeating account flags.
4. Prefer `--json` and `--no-input` for machine-readable commands.

## Safety

- Confirm before sending email, creating events, updating sheets, or deleting/clearing data.
- Prefer drafts over sends when wording or recipient identity is unclear.
- Never infer a recipient from a fuzzy name when email address is absent.
- Keep OAuth tokens out of prompts and logs.

## Gmail

Search:

```bash
gog gmail search 'newer_than:7d' --max 10 --json
gog gmail messages search 'in:inbox from:example.com' --max 20 --json
```

Draft:

```bash
gog gmail drafts create --to person@example.com --subject "Subject" --body-file ./message.txt
```

Send:

```bash
gog gmail send --to person@example.com --subject "Subject" --body-file ./message.txt
```

Use `--body-file -` for stdin. Do not rely on escaped `\n` inside `--body`.

## Calendar

List:

```bash
gog calendar events primary --from 2026-06-04T00:00:00 --to 2026-06-05T00:00:00 --json
```

Create:

```bash
gog calendar create primary --summary "Title" --from <iso> --to <iso>
```

Confirm time zone, attendees, and recurrence before creating.

## Drive

Search:

```bash
gog drive search "name contains 'proposal'" --max 20 --json
```

## Sheets

Read:

```bash
gog sheets get <sheetId> "Tab!A1:D10" --json
```

Update:

```bash
gog sheets update <sheetId> "Tab!A1:B2" --values-json '[["A","B"],["1","2"]]' --input USER_ENTERED
```

Append:

```bash
gog sheets append <sheetId> "Tab!A:C" --values-json '[["x","y","z"]]' --insert INSERT_ROWS
```

Clear only after confirmation:

```bash
gog sheets clear <sheetId> "Tab!A2:Z"
```

## Docs

Export:

```bash
gog docs export <docId> --format txt --out ./doc.txt
```

Read:

```bash
gog docs cat <docId>
```
