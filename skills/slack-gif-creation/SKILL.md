---
name: slack-gif-creation
description: Plan or create Slack-appropriate GIF concepts and lightweight animation artifacts through native media/artifact paths with approval-safe sharing.
---

# Slack GIF Creation

## Purpose

Support small, tasteful animated assets for Slack or team communication. Current execution should use native artifact/code paths or drafts unless a GIF encoder tool is implemented.

## When To Use

Use for celebratory GIF concepts, team reactions, onboarding animations, or Slack-optimized media drafts.

## Inputs And Evidence

- Message intent, audience, brand/style, duration, dimensions, and delivery channel.
- Native media capability status.

## Tool Map

- `web-artifact-builder`
- `algorithmic-art`
- `media_storyboard_create`
- `media_storyboard_inspect`
- `channel_message_prepare`
- `message-approval-policy`
- `tool_search`

## Workflow

1. Clarify emotion/message and audience.
2. Define safe, work-appropriate concept.
3. Use `media_storyboard_create` to create a local storyboard/contact-sheet artifact for the GIF concept, dimensions, scenes, palette, accessibility, and licensing constraints.
4. Use `media_storyboard_inspect` to verify the artifact and SVG path.
5. Prepare Slack message only after review.
6. Do not send/post without approval.

## Native Implementation Boundaries

- Do not import Anthropic Slack GIF creator code.
- GIF generation must be Humungousaur-owned or approved artifact workflow.
- Slack delivery uses native channel tools.
- The native storyboard tool creates Markdown/JSON/SVG planning artifacts; a binary GIF encoder remains a separate approved implementation.

## Safety And Approval

- Avoid embarrassing, offensive, or copyrighted material.
- External/team posting requires approval.
- Respect brand and workplace norms.

## Verification

- Artifact path proves generated media/prototype.
- Prepared Slack outbox proves draft only.
- State if the deliverable is a storyboard/contact sheet rather than a binary GIF.

## Failure Modes

- Claiming GIF output from a storyboard.
- Posting without review.
- Oversized or inaccessible animation.

## References

- Shortlist item: `slack-gif-creation`.
