---
name: gog
description: Google Workspace CLI operations for Gmail, Calendar, Drive, Contacts, Sheets, and Docs through a local authenticated `gog` binary.
---

# gog

## Purpose

Operate a locally authenticated Google Workspace CLI only when the user explicitly wants the `gog` path and approval boundaries are clear. Prefer Humungousaur-native packets and drafts when live CLI execution is not required.

## When To Use

Use this skill when the user asks for Gmail, Calendar, Drive, Contacts, Sheets, or Docs work and a local `gog` CLI is available. For Gmail drafting inside Humungousaur, prefer the native `gmail_draft_prepare` artifact tool first; use `gog` only when configured and approved.

## Tool Map

- `gmail_draft_prepare`
- `email_draft_prepare`
- `xlsx_workbook_create`
- `xlsx_workbook_inspect`
- `run_shell_command`

## Workflow

1. Check `gog` with a shell status command such as `gog auth list`.
2. If not configured, the user must complete OAuth setup:
   - `gog auth credentials <client_secret.json>`
   - `gog auth add <account> --services gmail,calendar,drive,contacts,docs,sheets`
3. Set `GOG_ACCOUNT=<email>` to avoid repeating account flags.
4. Prefer `--json` and `--no-input` for machine-readable commands.
5. Prefer native draft/packet tools before live CLI mutation.
6. Require explicit approval before sends, calendar creation, sheet mutation, deletes, clears, or sharing changes.

## Safety

- Confirm before sending email, creating events, updating sheets, or deleting/clearing data.
- Prefer drafts over sends when wording or recipient identity is unclear.
- Never infer a recipient from a fuzzy name when email address is absent.
- Keep OAuth tokens out of prompts and logs.

## Native Implementation Boundaries

- Use Humungousaur native tools for Gmail drafts, email drafts, XLSX artifacts, and operation packets when possible.
- Use `run_shell_command` for `gog` only as an approved local CLI adapter path, with exact arguments and no hidden shell expansion.
- Treat missing `gog`, missing OAuth, ambiguous account state, or non-JSON output as setup/blocker evidence.

## Gmail

Native draft artifact:

```json
{"tool_name":"gmail_draft_prepare","tool_input":{"to":["person@example.com"],"subject":"Subject","body":"Body text","reason":"Prepare an approval-ready Gmail draft."}}
```

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

## Verification

- Confirm `gog auth list` or an equivalent status command shows the intended account and services before live reads or writes.
- Confirm native draft/packet artifacts exist when using Humungousaur-native preparation.
- Confirm CLI JSON output or a concrete command result before reporting a read/update.
- For sends or mutations, report whether the action was only prepared, blocked, or actually executed.
