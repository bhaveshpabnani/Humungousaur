---
name: live-browser-testing
description: Test live browser apps with Humungousaur's Playwright-backed browser tools, observation-first actions, screenshots, downloads, PDFs, and evidence-backed completion checks.
---

# Live Browser Testing

## Purpose

Run real browser checks for local or remote web apps using Humungousaur-owned Playwright-backed tools. This skill is inspired by webapp testing practices, but execution stays inside Humungousaur's native browser tool surface.

## When To Use

Use for frontend smoke tests, local app QA, login-free flows, responsive checks, forms, screenshots, console-visible behavior, downloads, PDF export, and verifying that a UI change actually renders.

## Inputs And Evidence

- Target URL, expected screen, viewport needs, and user flow.
- `browser_live_status` readiness.
- Live session ID, observed element IDs, page URL/title/text, screenshot or artifact paths.
- Test result, blocker, or approval status for state-changing actions.

## Tool Map

- `browser_live_status`
- `browser_live_open`
- `browser_live_navigate`
- `browser_live_observe`
- `browser_live_back`
- `browser_live_forward`
- `browser_live_reload`
- `browser_live_query_selector`
- `browser_live_html`
- `browser_live_page_search`
- `browser_live_find_elements`
- `browser_live_extract`
- `browser_live_dropdown_options`
- `browser_live_select_option`
- `browser_live_click`
- `browser_live_hover`
- `browser_live_click_coordinates`
- `browser_live_drag`
- `browser_live_drag_coordinates`
- `browser_live_type`
- `browser_live_fill_form`
- `browser_live_scroll`
- `browser_live_scroll_to_text`
- `browser_live_resize`
- `browser_live_press_key`
- `browser_live_upload_file`
- `browser_live_download`
- `browser_live_save_pdf`
- `browser_live_evaluate_js`
- `browser_live_wait`
- `browser_live_screenshot`
- `browser_live_tabs`
- `browser_live_new_tab`
- `browser_live_switch_tab`
- `browser_live_close_tab`
- `browser_live_close`

## Workflow

1. Check live browser readiness when setup is uncertain.
2. Open the target URL and immediately observe the page.
3. Use observed element IDs for clicks and typing; avoid stale coordinates.
4. Take one state-changing action, then observe again.
5. Capture screenshots for visual claims or regression evidence.
6. Report verified behavior, blockers, and any untested assumptions.

## Native Implementation Boundaries

- Use Humungousaur `browser_live_*` tools only.
- Do not import Anthropic webapp-testing, external reference dogfood, or Playwright scripts from upstream skill repos.
- If Playwright dependencies are missing, report the native setup gap.

## Safety And Approval

- Clicks, typing, uploads, downloads, JS evaluation, PDFs, screenshots, and tab closing are approval-sensitive where tool policy requires it.
- Do not submit forms, payments, posts, or account changes without explicit user approval.

## Verification

- Completion requires observed URL/title/text or screenshot evidence.
- For form flows, verify values and resulting state after each action.
- For visual QA, use screenshot artifacts rather than memory alone.

## Failure Modes

- Calling a UI done without opening it.
- Acting from an old observation after the page changed.
- Ignoring mobile or desktop layout constraints when they matter.

## References

- Shortlist item: `live-browser-testing`.
- Native tools: Humungousaur live browser tools.
