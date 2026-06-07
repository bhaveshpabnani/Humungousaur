---
name: travel-and-maps
description: Plan routes, places, trips, and local itineraries from current evidence while marking missing native map/API adapters and avoiding unapproved bookings.
---

# Travel And Maps

## Purpose

Support practical travel planning: routes, places, commute options, itineraries, venue research, and map-adjacent decisions. Current execution uses native web/browser research unless a Humungousaur-owned maps adapter is added.

## When To Use

Use for travel plans, local places, route comparisons, hotel/activity research, commute planning, timezone checks, and itinerary drafts.

## Inputs And Evidence

- Origin, destination, dates, budget, mobility constraints, preferences, and region.
- Current web/map evidence, venue pages, transport pages, or user-provided notes.
- Booking, payment, or message approval state.

## Tool Map

- `research_webpages`
- `fetch_webpage`
- `browser_live_open`
- `browser_live_observe`
- `travel_plan_create`
- `travel_plan_inspect`
- `write_note`
- `cognitive_trigger_record`
- `message-approval-policy`

## Workflow

1. Clarify location, dates, constraints, and output shape.
2. Use current web evidence for changing facts such as hours, fares, closures, and weather-sensitive details.
3. Compare options by time, cost, reliability, accessibility, and user preference.
4. Use `travel_plan_create` to preserve route options, places, itinerary days, source refs, evidence timestamps, uncertainties, and approval boundaries.
5. Use `travel_plan_inspect` before reporting a saved itinerary or handing it to reminders/messages.
6. Stop before bookings, payments, cancellations, or messages unless approved.

## Native Implementation Boundaries

- Use Humungousaur-owned web/browser tools or future native map adapters.
- Do not import Hermes map skills or OpenClaw transportation plugins as implementation.
- Do not claim exact live routing without a current source.
- `travel_plan_create` is a local planning artifact tool; it is not live geocoding, routing, booking, or venue contact.

## Safety And Approval

- Bookings, payments, cancellations, and contacting venues require approval.
- Be careful with home/work addresses and personal travel plans.
- Mark uncertain timing and changing availability plainly.

## Verification

- Cite current pages for hours, routes, and prices.
- Note date/time of evidence for travel facts.
- Inspect the travel plan artifact and confirm `planning_only_not_booked`.
- Confirm saved itinerary or reminder IDs when created.

## Failure Modes

- Using stale general knowledge for current schedules.
- Missing accessibility or visa constraints.
- Accidentally booking or cancelling.

## References

- Shortlist item: `travel-and-maps`.
- Upstream inspiration: Hermes maps and OpenClaw transportation references only.
