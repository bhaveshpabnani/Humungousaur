---
name: app-launch-and-window-management
description: Find, launch, switch, resize, move, and organize Windows applications and virtual desktops through native Humungousaur OS tools with approval gates.
---

# App Launch And Window Management

## Purpose

Manage the Windows workspace like a practical assistant: launch allowed apps, switch windows, arrange layouts, handle virtual desktops, and verify focus before acting.

## When To Use

Use when the user asks to open an app, bring a window forward, resize/move windows, close/minimize/maximize, organize desktops, or prepare the workstation for a task.

## Inputs And Evidence

- App name, AppID, window title, process metadata, desired layout, and desktop target.
- `os_apps`, `os_windows`, and virtual desktop output.
- Approval state for launching or changing windows.

## Tool Map

- `os_apps`
- `os_launch_app`
- `open_app`
- `os_windows`
- `os_switch_window`
- `os_resize_window`
- `os_window_state`
- `os_virtual_desktops`
- `os_move_window_to_desktop`
- `os_virtual_desktop_action`

## Workflow

1. Discover apps/windows before launching or switching.
2. Use exact app names, AppIDs, or window IDs from native observations.
3. Launch only allowed apps and verify the new window appears.
4. Switch, move, resize, or change window state one step at a time.
5. Use virtual desktop actions only when the user requested workspace organization.
6. Verify final focus and layout.

## Native Implementation Boundaries

- Use Humungousaur-owned Windows tools.
- Do not import Windows-use or OpenClaw app-control code.
- Treat OS tool limitations as gaps, not reasons to call upstream runtimes directly.

## Safety And Approval

- Launching apps and changing windows can reveal private data; follow tool approvals.
- Do not close unsaved work without explicit confirmation.
- Do not move windows across desktops if it would hide active user work unexpectedly.

## Verification

- Confirm window IDs and titles before and after actions.
- Confirm launched app status from tool result.
- Report blockers such as app not found, unsupported platform, or permission failure.

## Failure Modes

- Launching the wrong similarly named app.
- Closing a window instead of minimizing.
- Acting before the target window is ready.

## References

- Shortlist item: `app-launch-and-window-management`.
- Native tools: Humungousaur OS control tools.
