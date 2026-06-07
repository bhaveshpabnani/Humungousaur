---
name: browser-computer-use
description: Use browser, Playwright, and computer-use style tools through observed state and approval-gated actions.
---

# Browser And Computer Use

## Tool Map

- `browser_live_status`
- `browser_live_open`
- `browser_live_observe`
- `browser_live_click`
- `browser_live_type`
- `browser_live_screenshot`
- `browser_live_wait`
- `os_active_window`
- `os_observe_ui`
- `os_click_element`
- `os_type_text`
- `os_send_keys`
- `screenshot_capture`

Use this skill when a task requires web navigation, browser UI testing, desktop GUI observation, or Windows app control.

Workflow:

1. Observe current state before acting.
2. Prefer browser tools for web pages and OS/UI tools for native desktop apps.
3. Use element ids from the most recent observation instead of stale coordinates when possible.
4. Take one state-changing action at a time, then observe again.
5. Keep high-risk GUI actions approval-gated.
6. Use Codex or Playwright guidance as evidence when it is available, but choose tools through model reasoning and schemas.

Verification:

- For browser work, verify URL, title, visible text, and form state after each action.
- For GUI work, verify active window and observed element state before clicking or typing.
- For frontend work, use real screenshots or browser observations before calling the task finished.
