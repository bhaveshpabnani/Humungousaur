---
name: openclaw-capability-surfaces
description: Keep tools, skills, and plugins separated while building broad assistant capabilities.
---

# OpenClaw Capability Surfaces

Use this skill when designing or integrating broad assistant capabilities inspired by OpenClaw-style Gateway architecture.

Concepts:

- Tools are callable typed actions such as file operations, browser actions, voice transcription, speech synthesis, or message preparation.
- Skills are reusable instructions, workflows, review rubrics, and operating constraints.
- Plugins add runtime capabilities such as tools, model providers, speech, realtime voice, channels, hooks, and packaged skills.

Workflow:

1. Add callable behavior as a typed tool with a schema, risk level, policy check, audit result, and tests.
2. Add reusable knowledge as a `SKILL.md` pack and import it into cognitive skill memory only through exact skill ids.
3. Add external runtimes through plugin manifests or trusted adapters; keep untrusted declared tools blocked.
4. Let model-led planning choose from schemas and structured context.
5. Keep deterministic code limited to validation, persistence, catalogs, safety gates, and explicit fallback commands.

Verification:

- Check that broad natural-language behavior is not implemented with regex, keyword maps, or hardcoded intent routes.
- Check that missing credentials or runtimes produce clear blocked or failed results.
- Check that the tool registry exposes schemas for every new callable capability.
