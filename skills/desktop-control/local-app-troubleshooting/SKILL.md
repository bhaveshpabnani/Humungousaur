---
name: local-app-troubleshooting
description: Diagnose local app issues by inspecting windows, app state, browser sessions, logs, system status, screenshots, and recent activity through native tools.
---

# Local App Troubleshooting

## Purpose

Help debug local desktop or browser apps by gathering real evidence: running windows, visible UI, local logs/files, browser state, screenshots, and system readiness.

## When To Use

Use when an app is frozen, hidden, misconfigured, failing tests, showing errors, not opening, not responding, or behaving differently than expected.

## Inputs And Evidence

- App name, window title, error text, expected behavior, and recent actions.
- Window list, UIA observation, screenshot, relevant files/logs, browser session evidence, and system status.
- Reproduction steps and any safe restart/close approval.

## Tool Map

- `system_status`
- `os_windows`
- `active_window`
- `os_observe_ui`
- `screenshot_capture`
- `read_file`
- `search_workspace`
- `browser_live_status`
- `browser_live_observe`

## Workflow

1. Identify whether the issue is desktop UI, browser UI, service, file/config, or environment.
2. Gather current state before attempting fixes.
3. Inspect visible errors, logs, and recent app state.
4. Form a hypothesis from evidence and choose the next low-risk check.
5. Use approval-gated actions for restarts, closing windows, typing, or config changes.
6. Verify the app state after the fix or report the blocker.

## Native Implementation Boundaries

- Use Humungousaur OS, browser, system, and file tools.
- Do not import Windows-use, browser-use, or external reference troubleshooting code.
- Do not replace diagnosis with keyword-based error matching; reason from evidence.

## Safety And Approval

- Do not close unsaved work or restart services without approval.
- Avoid exposing private screen/log data in summaries.
- Keep destructive fixes separate from diagnostic steps.

## Verification

- Current state should be proven by tool output.
- Fixes should have a post-action observation or test.
- If a cause is uncertain, label it as a hypothesis.

## Failure Modes

- Fixing before observing.
- Restarting away useful error evidence.
- Confusing browser failure with backend/service failure.

## References

- Shortlist item: `local-app-troubleshooting`.
- Native source: Humungousaur OS/browser/system/file tools.
