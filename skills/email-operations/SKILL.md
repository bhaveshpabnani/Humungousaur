---
name: email-operations
description: Read provided email evidence, draft and summarize email, prepare follow-ups, and identify native adapter gaps for Gmail, Outlook, IMAP, SMTP, or local mail workflows.
---

# Email Operations

## Purpose

Support email work as a personal-assistant capability while respecting the current Humungousaur native-tool boundary. Until a Humungousaur-owned mail adapter exists, this skill drafts, summarizes, and plans email work from provided evidence instead of pretending to read or send mail directly.

## When To Use

Use for email drafts, inbox summaries from pasted/exported email, follow-up wording, reply review, mail setup planning, or deciding what native mail tools need to be implemented.

## Inputs And Evidence

- Pasted email, exported `.eml`/text, thread summary, recipient list, subject, and desired tone.
- Existing notes, meeting follow-ups, commitments, or relationship context.
- User approval for any external-visible draft or send.
- Native capability search/status output.

## Tool Map

- `read_file`
- `write_note`
- `email_draft_prepare`
- `gmail_draft_prepare`
- `memory_write`
- `cognitive_commitment_record`
- `cognitive_trigger_record`
- `tool_search`
- `capability_surface`
- `message-approval-policy`

## Workflow

1. Determine whether the user needs summary, reply draft, new email, follow-up plan, or adapter implementation.
2. Use only provided mail evidence unless a native mail adapter is added later.
3. Extract sender, recipients, subject, dates, asks, commitments, deadlines, and risks.
4. Draft concise emails with subject, greeting, body, ask, closing, and optional alternatives.
5. Record commitments or reminders only when explicit and desired.
6. For Gmail-style drafting, use `gmail_draft_prepare` with explicit recipients, subject, body, and reason; verify the draft artifact path.
7. For real sending, report the missing native send adapter or route through a future Humungousaur-owned email send tool with approval.

## Native Implementation Boundaries

- Do not use Hermes Himalaya, Gmail scripts, OpenClaw plugins, or external mail packages as the skill implementation.
- Drafting is natively supported through Humungousaur-owned draft artifact tools. Sending still requires a future Humungousaur-owned Gmail/Outlook/IMAP/SMTP adapter with schemas, approvals, tests, and redaction.
- Do not scrape a mail UI with OS/browser tools unless the user explicitly asks and approves that path.

## Safety And Approval

- External email sends require explicit user approval.
- Never expose confidential thread content in broad summaries.
- Do not invent recipients, commitments, legal claims, or attachments.

## Verification

- A summary should cite the provided email evidence.
- A draft should clearly be marked as draft unless a native send tool returns sent.
- A Gmail draft preparation task should return a local JSON artifact, body file, `send_status: not_sent`, and `approval_required_for_send: true`.
- Adapter gaps should be listed as gaps, not working features.

## Failure Modes

- Claiming inbox access without a native adapter.
- Sending or drafting in the wrong voice for the recipient.
- Missing an important deadline buried in a thread.

## References

- Shortlist item: `email-operations`.
- Upstream inspiration: Hermes Himalaya and Google Workspace references only.
