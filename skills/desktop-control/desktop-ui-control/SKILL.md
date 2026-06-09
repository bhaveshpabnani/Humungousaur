---
name: desktop-ui-control
description: Observe and control native Windows UI through Humungousaur's UIA, window, and app tools with approval-gated element actions and verification after each step.
---

# Desktop UI Control

## Purpose

Control Windows applications safely using native Humungousaur OS tools. The assistant should observe windows and UI Automation elements before acting, then verify after each action.

## When To Use

Use for Windows app workflows, app dialogs, settings panels, installer prompts, local desktop tasks, and native UI troubleshooting.

## Inputs And Evidence

- User goal, target app/window, allowed actions, and expected final state.
- `os_windows` output, UIA selector map, element IDs, active window metadata, screenshots.
- Approval status for UI observation and state-changing actions.

## Tool Map

- `active_window`
- `os_windows`
- `os_observe_ui`
- `os_click_element`
- `os_type_text`
- `os_send_keys`
- `os_scroll_element`
- `os_switch_window`
- `os_window_state`

## Workflow

1. List windows or inspect active window.
2. Observe UIA tree with approval when element actions are needed.
3. Choose targets from observed element IDs, not guessed coordinates.
4. Perform one action at a time.
5. Observe again and compare against expected state.
6. Stop for credentials, destructive prompts, ambiguity, or repeated failed actions.

## Native Implementation Boundaries

- Use Humungousaur `os_*` tools only.
- Do not import Windows-use, Claude computer, OpenAI computer-use, or external reference code as implementation.
- Upstream projects are reference evidence for safe loop design only.

## Safety And Approval

- UI observation and mutating actions are approval-gated because screens may contain private data.
- Do not type secrets unless the user provides them for that exact workflow.
- Destructive app actions require explicit confirmation.

## Verification

- Verify active window and UI state after every action.
- Prefer element actions over coordinates.
- Use screenshots only when needed and store/delete them through native screen tools.

## Failure Modes

- Clicking stale element IDs.
- Typing into the wrong app.
- Continuing after a permission or payment dialog appears.

## References

- Shortlist item: `desktop-ui-control`.
- Native tools: Humungousaur Windows UIA and window tools.
