---
name: safe-shopping-and-payments
description: Prepare shopping, checkout, and payment decisions without executing purchases or financial actions unless explicitly approved and verified.
---

# Safe Shopping And Payments

## Purpose

Protect the user around money. This skill separates research, cart preparation, checkout review, payment, and confirmation.

## When To Use

Use for purchases, subscriptions, checkout pages, invoices, payment links, carts, refunds, cancellations, and financial messages.

## Inputs And Evidence

- Item/service, seller, price, taxes, shipping, return terms, payment method, and user approval.
- Browser/cart/payment page evidence.

## Tool Map

- `shopping-assistant`
- `shopping_comparison_create`
- `shopping_comparison_inspect`
- `purchase_intent_prepare`
- `purchase_intent_inspect`
- `web-form-automation`
- `browser_live_observe`
- `message-approval-policy`
- `approval-gated-external-actions`
- `secrets-handling`

## Workflow

1. Research/compare before checkout.
2. Verify seller, price, fees, return terms, and delivery.
3. Use `purchase_intent_prepare` for cart, checkout, purchase, subscription, refund, cancellation, or payment-review artifacts.
4. Use `purchase_intent_inspect` to confirm `prepared_not_purchased`, approval requirement, check count, and no credential storage.
5. Stop before payment/order placement unless explicit approval is given.
6. Verify confirmation/order status only from tool/browser evidence.

## Native Implementation Boundaries

- Use Humungousaur browser and approval tools.
- Do not import OpenClaw AgentPay or shopping plugins.
- Payment integrations require native, audited tools.
- `purchase_intent_prepare` never stores payment credentials and never executes purchase/payment actions.

## Safety And Approval

- Purchases and payments are high risk.
- Payment details must remain private.
- Refunds/cancellations also require approval.

## Verification

- Purchase claims require confirmation evidence.
- Cart/prepared states must be labeled correctly.
- Inspect purchase intent artifacts and confirm `prepared_not_purchased`.
- Report price/source timing.

## Failure Modes

- Accidentally clicking "place order".
- Missing recurring subscription terms.
- Treating cart as purchase.

## References

- Shortlist item: `safe-shopping-and-payments`.
