---
name: social-media-drafting
description: Draft posts, threads, replies, captions, and social updates with audience fit, safety review, and no automatic posting unless a native approved channel/tool exists.
---

# Social Media Drafting

## Purpose

Help the user write social content without turning the assistant into an uncontrolled broadcaster. This skill creates drafts, variants, and review notes while keeping posting behind explicit approval and native tool support.

## When To Use

Use for LinkedIn posts, X/Twitter-style threads, community updates, launch posts, replies, captions, or public-facing short content.

## Inputs And Evidence

- Platform, audience, intent, source facts, desired tone, and length.
- Links, screenshots, product details, or announcement facts.
- Risk constraints: privacy, policy, legal, competitive, or safety.
- Native channel or browser posting support if requested.

## Tool Map

- `write_note`
- `memory_write`
- `read_file`
- `browser_live_open`
- `browser_live_observe`
- `channel_message_prepare`
- `message-approval-policy`

## Workflow

1. Identify platform norms and audience.
2. Extract verified facts and decide what should stay private.
3. Draft one strong version and optional shorter/warmer/more formal variants.
4. Avoid unsupported claims, protected lyrics, private data, and impersonation.
5. Save reusable drafts when requested.
6. Do not post automatically; use native browser/channel actions only after explicit approval.

## Native Implementation Boundaries

- Do not use Hermes X/Twitter utilities, OpenClaw social plugins, or third-party posting scripts as implementation.
- If a native social API adapter does not exist, provide drafts or use approved browser control as a user-directed path.

## Safety And Approval

- Public posts need review before publication.
- Do not imitate a real person's private voice without user-provided context and permission.
- Do not disclose confidential roadmap, keys, addresses, or private conversations.

## Verification

- Confirm whether output is a draft, saved note, prepared message, or posted artifact.
- Posting requires a native tool result proving success.
- Check factual claims against provided evidence.

## Failure Modes

- Generic content that does not match platform or audience.
- Accidentally publishing a draft.
- Overclaiming product features or timelines.

## References

- Shortlist item: `social-media-drafting`.
- Upstream inspiration: Hermes X/Twitter and OpenClaw social categories as reference only.
