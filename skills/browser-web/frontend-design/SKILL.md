---
name: frontend-design
description: Design and implement polished, domain-appropriate frontend interfaces using existing app conventions, visual verification, and native browser testing.
---

# Frontend Design

## Purpose

Build usable interfaces, not placeholder pages. This skill guides product screens, dashboards, tools, and frontend changes with empathy, domain fit, and verification.

## When To Use

Use for UI builds, redesigns, frontend polish, app screens, visual QA, responsive layout, and product-flow improvements.

## Inputs And Evidence

- Product domain, audience, existing design system, screenshots, current UI code, and interaction goals.
- Browser observations, screenshots, and test results.

## Tool Map

- `read_file`
- `search_workspace`
- `browser_live_open`
- `browser_live_observe`
- `browser_live_screenshot`
- `live-browser-testing`
- `codebase-inspection`

## Workflow

1. Inspect existing frontend patterns before designing.
2. Match density, tone, layout, and controls to the domain.
3. Build the actual usable screen first, not a marketing shell.
4. Keep interactions discoverable and ergonomic.
5. Verify in browser with screenshots/observations.
6. Fix responsive text/layout overlap before calling done.

## Native Implementation Boundaries

- Use repo-native frontend code and Humungousaur browser tools.
- Do not import Anthropic frontend-design or external reference design code.
- Generated visual references may inspire, but implementation must be project-owned.

## Safety And Approval

- Avoid hiding important actions.
- Do not add unrelated dependencies without approval.
- Preserve existing design conventions unless the task asks for a redesign.

## Verification

- Browser evidence should prove the UI renders.
- Check desktop/mobile where relevant.
- Report any unverified viewports or interactions.

## Failure Modes

- Generic landing-page output for a tool/app.
- Pretty but unusable controls.
- No real browser verification.

## References

- Shortlist item: `frontend-design`.
