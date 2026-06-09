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
- `shopping_comparison_create`
- `shopping_comparison_inspect`
- `purchase_intent_prepare`
- `write_note`
- `message-approval-policy`

## Workflow

1. Clarify budget, constraints, and decision criteria.
2. Gather current product evidence from native web/browser tools.
3. Compare options by user-relevant dimensions, not only price.
4. Use `shopping_comparison_create` to preserve products, evidence timing, seller/price/availability, risks, and recommendation as a local artifact.
5. Use `shopping_comparison_inspect` before reporting the shortlist or recommendation.
6. If the user wants a cart/review step, use `purchase_intent_prepare` and stop before checkout, payment, order placement, or contacting sellers unless explicitly approved.

## Native Implementation Boundaries

- Use Humungousaur web and browser tools.
- Do not import external reference shopping plugins or store-specific upstream scripts.
- Do not use brittle product-name keyword routing; reason from user criteria and page evidence.
- Native commerce tools create research and purchase-review artifacts only; they do not buy, add to cart, or contact sellers.

## Safety And Approval

- Purchases, carts, payments, addresses, and seller messages require approval.
- Do not store payment details.
- Verify current prices because they change frequently.

## Verification

- Include source URLs and observation timing for prices/specs.
- Say when availability or shipping was not verified.
- Inspect shopping comparison artifacts and confirm `research_only_not_purchased`.
- A purchase claim requires an approved native action result, which should usually be avoided.

## Failure Modes

- Recommending based on outdated cached knowledge.
- Ignoring compatibility or return policy.
- Accidentally submitting a purchase flow.

## References

- Shortlist item: `shopping-assistant`.
- Upstream inspiration: external reference shopping category as reference only.
