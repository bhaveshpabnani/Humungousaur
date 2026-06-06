---
name: network-and-dns-safety
description: Review DNS, proxy, ad-block, firewall, tunnel, and network changes safely before applying them, with rollback and privacy awareness.
---

# Network And DNS Safety

## Purpose

Network changes can break connectivity or leak data. This skill keeps diagnosis and changes cautious, explicit, and reversible.

## When To Use

Use for DNS/ad-block/privacy services, proxy settings, tunnels, firewall rules, network failures, and connectivity-sensitive setup.

## Inputs And Evidence

- Desired change, current error, OS/network context, target domain/service, and rollback plan.
- System status and approved diagnostic commands.

## Tool Map

- `system_status`
- `run_shell_command`
- `web-data-extraction`
- `local-service-monitoring`
- `secrets-handling`

## Workflow

1. Clarify the problem or desired network change.
2. Gather non-destructive diagnostics first.
3. Identify privacy/security impact.
4. Propose a minimal reversible change.
5. Apply only after approval.
6. Verify connectivity and rollback path.

## Native Implementation Boundaries

- Use native shell/status tools when approved.
- Do not import OpenClaw AdGuard/DNS plugins.
- Do not modify network settings through hidden scripts.

## Safety And Approval

- Network changes require explicit user approval.
- Avoid logging sensitive domains/tokens.
- Keep rollback instructions.

## Verification

- Before/after diagnostics should be recorded.
- Confirm target service behavior.
- Report if admin privileges blocked action.

## Failure Modes

- Breaking global DNS for a local issue.
- No rollback.
- Exposing private browsing/service targets.

## References

- Shortlist item: `network-and-dns-safety`.
