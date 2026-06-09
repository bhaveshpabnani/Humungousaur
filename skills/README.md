# Humungousaur Skills

Skills are organized by broad capability domain. Each domain folder owns a parent `SKILL.md`, and each child folder owns a focused child `SKILL.md`.

## Domains

- `agent-core`: cognition, memory, approvals, safety, focus, taskflow, and system readiness.
- `delegation-agents`: multi-agent coordination, worker handoffs, and coding-agent delegation.
- `browser-web`: browser evidence, web extraction, web forms, live browser testing, and web artifact work.
- `office-productivity`: spreadsheets, documents, slides, reports, meetings, research, and knowledge work.
- `communications`: email, chat, channels, messaging, outbound drafts, and communication policy.
- `integrations`: external APIs, Google/Notion/Airtable/GitHub/RSS/GOG/OpenAI/Claude integrations.
- `software-engineering`: code inspection, debugging, CI, tests, dependency/security review, and skill authoring.
- `desktop-control`: local UI, accessibility, files, windows, clipboard, screenshots, and app troubleshooting.
- `voice-media`: speech, voice loops, audio/video/image/music workflows, and media summaries.
- `creative-design`: writing, brand, diagrams, canvas, themes, infographics, and creative work.
- `commerce-travel`: shopping, travel, rail, flights, maps, and payment/booking safety.

## Hierarchy Rules

- Domain folders group related skills; domain parent skill names match the domain folder.
- Parent skills reference child skills in `Tool Map`, `Sub-Skills`, or `Skill Map` sections.
- The orchestrator reads parent skills first, then recursively exposes child summaries, Tool Maps, and child refs with bounded depth.
- Full child details are loaded only when a selected child needs them or when the planner calls `agent_skill_read`.
- Tool-specific implementation detail belongs in tools or leaf skills, not in the central planner prompt.
