# Changelog

All notable public changes to Humungousaur are tracked here.

This project follows a practical release-log style: user-visible capabilities, safety changes, release-process changes, and known blockers are more important than internal implementation churn.

## 0.1.0 - Unreleased

### Highlights

- Added the first public open-source README focused on Humungousaur's real-world cognition capabilities, desktop surfaces, safety defaults, and contributor path.
- Added native Windows and macOS desktop shells around the shared local REST API.
- Added governed tool contracts across files, browser, channels, voice, cognition, memory, OS, plugins, skills, research, media, productivity, and workflow surfaces.
- Added durable cognition layers for goals, tasks, focus, commitments, environment records, priorities, wakeups, triggers, memory, learning, reflection, recovery, persona evolution, skill evolution, and autonomous cycles.
- Added workspace `SKILL.md` packs with validation and smoke coverage for agent-core, browser-web, commerce-travel, communications, creative-design, delegation-agents, desktop-control, integrations, office-productivity, software-engineering, and voice-media.
- Added release-readiness scripts for open-source hygiene, desktop parity, shared desktop runtime smoke, release report generation, publication-state checks, macOS packaging, Windows packaging, and GitHub release asset verification.

### Safety

- High-risk tools use explicit approval gates and audit timelines.
- Browser mutation, desktop UI actions, screenshots, shell/code execution, app launches, external sends, and local state deletion are bounded by policy.
- Open-source hygiene scans publish candidates for local state, likely secrets, signing material, generated Codex state, and oversized files.
- Release workflows are designed with least-privilege permissions and separate platform packaging gates.

### Known Release Blockers

- Public release assets are not complete until the Windows package is produced on Windows or GitHub Actions, both platform zips are attached to the tagged GitHub release, and `checksums.txt` includes both rows.
- Live credentialed channel, voice, Google Workspace, and provider-specific workflows require test accounts/secrets before they can be claimed as fully end-to-end.
- Public announcement should wait for strict release readiness, website publication checks, and live release asset verification.
