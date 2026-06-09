# Security Policy

Humungousaur runs local tools that can touch files, browser sessions, desktop UI, shell commands, channels, memory, and voice providers. Please report security issues privately.

## Reporting

Open a private GitHub security advisory for `bhaveshpabnani/Humungousaur` or contact the maintainers directly before publishing details.

Include:

- affected version or commit
- operating system and app surface involved
- reproduction steps
- expected and actual behavior
- whether secrets, local files, approvals, audit logs, channels, or external sends are involved

## Security Expectations

- Do not include live API keys, tokens, credentials, or private user data in reports.
- Do not run destructive proofs of concept against another user's machine or accounts.
- Do not bypass approval gates, exfiltrate data, or trigger external sends beyond the minimum needed to demonstrate the issue.

## Supported Surfaces

The current security policy covers the Python agent runtime, REST API, CLI, local dashboard, Windows app, macOS app, bundled skills, channel gateway surfaces, and website release documentation.
