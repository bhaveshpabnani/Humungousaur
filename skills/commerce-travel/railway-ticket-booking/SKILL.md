---
name: railway-ticket-booking
description: Research, compare, and prepare Indian railway ticket booking intents from live evidence while stopping before passenger-data submission, captcha, OTP, payment, or final booking.
---

# Railway Ticket Booking

## Purpose

Find train options, verify class/berth availability, compare tradeoffs, and prepare a booking review artifact. This skill supports railway ticket work without silently booking tickets.

## When To Use

Use when the user asks for trains, railway tickets, sleeper or AC class availability, waitlist status, route/date options, fare comparison, or help booking a rail ticket.

## Tool Map

- `web_search`
- `research_web_pages`
- `fetch_web_page`
- `browser_live_status`
- `browser_live_open`
- `browser_live_observe`
- `browser_live_search`
- `browser_live_query_selector`
- `browser_live_click`
- `browser_live_type`
- `browser_live_select_option`
- `browser_live_press_key`
- `browser_live_scroll`
- `browser_live_scroll_to_text`
- `browser_live_wait`
- `browser_live_evaluate_js`
- `browser_live_screenshot`
- `rail_route_availability_lookup`
- `travel_booking_intent_prepare`
- `travel_booking_intent_inspect`
- `purchase_intent_prepare`
- `purchase_intent_inspect`
- `browser-evidence-workflow`
- `web-form-automation`
- `safe-shopping-and-payments`

## Inputs

- Origin and destination station or city, with station codes when known.
- Journey date and timezone or country context.
- Class or quota, such as SL, 3A, 2A, General, Tatkal, Ladies, or senior citizen.
- Passenger count and broad requirements, not full identity details unless the user explicitly authorizes entry into a verified booking site.
- Preference order: confirmed availability, departure time, arrival time, duration, fare, refund terms, route reliability, or provider.

## Workflow

1. Interpret dates concretely. If the user says a month/day without a year, use the current local date to choose the next plausible date and state that assumption later.
2. Treat route/date requests like "available sleeper class", "available SL", or "sleeper available" as live berth/status availability unless the user explicitly asks only whether the class is offered on the train.
3. Search only if no reliable source URL is already available. Prefer official railway/IRCTC pages when accessible; otherwise use reputable travel providers as evidence and label them.
4. For Indian route/date/class availability, call `rail_route_availability_lookup` with the concrete journey date, class code, origin, and destination. Include a route URL when search/browser has already found one; otherwise let the tool construct its supported route source from origin and destination.
5. Open a concrete source page and verify route, origin, destination, selected date, class, and quota from page-visible state when the lookup tool is not enough or the page/source is unsupported.
6. If static text only gives a timetable, use live browser tools for availability, date picker, class filters, and refresh controls.
7. For each train, capture train number/name, departure, arrival, duration, class, quota, fare, availability status, source, and evidence timestamp.
8. Separate:
   - Confirmed available options.
   - Waitlisted options.
   - Unavailable/regret/sold-out options.
   - Unresolved options that stayed behind "tap to refresh", blocked controls, login, captcha, or provider errors.
9. If the user asked only "what is available", answer from observed evidence and caveats.
10. If the user asks to book or proceed, create `travel_booking_intent_prepare` with rail mode, options, selected option if any, checks, uncertainties, and approval note.
11. Inspect the booking intent before reporting it. The status must remain `prepared_not_booked`.
12. Stop before login, captcha, OTP, passenger details submission, payment, final "Book Now"/"Pay"/"Confirm" action, cancellation, or PNR-changing action unless the user explicitly approved that exact step and the tool policy permits it.

## Approval Boundary

- Reading schedules and availability is allowed.
- Preparing a local booking intent is allowed.
- Adding passenger data, submitting a booking form, solving captcha, entering OTP, paying, cancelling, or confirming a ticket requires explicit user approval at action time.
- Payment details must never be stored in artifacts.

## Verification

- Confirm the source-visible date, route, class, and quota before finalizing.
- Use live observation after every date/filter/click/type action.
- Store unresolved refresh or provider failures as uncertainties instead of guessing.
- A final booked-ticket claim requires observed confirmation evidence, ticket/PNR status, and user-approved booking/payment steps.

## Failure Modes

- Treating timetable availability of a class as live berth availability.
- Counting waitlist as available when the user asked for available seats/berths.
- Losing the selected date because the page defaulted to today.
- Omitting unresolved cards whose availability did not refresh.
- Clicking "Book Now" merely because it is visible.
