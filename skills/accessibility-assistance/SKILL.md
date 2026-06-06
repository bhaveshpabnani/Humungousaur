---
name: accessibility-assistance
description: Reduce user friction with UIA observations, spoken responses, keyboard-friendly flows, readable summaries, and careful adaptation to the user's accessibility needs.
---

# Accessibility Assistance

## Purpose

Make the assistant more helpful for accessibility and ease-of-use needs. This skill uses native UI observations, voice, keyboard, and summarization tools to reduce friction without making assumptions about the user's abilities.

## When To Use

Use when the user asks for accessibility help, easier navigation, reading screen content, voice-first interaction, keyboard alternatives, or reducing repetitive UI work.

## Inputs And Evidence

- User-stated need, preference, or temporary constraint.
- Current app/browser state.
- Voice provider status, UIA observations, screenshots, or browser observations.
- Desired accommodation or workflow simplification.

## Tool Map

- `os_observe_ui`
- `os_send_keys`
- `voice_response_prepare`
- `voice_speak`
- `browser_live_observe`
- `screenshot_capture`
- `memory_write`

## Workflow

1. Ask or infer from explicit context what kind of assistance is needed.
2. Observe UI state through structured tools.
3. Prefer keyboard-friendly and reversible actions.
4. Provide concise spoken or text summaries when helpful.
5. Remember stable accessibility preferences only when the user asks or clearly wants durable memory.
6. Verify that the adapted workflow actually reduced friction.

## Native Implementation Boundaries

- Use Humungousaur voice, browser, OS, and memory tools.
- Do not import OpenClaw accessibility-toolkit code or upstream scripts.
- Do not hardcode assumptions about disability or preference.

## Safety And Approval

- Accessibility needs can be sensitive; store only explicit, useful preferences.
- Do not speak private content aloud in shared contexts.
- UI actions remain approval-gated where required.

## Verification

- Verify the active UI state after actions.
- Confirm voice artifacts or spoken output status.
- Ask for correction when an accommodation is not working.

## Failure Modes

- Assuming a need the user did not state.
- Making the UI harder by adding too much narration.
- Speaking sensitive screen content aloud.

## References

- Shortlist item: `accessibility-assistance`.
- Upstream inspiration: OpenClaw accessibility category as reference only.
