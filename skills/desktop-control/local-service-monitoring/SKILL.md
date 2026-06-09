---
name: local-service-monitoring
description: Monitor local services such as Ollama, browser backends, voice daemons, channels, and automation loops using native status tools and bounded checks.
---

# Local Service Monitoring

## Purpose

Keep local assistant services observable without hidden or noisy monitoring. This skill checks readiness and can create bounded wakeups/triggers when the user wants ongoing watch.

## When To Use

Use for Ollama, voice wakeup, browser live backend, automation daemon, channels, local servers, and provider readiness.

## Inputs And Evidence

- Service name, endpoint/process, expected state, check cadence, and alert behavior.
- Status tool output and logs if available.

## Tool Map

- `system_status`
- `external_integrations_status`
- `voice_provider_status`
- `browser_live_status`
- `channel_doctor`
- `cognitive_trigger_record`
- `activity_ingest`

## Workflow

1. Identify service and expected healthy state.
2. Use native status tools first.
3. Run bounded shell checks only when approved/needed.
4. Record gaps and next setup steps.
5. Create monitoring triggers only on user request.
6. Report health as current-time evidence, not permanent truth.

## Native Implementation Boundaries

- Use Humungousaur status/trigger tools.
- Do not import external reference active-maintenance code.
- Do not run hidden background loops.

## Safety And Approval

- Avoid exposing env/secrets in status.
- Starting/stopping services requires approval.
- Keep monitoring cadence reasonable.

## Verification

- Status outputs prove current readiness.
- Trigger IDs prove scheduled monitoring.
- Report unsupported checks.

## Failure Modes

- Saying a service is ready from catalog support.
- Creating noisy monitors.
- Ignoring resource limits.

## References

- Shortlist item: `local-service-monitoring`.
