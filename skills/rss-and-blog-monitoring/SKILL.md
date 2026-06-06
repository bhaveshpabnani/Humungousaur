---
name: rss-and-blog-monitoring
description: Monitor, summarize, and turn feeds or blogs into notes and briefings using native web, activity, trigger, and memory tools or explicit adapter plans.
---

# RSS And Blog Monitoring

## Purpose

Track recurring web sources and produce useful summaries without building hidden polling behavior. Native triggers/automation should be explicit and bounded.

## When To Use

Use for RSS feeds, blog updates, release notes, newsletters, changelogs, and scheduled briefings.

## Inputs And Evidence

- Feed/blog URLs, cadence, summary format, filters, and notification preference.
- Current page/feed evidence and prior memory.

## Tool Map

- `fetch_webpage`
- `research_webpages`
- `activity_ingest`
- `memory_write`
- `cognitive_trigger_record`
- `write_note`

## Workflow

1. Identify sources and cadence.
2. Fetch or inspect current source content.
3. Summarize changes with source links and dates.
4. Record durable watch intent only when the user wants ongoing monitoring.
5. Use trigger/automation tools for scheduled checks if supported.
6. Report missing native RSS parser/monitor adapter when needed.

## Native Implementation Boundaries

- Do not import Hermes blogwatcher or OpenClaw RSS plugins.
- Monitoring must use Humungousaur-owned triggers/adapters.
- Do not silently run background polling.

## Safety And Approval

- Respect source terms and rate limits.
- Avoid noisy notifications.
- Do not subscribe the user externally without approval.

## Verification

- Source links and timestamps prove current summary.
- Trigger IDs prove scheduled monitoring.
- Missing adapter status should be explicit.

## Failure Modes

- Summarizing stale pages.
- Creating hidden recurring work.
- Missing source attribution.

## References

- Shortlist item: `rss-and-blog-monitoring`.
