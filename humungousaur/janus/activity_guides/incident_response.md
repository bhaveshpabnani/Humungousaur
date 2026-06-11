# Activity Skill Pack: Incident Response

## Summary

Use when the user is investigating, coordinating, mitigating, communicating, or
reviewing a service, security, operations, or workflow incident. Optimize for
timeline continuity, escalation awareness, and approval-gated access.

## Signals

- Alert, monitor, outage, error-rate, latency, deployment, rollback, status page,
  on-call, runbook, log, dashboard, or incident channel activity.
- Repeated switching among alerts, dashboards, logs, code, deploys, chats,
  runbooks, and status updates.
- Escalation, acknowledgement, mitigation, handoff, resolution, or post-incident
  artifact events.

## Helpful Moments

- A new alert or escalation appears and safe context can reduce orientation cost.
- The user returns during an active incident and may need a compact timeline.
- Mitigation or resolution occurs and a handoff, status update, or postmortem
  draft may help.
- The user explicitly asks for timeline, runbook context, impact summary, or next
  steps.

## Stay Silent When

- Alerts are noisy, auto-resolved, background-only, or unrelated to user focus.
- Assistance would require reading logs, dashboards, customer data, secrets,
  vulnerability details, infrastructure config, or private chats without approval.
- The incident is security-sensitive or compliance-sensitive and no permission is
  available.
- The user is actively mitigating and interruption could increase risk.

## Deep Dive Triggers

- Reading logs, traces, dashboards, alerts, runbooks, deployment details,
  credentials-adjacent config, customer reports, or incident communications.
- Suggesting remediation, rollback, external communication, status updates, or
  postmortem content.
- Taking operational actions or modifying infrastructure, deploys, monitors, or
  incident records.

## Memory Guidance

- Store redacted incident/service hashes, broad incident class, severity category,
  phase, safe timestamps, mitigation state, handoff state, and explicit decisions.
- Remember timeline milestones from safe metadata or approved content.
- Do not retain logs, customer data, hostnames, IPs, secrets, vulnerability
  details, private messages, or exact service names without approval.

## Privacy Notes

- Treat incidents as high-sensitivity by default.
- Ask before reading operational content or taking action.
- Prefer timeline skeletons, phase labels, and redacted state over raw evidence.
