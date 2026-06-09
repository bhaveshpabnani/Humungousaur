---
name: approval-gated-external-actions
description: Require explicit human approval before purchases, messages, installs, file writes, remote API mutations, app control, or other irreversible actions.
---

# Approval Gated External Actions

## Purpose

Keep high-impact actions under human control. This skill applies the assistant's approval discipline across tools and workflows.

## When To Use

Use before sending messages, buying anything, installing packages, pushing code, deleting files, changing apps, mutating APIs, or posting publicly.

## Inputs And Evidence

- Exact action, target, payload, risk, tool schema, approval token/status, and expected result.
- Prior draft or prepared outbox item.

## Tool Map

- `tool_describe`
- `channel_message_prepare`
- `channel_message_send`
- `lobster_workflow_start`
- `lobster_workflow_approve`
- `message-approval-policy`

## Workflow

1. Identify whether action is external, irreversible, costly, destructive, or privacy-sensitive.
2. Prepare/review exact payload before execution.
3. Request approval through the native tool/workflow path.
4. Execute only after approval.
5. Verify final status.
6. Report blocked/pending states honestly.

## Native Implementation Boundaries

- Use Humungousaur approval queue, risk levels, and workflow tools.
- Do not import external reference AgentGate/AgentPay code.
- Any new high-risk tool must be native and approval-gated.

## Safety And Approval

- Approval is specific to exact action and payload.
- Edits after approval require re-review where risk changes.
- Never blur prepared into sent/executed.

## Verification

- Approval records or tool status prove state.
- Sent/executed claims require tool result.
- Rejections should be honored.

## Failure Modes

- Auto-executing because the task seems obvious.
- Changing payload after approval.
- Claiming pending actions completed.

## References

- Shortlist item: `approval-gated-external-actions`.
