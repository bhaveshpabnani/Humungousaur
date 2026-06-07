---
name: screenshot-ocr-review
description: Capture, inspect, summarize, and manage screen evidence with native screenshot tools and careful privacy boundaries; use OCR only when a native OCR path is available.
---

# Screenshot OCR Review

## Purpose

Use screen captures as visual evidence for UI review, troubleshooting, and accessibility. This skill is careful about privacy and does not claim OCR unless a native OCR/tool path actually runs.

## When To Use

Use when the user asks what is on screen, needs visual UI evidence, wants screenshot review, or asks to diagnose a visible app state.

## Inputs And Evidence

- Active window or screen target.
- Screenshot filename, metadata, and sensitivity.
- User-requested review focus: layout, errors, text, controls, or visual state.

## Tool Map

- `screenshot_capture`
- `screen_captures`
- `screen_capture_delete`
- `ocr_provider_status`
- `os_windows`
- `os_observe_ui`
- `browser_live_screenshot`
- `tool_search`

## Workflow

1. Prefer UIA/browser observations when text structure is available.
2. Capture a screenshot only when visual evidence is needed and approved.
3. Review visible state and note uncertainty.
4. Use `ocr_provider_status` before OCR claims; run OCR only when a native extraction adapter is actually available.
5. Delete sensitive captures when they are no longer needed.
6. Connect visual findings to the task outcome.

## Native Implementation Boundaries

- Use Humungousaur screen and browser screenshot tools.
- Do not import OpenClaw OCR, computer-use, or screenshot scripts as implementation.
- Do not claim OCR/text extraction if only visual observation was performed.

## Safety And Approval

- Screens can show private data; screenshot capture and deletion follow approval policy.
- Do not include secrets from screenshots in responses.
- Avoid broad screen capture in shared or sensitive contexts.

## Verification

- Screenshot paths and metadata prove capture.
- Deletion tool result proves cleanup.
- UI text claims should come from UIA/browser observations or native OCR where available.

## Failure Modes

- Keeping sensitive screenshots.
- Reading text inaccurately from visuals.
- Treating a screenshot as current after the UI changes.

## References

- Shortlist item: `screenshot-ocr-review`.
- Native tools: Humungousaur screen capture tools.
