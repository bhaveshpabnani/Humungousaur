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

- `dns_lookup`
- `http_endpoint_check`
- `tcp_connectivity_probe`
- `system_status`
- `run_shell_command`
- `web-data-extraction`
- `local-service-monitoring`
- `secrets-handling`

## Workflow

1. Clarify the problem or desired network change.
2. Use `dns_lookup`, `http_endpoint_check`, and `tcp_connectivity_probe` for bounded native diagnostics before shell commands.
3. Gather non-destructive diagnostics first.
4. Identify privacy/security impact.
5. Propose a minimal reversible change.
6. Apply changes only after approval.
7. Verify connectivity and rollback path.

## Native Implementation Boundaries

- Use native shell/status tools when approved.
- Do not import external reference AdGuard/DNS plugins.
- Do not modify network settings through hidden scripts.
- Native network tools are diagnostic only; they do not edit DNS, proxy, firewall, tunnel, or adapter settings.
- TCP probing is limited to a single host and port, not scan ranges.

## Safety And Approval

- Network changes require explicit user approval.
- Avoid logging sensitive domains/tokens.
- Keep rollback instructions.

## Verification

- Before/after diagnostics should be recorded.
- DNS diagnostics should report resolved state, address records, and address classification.
- HTTP diagnostics should report status, redirects, TLS metadata, headers, and errors.
- TCP diagnostics should report reachable state for the single requested host and port.
- Confirm target service behavior.
- Report if admin privileges blocked action.

## Failure Modes

- Breaking global DNS for a local issue.
- No rollback.
- Exposing private browsing/service targets.

## References

- Shortlist item: `network-and-dns-safety`.
