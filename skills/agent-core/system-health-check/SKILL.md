---
name: system-health-check
description: Check local system readiness, disks, environment, integrations, voice/browser/channel providers, and dependency health before or during agent workflows.
---

# System Health Check

## Purpose

Give the assistant a reliable view of local readiness before running complex tasks. This skill checks environment and integration health without pretending missing providers are working.

## When To Use

Use before end-to-end smoke tests, local model/voice/channel/browser setup, app troubleshooting, dependency diagnosis, or when the user asks whether the system is ready.

## Inputs And Evidence

- User's target workflow and required capabilities.
- System status, provider status, channel doctor output, external integration status, and browser readiness.
- Missing environment variables, binaries, models, or local services.

## Tool Map

- `system_status`
- `external_integrations_status`
- `voice_provider_status`
- `browser_live_status`
- `channel_doctor`
- `activity_policy`
- `tool_search`
- `capability_surface`
- `agent_skill_script_catalog`
- `agent_skill_script_run`

## Native Scripts

- `scripts/check_readiness.py`: collects workspace, data directory, Python runtime, skill count, and redacted environment-presence facts. Use through `agent_skill_script_run` when a compact local readiness snapshot is useful.

## Workflow

1. Identify the workflow being checked: voice, browser, OS control, channels, local models, or full agent.
2. Query the relevant native status tools.
3. Separate working, missing, disabled, unconfigured, and unsupported capabilities.
4. Recommend the smallest native setup step for each blocker.
5. Do not install or run external code unless the user approves the exact action.
6. Re-run targeted checks after fixes.

## Native Implementation Boundaries

- Use Humungousaur status and capability tools.
- Do not call upstream health-check scripts from external reference/external reference/Windows-use.
- Do not infer readiness from installed reference repos alone.

## Safety And Approval

- Status checks should not expose secrets; report presence/missing rather than raw values.
- Environment changes, installs, and service starts require approval where applicable.
- Avoid broad scans of private locations unless required.

## Verification

- Readiness claims must be backed by status tool output.
- Missing providers should be named with exact missing env/model/binary where available.
- Full readiness requires all required workflow surfaces to pass, not just one smoke.

## Failure Modes

- Saying "ready" when only dry-run mode passed.
- Confusing catalog support with configured runtime support.
- Ignoring local resource limits.

## References

- Shortlist item: `system-health-check`.
- Native source: Humungousaur status, capability, channel, browser, and voice tools.
