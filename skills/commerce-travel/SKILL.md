---
name: commerce-travel
description: Parent skill for shopping, payments, maps, rail, flight, and travel booking research with approval-gated purchase and booking boundaries.
---

# Commerce Travel

## Purpose

Use this parent skill for travel options, railway or flight tickets, shopping comparison, maps, purchases, availability, fares, and booking intent preparation.

## Hierarchy Reading Rules

1. Start with this parent to classify the task as rail, flight, shopping, maps, or payment safety.
2. Load the domain child skill before using booking or purchase-specific workflows.
3. Use live/current evidence for availability, prices, schedules, and inventory.
4. Stop at prepared intent unless the user explicitly approves the exact booking, purchase, payment, or account-changing step.

## Tool Map

- `flight-ticket-booking`
- `railway-ticket-booking`
- `safe-shopping-and-payments`
- `shopping-assistant`
- `travel-and-maps`

## Child Skill Guide

- Use railway ticket booking for trains, Indian railway availability, classes, quotas, and PNR-sensitive boundaries.
- Use flight ticket booking for air routes, fares, baggage, layovers, provider comparisons, and hold or purchase boundaries.
- Use travel and maps for routes, locations, local logistics, itineraries, and geography.
- Use shopping assistant for product comparison, stock, seller, warranty, and buying choices.
- Use safe shopping and payments whenever checkout, payment, personal data, account state, refunds, or cancellation can occur.

## Verification

- Distinguish offered service, live availability, waitlist, sold out, unresolved, and booked.
- Verify date, route, class/cabin, passenger count assumptions, source, and timestamp before finalizing.
- Never store payment details or claim a booking/purchase without observed confirmation and approved steps.
