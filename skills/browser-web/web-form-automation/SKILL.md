---
name: web-form-automation
description: Fill, review, and submit browser forms safely using observed fields, explicit values, approval gates, and verification after each browser action.
---

# Web Form Automation

## Purpose

Help the assistant complete browser forms without guessing fields or submitting unintended data. This skill applies Actionbook-style form discipline through Humungousaur's native browser tools.

## When To Use

Use for account forms, contact forms, filters, search boxes, checkout-like forms, surveys, onboarding screens, and browser workflows with text fields, selects, or submit buttons.

## Inputs And Evidence

- Target URL or existing browser session.
- Exact field values and any fields the user wants left blank.
- Observed form or element IDs.
- Confirmation/submit policy and final page state.

## Tool Map

- `browser_open`
- `browser_observe`
- `browser_type`
- `browser_fill_form`
- `browser_submit_form`
- `browser_live_observe`
- `browser_live_type`
- `browser_live_fill_form`
- `browser_live_select_option`
- `browser_live_press_key`
- `browser_live_click`

## Workflow

1. Observe the form and identify fields from structured browser evidence.
2. Map each user-provided value to a field; ask or stop when mapping is ambiguous.
3. Fill fields through native browser tools.
4. Re-observe and verify values before any submission.
5. Submit only when the user explicitly asked and policy approval is satisfied.
6. Verify the post-submit state or report the exact blocker.

## Native Implementation Boundaries

- Use Humungousaur browser tools and schemas.
- Do not import external reference Actionbook, browser-use, or upstream automation code.
- Do not use deterministic keyword matching to decide field semantics; use observed labels and model reasoning.

## Safety And Approval

- Submitting forms, purchases, applications, messages, uploads, or account changes requires approval.
- Do not enter secrets, credentials, or payment details unless the user explicitly provides them for that session.

## Verification

- Field values must be observed before submission.
- Submit result must be verified by page text, URL, status, or screenshot.
- If a captcha/login/payment appears, stop and report.

## Failure Modes

- Typing into the wrong field.
- Submitting stale or incomplete values.
- Treating placeholder text as the user's instruction.

## References

- Shortlist item: `web-form-automation`.
- Related skill: `browser-computer-use`.
