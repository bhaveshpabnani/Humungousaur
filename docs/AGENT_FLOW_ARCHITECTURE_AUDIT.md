# Agent Flow Architecture Audit

## Current Flow

1. The orchestrator builds compact runtime context.
2. A model-led relevant-skill selector chooses workspace skills from metadata that includes domain, hierarchy kind, parent skill, and child count.
3. The runtime reads ancestors first: domain parent skills load in full, selected child skills load in full, and sibling or descendant sub-skills are exposed as summaries, Tool Maps, and child references from `Tool Map`, `Sub-Skills`, or `Skill Map` sections.
4. The model planner selects capability groups and exact tools from tool schemas, active skills, context, and observations.
5. The ReAct loop executes one tool at a time, reviews repeated/browser/final actions, and feeds tool observations back into the next turn.
6. The final response is prepared only after evidence is sufficient or after a real blocker is observed.

## Issues Found

- Flat skill selection missed relevant skills that appeared later in the workspace catalog.
- Selected skill bodies were not loaded recursively, so parent skills could not bring their sub-skills into context.
- Active skill Tool Maps were advisory only and did not affect candidate tool availability.
- Recursive skill loading could waste prompt input by placing full child and grandchild skill bodies into context before the planner knew it needed them.
- Domain folders had no parent `SKILL.md`, so domain-level instructions lived in README prose instead of executable skill hierarchy.
- Domain-specific behavior had leaked into central provider prompts instead of living in skills and tool contracts.
- Browser/search/model calls were brittle when local DNS resolution failed, even though public DNS could resolve the host.
- Web search failure could prevent a domain tool from running even when origin/destination were enough to construct a supported source URL.
- JSON model outputs with trailing commentary could break planning and review parsing.
- Real-world office workflows existed as separate skills but lacked a parent skill for research-to-artifact work.

## Fixes Implemented

- Added model-led relevant skill selection with full workspace skill catalog coverage.
- Added bounded hierarchical sub-skill loading from skill references.
- Added progressive skill disclosure: parent skill bodies load in full, child skills load as summaries with declared tools and child refs, and `agent_skill_read` loads child details only when needed.
- Added parent `SKILL.md` files to every domain folder with domain instructions, child Tool Maps, and child-selection guidance.
- Added ancestor-first loading so a directly selected child still inherits its parent domain instructions.
- Added active-skill Tool Map integration into candidate tool selection.
- Moved task-specific travel/browser instructions into skills and domain tools.
- Added `rail_route_availability_lookup` as a read-only domain evidence tool.
- Added DNS fallback for model, browser/search, and rail HTTP fetch paths.
- Added tolerant JSON object extraction for planner/reviewer outputs.
- Added `real-world-workflows` as a parent skill for browser research, extraction, spreadsheets, reports, docs, and decks.

## Remaining Architecture Risks

- Skill hierarchy is metadata-driven and bounded, but later runs can still improve ranking of sibling sub-skills by observed marginal utility.
- Multi-agent coordination records boards and specialist contracts, but it does not yet spawn truly isolated parallel model workers in this runtime.
- Browser interaction is more resilient, but live browser UI control still depends on Playwright availability and page-specific accessibility.
- Artifact QA for complex decks/docs can be stronger when render-to-image inspection is available for every format.
- Search engine access can still vary by network environment, so domain tools should keep accepting structured inputs that avoid search when possible.

## Verification

- Focused regression suite: `201 passed, 4 skipped, 270 subtests passed`.
- Skill smoke: `failed_count: 0`.
- Live GPT-5.4 rail query test answered with `12809 HOWRAH MAIL` and `SL: AVL4` via `rail_route_availability_lookup`.
