---
name: shopping-assistant
description: Research and compare products, prices, constraints, and purchase options while keeping checkout, payments, and messages approval-gated.
---

# Shopping Assistant

## Purpose

Help the user make informed purchase decisions without autonomously buying anything. This skill turns shopping/e-commerce references into native research, comparison, note, and approval workflows.

## When To Use

Use when the user asks to compare products, find options, evaluate specs, inspect reviews, prepare a cart, or decide what to buy.

## Inputs And Evidence

- Budget, region, must-have features, nice-to-have features, constraints, and preferred stores.
- Product pages, current prices, shipping/return terms, reviews, and availability.
- User's purchase intent and approval boundary.

## Tool Map

- `research_webpages`
- `fetch_webpage`
- `browser_live_open`
- `browser_live_observe`
- `web-data-extraction`
- `write_note`
- `message-approval-policy`

## Workflow

1. Clarify budget, constraints, and decision criteria.
2. Gather current product evidence from native web/browser tools.
3. Compare options by user-relevant dimensions, not only price.
4. Identify risks: fake reviews, unclear sellers, returns, warranty, compatibility, or hidden fees.
5. Prepare a recommendation and optional shortlist.
6. Stop before checkout, payment, order placement, or contacting sellers unless explicitly approved.

## Native Implementation Boundaries

- Use Humungousaur web and browser tools.
- Do not import OpenClaw shopping plugins or store-specific upstream scripts.
- Do not use brittle product-name keyword routing; reason from user criteria and page evidence.

## Safety And Approval

- Purchases, carts, payments, addresses, and seller messages require approval.
- Do not store payment details.
- Verify current prices because they change frequently.

## Verification

- Include source URLs and observation timing for prices/specs.
- Say when availability or shipping was not verified.
- A purchase claim requires an approved native action result, which should usually be avoided.

## Failure Modes

- Recommending based on outdated cached knowledge.
- Ignoring compatibility or return policy.
- Accidentally submitting a purchase flow.

## References

- Shortlist item: `shopping-assistant`.
- Upstream inspiration: OpenClaw shopping category as reference only.
