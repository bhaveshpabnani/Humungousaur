---
name: flight-ticket-booking
description: Research, compare, and prepare flight ticket booking intents from current fare evidence while stopping before passenger-data submission, seat purchase, payment, or final booking.
---

# Flight Ticket Booking

## Purpose

Find flight options, verify current fares and restrictions, compare itinerary tradeoffs, and prepare a booking review artifact. This skill supports flight booking work without executing the booking.

## When To Use

Use when the user asks for flights, airfare, flight availability, flight tickets, fare classes, baggage allowances, connections, or help booking a flight.

## Tool Map

- `web_search`
- `research_web_pages`
- `fetch_web_page`
- `browser_live_status`
- `browser_live_open`
- `browser_live_observe`
- `browser_live_search`
- `browser_live_query_selector`
- `browser_live_dropdown_options`
- `browser_live_select_option`
- `browser_live_click`
- `browser_live_type`
- `browser_live_press_key`
- `browser_live_scroll`
- `browser_live_wait`
- `browser_live_evaluate_js`
- `browser_live_screenshot`
- `travel_booking_intent_prepare`
- `travel_booking_intent_inspect`
- `purchase_intent_prepare`
- `purchase_intent_inspect`
- `browser-evidence-workflow`
- `web-form-automation`
- `safe-shopping-and-payments`

## Inputs

- Origin and destination airport/city, dates, one-way/round trip/multi-city, passenger count, cabin, baggage needs, budget, and timing preferences.
- Airline/provider preference, refund/change constraints, layover tolerance, and visa/transit concerns.
- Whether the user wants current fare research, a short list, or a prepared booking intent.

## Workflow

1. Resolve dates concretely and state assumptions when the user gives partial or relative dates.
2. Use search only for discovery when no booking/search provider URL is supplied.
3. Open a concrete airline, OTA, or search provider page and verify visible route, dates, traveler count, cabin, and currency.
4. Prefer source-visible fare cards over snippets. Use live browser controls for date pickers, airports, passenger counts, cabin filters, and sort/filter controls.
5. For each option, capture airline/provider, flight number when visible, departure/arrival, airports, connection count, duration, cabin/fare family, fare, baggage allowance, change/refund terms, and source timestamp.
6. Separate base fare from taxes, convenience fees, baggage/seat fees, and payment fees when visible.
7. Do not treat fare calendars or ads as final ticket price unless the page confirms the selected itinerary and passengers.
8. If the user asks to proceed, create `travel_booking_intent_prepare` with flight mode, options, selected option if any, checks, uncertainties, and approval note.
9. Inspect the booking intent before reporting it. The status must remain `prepared_not_booked`.
10. Stop before login, passenger data submission, seat/add-on purchase, payment, final booking, cancellation, or loyalty-account changes unless the user explicitly approved that exact action and tool policy permits it.

## Approval Boundary

- Reading public fare/search results is allowed.
- Preparing a local booking intent is allowed.
- Passenger details, passport/ID details, frequent-flyer details, add-ons, seat selection, checkout, payment, cancellation, or final booking require explicit user approval at action time.
- Do not store payment credentials or full identity documents in artifacts.

## Verification

- Confirm visible route, date, passenger count, cabin, currency, provider, fare, and terms before finalizing.
- Re-observe after each form/filter/date action.
- Preserve provider/source refs and evidence timestamps in booking intents.
- A final booked-flight claim requires observed confirmation evidence and user-approved payment/booking steps.

## Failure Modes

- Answering from stale fare snippets.
- Mixing one-way and round-trip prices.
- Ignoring taxes, baggage, seat, payment, or convenience fees.
- Skipping refund/change terms on non-refundable fares.
- Continuing through checkout without explicit approval.
