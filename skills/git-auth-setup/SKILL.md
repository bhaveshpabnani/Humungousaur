---
name: git-auth-setup
description: Diagnose and guide GitHub/Git authentication for HTTPS tokens, SSH keys, credential helpers, and gh login without exposing secrets.
---

# Git Auth Setup

## Purpose

Help the user make Git and GitHub authentication work while keeping credentials private. This skill diagnoses auth state and gives setup steps or runs approved safe commands.

## When To Use

Use when clone, fetch, push, gh, SSH, HTTPS token, credential manager, or permission errors block repo work.

## Inputs And Evidence

- Error output, remote URL, auth method, platform, and intended operation.
- `git remote -v`, `gh auth status`, SSH test output, and credential-helper config when approved.

## Tool Map

- `run_shell_command`
- `read_file`
- `system_status`
- `github-repo-management`

## Workflow

1. Identify whether Git uses HTTPS, SSH, or gh auth.
2. Inspect non-secret config and current error output.
3. Recommend the least invasive fix: gh login, credential-manager refresh, SSH key setup, or remote URL update.
4. Never ask the user to paste secrets into chat.
5. Run auth commands only when the user approves interactive/setup work.
6. Verify with a safe read or status command before retrying the original operation.

## Native Implementation Boundaries

- Use native Git/gh/ssh commands through approved shell tooling.
- Do not import Hermes auth scripts.
- Do not store tokens in files managed by skills.

## Safety And Approval

- Treat tokens, private keys, and credential-helper output as secrets.
- Avoid printing sensitive values.
- Do not change remotes or credential helpers without approval.

## Verification

- Auth success should be proven by `gh auth status`, `ssh -T` style output, or a safe Git command.
- Push readiness is separate from permission to push.
- Report remaining permission blockers exactly.

## Failure Modes

- Exposing a token in logs.
- Fixing the wrong account.
- Retrying pushes without user intent.

## References

- Shortlist item: `git-auth-setup`.
- Native path: GitHub CLI/Git through Humungousaur shell tooling.
