---
name: clipboard-operations
description: Read, write, clear, and use clipboard text safely through Humungousaur's approval-gated Windows clipboard tools with redaction and provenance.
---

# Clipboard Operations

## Purpose

Use the clipboard as a sensitive local handoff surface. Clipboard reads and writes must be explicit, approval-gated, and treated as private until proven otherwise.

## When To Use

Use when the user asks to inspect clipboard contents, copy text for an app, paste prepared text, replace clipboard text, or debug clipboard-dependent workflows.

## Inputs And Evidence

- User's intended clipboard action.
- Current active window or target app context.
- Text to write, source of text, and sensitivity.
- Tool result showing read/write status.

## Tool Map

- `os_clipboard_read`
- `os_clipboard_write`
- `os_windows`
- `active_window`
- `message-approval-policy`

## Workflow

1. Confirm whether the task needs read, write, or both.
2. Use clipboard read only after approval; treat content as sensitive.
3. Redact or avoid repeating secrets in responses.
4. Write clipboard text only when the user wants that exact content staged.
5. Verify write status before telling the user it is ready to paste.
6. Use paste or app actions separately and only with the right active window.

## Native Implementation Boundaries

- Use Humungousaur clipboard tools.
- Do not import upstream computer-use clipboard helpers.
- Do not use clipboard as hidden inter-tool memory.

## Safety And Approval

- Clipboard may contain passwords, tokens, private messages, or financial data.
- Never send clipboard contents to channels without explicit approval.
- Do not overwrite useful clipboard content without user intent.

## Verification

- Read/write tool result proves access.
- If text was redacted, say that only a redacted view is shown.
- Verify target app focus before any paste-like follow-up action.

## Failure Modes

- Leaking clipboard secrets into logs or messages.
- Overwriting the clipboard unexpectedly.
- Assuming clipboard text belongs to the current task.

## References

- Shortlist item: `clipboard-operations`.
- Native tools: `os_clipboard_read`, `os_clipboard_write`.
