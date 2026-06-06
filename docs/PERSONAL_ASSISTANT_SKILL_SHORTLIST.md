# Personal Assistant Skill Shortlist

Status: first implementation map for the 100+ skill integration goal.

Purpose: shortlist source-inspired, Humungousaur-owned skills that are relevant to a complete human personal system assistant. These are not direct third-party installs. Each implementation must follow `docs/AGENT_SKILL_AUTHORING_STANDARD.md`, use Humungousaur tool schemas, and treat upstream material as untrusted reference evidence.

Reference sources inspected locally:

- Hermes Agent: `external_repos/hermes-agent/skills`
- Anthropic Skills: `external_repos/anthropic-skills/skills`
- OpenClaw/ClawHub awesome index: `external_repos/awesome-openclaw-skills/README.md`

## Selection Rules

- Keep skills useful for daily personal assistance, local computer control, communication, productivity, coding, research, documents, memory, automation, multimodal creation, and safe operations.
- Exclude or defer narrow crypto/trading, spammy marketing automation, dubious jailbreak/red-team-only skills, and platform-specific integrations that cannot be safely represented without a trusted adapter.
- Prefer owned skills that map to existing Humungousaur tools first; add scripts/references only when they make execution safer or clearer.
- Every required tool, script, adapter, or runtime helper must be implemented natively in Humungousaur or exposed through an existing trusted Humungousaur tool.
- Do not depend on Hermes Agent, Anthropic Skills, OpenClaw, ClawHub, Codex plugins, or other upstream skill code as the implementation. Use those sources only as reference evidence.
- Skills must not become regex or keyword routes. They are model-readable workflow knowledge.

## Shortlisted Skill Packs

### Core Cognition, Memory, and Autonomy

1. `daily-planning` - Plan the day, convert goals into tasks, and set follow-ups. Sources: OpenClaw `agent-daily-planner`, `adhd-founder-planner`; Humungousaur cognition tools.
2. `task-tracking` - Track commitments, tasks, statuses, blockers, and next actions. Sources: OpenClaw `agent-task-tracker`; Humungousaur commitments.
3. `autonomous-loop-operations` - Run bounded autonomous cycles over events, wakeups, and ready tasks. Sources: OpenClaw `agent-autonomy-primitives`; Humungousaur automation daemon.
4. `agent-self-reflection` - Review recent sessions and update lessons. Sources: OpenClaw `agent-self-reflection`; Humungousaur self-review.
5. `agent-self-assessment` - Assess capability, safety, and reliability before complex work. Sources: OpenClaw `agent-self-assessment`, `agent-audit`.
6. `memory-metabolism` - Curate, summarize, archive, and forget stale memory. Sources: OpenClaw `active-maintenance`; Humungousaur memory curation.
7. `persona-evolution` - Update communication style and user preferences from evidence. Sources: Humungousaur persona tools; OpenClaw personal development category.
8. `focus-and-priority-review` - Decide what matters next across goals, tasks, and environment. Sources: Humungousaur priority review.
9. `wakeup-scheduling` - Create, evaluate, and cancel future wakeups or reminders. Sources: Hermes Apple Reminders, OpenClaw calendar/scheduling category.
10. `session-wrap-up` - Summarize a work session, commit eligible changes, and persist lessons. Sources: OpenClaw `alex-session-wrap-up`; Hermes GitHub workflow.
11. `agent-team-orchestration` - Coordinate specialists with task lifecycle and review. Sources: OpenClaw `agent-team-orchestration`; Hermes kanban orchestrator.
12. `agent-worker-handoff` - Hand work to another agent/CLI and verify outputs. Sources: Hermes `codex`, `claude-code`, `opencode`.
13. `skill-authoring` - Create and improve compliant SKILL.md packs. Sources: Hermes skill authoring, Anthropic `skill-creator`.
14. `skill-security-review` - Review skill provenance, scripts, permissions, and risk. Sources: OpenClaw `arc-trust-verifier`, `azhua-skill-vetter`, `aegis-audit`.
15. `capability-audit` - Audit tools, plugins, skills, channels, providers, and gaps. Sources: OpenClaw agent audit entries; Humungousaur capability surface.

### Voice, Speech, and Ambient Interaction

16. `voice-wakeup-loop` - Wake-word, STT, harness, and TTS loop. Sources: existing `voice-loop`, Hermes media/audio skills.
17. `local-speech-operations` - Use local Whisper and Windows SAPI before cloud speech. Sources: Humungousaur local voice wiring.
18. `meeting-transcription` - Transcribe meetings and create summaries/actions. Sources: Hermes Teams meeting pipeline, OpenClaw speech/transcription.
19. `meeting-follow-up` - Convert meeting notes into tasks, emails, reminders, and docs. Sources: Hermes Teams meeting pipeline, internal comms.
20. `voice-call-gateway` - Handle phone/voice-call channel flows with consent. Sources: OpenClaw voice-call channel notes.
21. `ambient-room-context` - Observe group chatter as quiet context until response is justified. Sources: OpenClaw ambient rooms.
22. `bot-loop-protection` - Detect and suppress bot-to-bot loops in channels. Sources: OpenClaw bot-loop protection.
23. `spoken-response-style` - Prepare concise voice responses and choose speak vs artifact. Sources: Humungousaur voice tools.
24. `audio-content-summary` - Summarize audio or video transcripts. Sources: Hermes YouTube content, Songsee.
25. `music-and-sound-generation` - Draft prompts for music/sound tools when explicitly requested. Sources: Hermes AudioCraft, HeartMuLa, songwriting.

### Channels and Communication

26. `channel-gateway-operations` - Normalize chat channels into the interaction harness. Sources: existing `channel-gateway`, OpenClaw gateway docs.
27. `slack-operations` - Slack DMs, MPIMs, channels, mentions, and approval-safe replies. Sources: existing Slack skill, OpenClaw Slack channel.
28. `whatsapp-operations` - WhatsApp setup, QR pairing, and safe message preparation. Sources: existing WhatsApp skill, OpenClaw WhatsApp channel.
29. `telegram-operations` - Telegram bot setup, groups, markdown media, and replies. Sources: existing Telegram skill, OpenClaw Telegram channel.
30. `discord-operations` - Discord bot channels, DMs, and server behavior. Sources: existing Discord skill, OpenClaw Discord channel.
31. `teams-operations` - Microsoft Teams chat and meeting workflow. Sources: OpenClaw Teams channel, Hermes Teams pipeline.
32. `signal-operations` - Signal private messaging through signal-cli style adapters. Sources: OpenClaw Signal channel.
33. `sms-operations` - Twilio-style SMS channel setup and policy. Sources: OpenClaw SMS channel.
34. `webchat-operations` - Browser WebChat UI over WebSocket. Sources: OpenClaw WebChat channel.
35. `email-operations` - Read, compose, send, search, and summarize email. Sources: Hermes Himalaya, Google Workspace.
36. `internal-comms-writing` - Write updates, FAQs, incident notes, newsletters. Sources: Anthropic `internal-comms`.
37. `status-update-writing` - Concise blocker-first project updates. Sources: OpenClaw session wrap-up, Humungousaur memory preferences.
38. `social-media-drafting` - Draft posts, threads, and replies with review gates. Sources: Hermes X/Twitter xurl, OpenClaw social category.
39. `contact-and-relationship-notes` - Maintain people, preferences, and relationship context. Sources: OpenClaw second-brain entries.
40. `message-approval-policy` - Require user approval for external-visible messages. Sources: OpenClaw gateway security, Humungousaur policy.

### Browser, Computer, and OS Control

41. `browser-computer-use` - Browser automation with observation, element IDs, typing, and screenshots. Sources: existing browser skill, Anthropic webapp testing.
42. `live-browser-testing` - Test local web apps with Playwright and browser logs. Sources: Anthropic `webapp-testing`, Hermes dogfood.
43. `web-form-automation` - Fill and submit forms only with approval. Sources: OpenClaw Actionbook, browser automation category.
44. `web-data-extraction` - Extract structured data from pages with provenance. Sources: OpenClaw search/research, Hermes browser QA.
45. `shopping-assistant` - Compare products and prepare purchase decisions with approval. Sources: OpenClaw shopping/e-commerce category.
46. `travel-and-maps` - Routes, POIs, geocoding, and local itinerary assistance. Sources: Hermes maps, OpenClaw transportation.
47. `desktop-ui-control` - Observe UIA tree, click elements, type text, and manage windows. Sources: existing computer-use skills.
48. `keyboard-mouse-screen-control` - Coordinate cursor, keyboard shortcuts, screenshots, and safety gates. Sources: OpenAI/Claude computer-use inspirations.
49. `app-launch-and-window-management` - Launch allowed apps and arrange windows/desktops. Sources: Windows-use, OpenClaw computer control entries.
50. `clipboard-operations` - Read/write clipboard with approval and redaction. Sources: computer-use operations.
51. `local-file-navigation` - Search, read, write notes, and manage workspace files safely. Sources: Humungousaur file tools.
52. `screenshot-ocr-review` - Capture screens and inspect visual state. Sources: OpenClaw computer/browser categories.
53. `accessibility-assistance` - Reduce friction with accessibility-oriented workflows. Sources: OpenClaw `accessibility-toolkit`.
54. `local-app-troubleshooting` - Inspect running apps, logs, windows, and app state. Sources: Windows-use, browser-use, system status.
55. `system-health-check` - Check disk, environment, dependencies, and local service readiness. Sources: OpenClaw active maintenance, Humungousaur system tools.

### Coding, Git, and Engineering

56. `codebase-inspection` - Inspect structure, languages, LOC, and hotspots. Sources: Hermes `codebase-inspection`.
57. `systematic-debugging` - Four-phase root-cause debugging. Sources: Hermes `systematic-debugging`.
58. `test-driven-development` - Red-green-refactor workflow for code changes. Sources: Hermes `test-driven-development`.
59. `spike-experiment` - Run bounded throwaway experiments before implementation. Sources: Hermes `spike`.
60. `code-review` - Review diffs for bugs, security, and missing tests. Sources: Hermes `github-code-review`.
61. `request-code-review` - Prepare pre-commit review and quality gates. Sources: Hermes `requesting-code-review`.
62. `github-pr-workflow` - Branch, commit, open PR, inspect CI, merge when approved. Sources: Hermes GitHub PR workflow.
63. `github-issues` - Create, triage, label, and update issues. Sources: Hermes `github-issues`.
64. `github-repo-management` - Clone, fork, remote, release, and repo admin flows. Sources: Hermes repo management.
65. `git-auth-setup` - Set up HTTPS tokens, SSH, and gh login. Sources: Hermes `github-auth`.
66. `ci-failure-debugging` - Inspect failing checks and logs, patch root causes. Sources: GitHub CI skills, OpenClaw CI audit.
67. `codex-cli-delegation` - Delegate bounded work to Codex CLI and verify. Sources: existing `codex-delegation`, Hermes `codex`.
68. `claude-code-delegation` - Delegate coding to Claude Code when configured. Sources: Hermes `claude-code`.
69. `opencode-delegation` - Delegate coding to OpenCode when configured. Sources: Hermes `opencode`.
70. `node-debugging` - Debug Node via inspector and browser DevTools protocol. Sources: Hermes node inspect debugger.
71. `python-debugging` - Debug Python with pdb/debugpy and evidence. Sources: Hermes `python-debugpy`.
72. `mcp-server-builder` - Build MCP servers with tools and auth. Sources: Anthropic `mcp-builder`.
73. `claude-api-development` - Build/debug Anthropic SDK apps. Sources: Anthropic `claude-api`.
74. `openai-api-development` - Build/debug OpenAI-compatible and Responses API clients. Sources: Humungousaur model clients.
75. `agent-api-integration` - Discover and wrap external APIs as agent tools. Sources: OpenClaw AgentAPI entries.

### Documents, Data, and Knowledge Work

76. `doc-coauthoring` - Co-author specs, proposals, and docs. Sources: Anthropic `doc-coauthoring`.
77. `docx-operations` - Create/read/edit Word documents. Sources: Anthropic `docx`, Hermes document skills.
78. `pdf-operations` - Read, split, merge, OCR, fill, and create PDFs. Sources: Anthropic `pdf`, Hermes nano-pdf.
79. `pptx-operations` - Create/read/edit slide decks. Sources: Anthropic `pptx`, Hermes PowerPoint.
80. `xlsx-operations` - Clean, analyze, format, and create spreadsheets. Sources: Anthropic `xlsx`.
81. `ocr-document-extraction` - Extract text/tables from scans and documents. Sources: Hermes OCR/documents.
82. `google-workspace` - Gmail, Calendar, Drive, Docs, Sheets workflows. Sources: Hermes Google Workspace.
83. `notion-operations` - Read/write Notion pages and databases. Sources: Hermes Notion.
84. `airtable-operations` - Airtable records, filters, and upserts. Sources: Hermes Airtable.
85. `obsidian-notes` - Search, create, and edit Obsidian vault notes. Sources: Hermes Obsidian.
86. `second-brain` - Capture and retrieve personal knowledge. Sources: OpenClaw `2nd-brain`.
87. `research-paper-search` - Search papers and build literature sets. Sources: Hermes arXiv, OpenClaw academic research.
88. `research-paper-writing` - Structure ML/research papers and submissions. Sources: Hermes research-paper-writing.
89. `rss-and-blog-monitoring` - Monitor feeds and summarize updates. Sources: Hermes blogwatcher, OpenClaw RSS brief.
90. `youtube-content-summary` - Summarize transcripts into notes, blogs, and threads. Sources: Hermes YouTube content.
91. `knowledge-base-builder` - Build and query markdown knowledge bases. Sources: Hermes `llm-wiki`.
92. `citation-and-bib-cleanup` - Enrich bibliography entries and citations. Sources: OpenClaw abstract searcher.
93. `business-reporting` - Prepare BI reports from structured sources. Sources: OpenClaw business reporting.
94. `data-analysis-notebook` - Use notebook/live-kernel analysis. Sources: Hermes Jupyter live kernel.
95. `data-visualization` - Create charts, diagrams, and explanatory visuals. Sources: Hermes architecture diagrams, Anthropic canvas.

### Design, Media, and Artifacts

96. `frontend-design` - Build polished frontend interfaces. Sources: Anthropic `frontend-design`, Hermes popular web designs.
97. `web-artifact-builder` - Build rich HTML artifacts and prototypes. Sources: Anthropic `web-artifacts-builder`.
98. `theme-factory` - Apply or generate visual themes. Sources: Anthropic `theme-factory`.
99. `brand-guidelines` - Apply brand colors, typography, and rules. Sources: Anthropic `brand-guidelines`.
100. `canvas-design` - Create static visual designs. Sources: Anthropic `canvas-design`.
101. `algorithmic-art` - Create generative art with code. Sources: Anthropic `algorithmic-art`, Hermes p5js.
102. `architecture-diagrams` - Generate architecture and flow diagrams. Sources: Hermes architecture-diagram.
103. `excalidraw-diagrams` - Create hand-drawn diagram JSON. Sources: Hermes Excalidraw.
104. `infographic-design` - Turn complex data into infographics. Sources: Hermes baoyu-infographic.
105. `slack-gif-creation` - Create Slack-optimized animated GIFs. Sources: Anthropic `slack-gif-creator`.
106. `image-generation-workflow` - Plan image generation or editing workflows. Sources: Hermes ComfyUI, OpenClaw image generation category.
107. `video-generation-workflow` - Plan short video or animation workflows. Sources: Hermes Manim, ASCII video.
108. `presentation-design` - Improve narrative, visuals, and slide quality. Sources: Anthropic PPTX/theme skills.
109. `humanized-writing` - Make prose clear, natural, and less AI-generic. Sources: Hermes humanizer.
110. `creative-writing-and-songwriting` - Draft lyrics, music prompts, and creative text. Sources: Hermes songwriting.

### Security, Privacy, and Safe Integrations

111. `prompt-injection-screening` - Screen untrusted text for injection and exfiltration risks. Sources: OpenClaw `aegis-shield`.
112. `agent-access-control` - Apply stranger/group/channel access tiers. Sources: OpenClaw `agent-access-control`.
113. `approval-gated-external-actions` - Require human approval before purchases, sends, installs, or writes. Sources: OpenClaw Agent Passport/AgentGate.
114. `secrets-handling` - Prevent secret leakage in logs, prompts, files, and messages. Sources: Humungousaur policy and model-client redaction.
115. `dependency-security-check` - Check packages before install or execution. Sources: OpenClaw AgentAudit, Snyk scanner mention.
116. `skill-provenance-review` - Trace source, license, scripts, and trust level for skill packs. Sources: OpenClaw trust verifier.
117. `audit-trail-review` - Inspect audit logs and reconstruct task history. Sources: OpenClaw agent-audit-trail, Humungousaur audit DB.
118. `local-service-monitoring` - Monitor local services such as Ollama, browser backends, and daemons. Sources: OpenClaw active maintenance.
119. `network-and-dns-safety` - Review DNS/ad-block/privacy services before changing them. Sources: OpenClaw AdGuard/adblock DNS.
120. `safe-shopping-and-payments` - Prepare purchases/payment actions without executing unless approved. Sources: OpenClaw AgentPay/shopping category.

## Implementation Order

1. Standard and validator.
2. Core cognition and autonomy skills.
3. Voice/channel skills.
4. Browser/computer/OS skills.
5. Coding/Git skills.
6. Documents/data/research skills.
7. Design/media skills.
8. Security/privacy skills.
9. Scripts and references for skills that need executable helpers.
10. Catalog verification, import smoke, and model-led planning smoke.
