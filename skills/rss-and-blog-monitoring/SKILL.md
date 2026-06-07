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
- `rss_feed_read`
- `rss_watch_prepare`
- `rss_watch_list`
- `activity_ingest`
- `memory_write`
- `cognitive_trigger_record`
- `write_note`

## Workflow

1. Identify sources and cadence.
2. Use `rss_feed_read` for RSS or Atom feeds; use `fetch_webpage`/`research_webpages` for ordinary blog pages.
3. Summarize changes with source links and dates.
4. Record durable watch intent with `rss_watch_prepare` only when the user wants ongoing monitoring.
5. Inspect existing prepared watches with `rss_watch_list`.
6. Use trigger/automation tools for scheduled checks only after explicit approval.
7. Report missing scheduler/credential gaps separately from feed parsing.

## Native Implementation Boundaries

- Do not import Hermes blogwatcher or OpenClaw RSS plugins.
- Feed parsing and watch preparation must use Humungousaur-owned tools.
- Prepared watch artifacts do not start polling.
- Do not silently run background polling.

## Safety And Approval

- Respect source terms and rate limits.
- Avoid noisy notifications.
- Do not subscribe the user externally without approval.

## Verification

- Source links and timestamps prove current summary.
- RSS watch paths prove prepared intent; trigger IDs prove scheduled monitoring.
- Missing adapter status should be explicit.

## Failure Modes

- Summarizing stale pages.
- Creating hidden recurring work.
- Missing source attribution.

## References

- Shortlist item: `rss-and-blog-monitoring`.
