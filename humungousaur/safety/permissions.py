from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.safety.policy import PolicyEngine
from humungousaur.tools import default_tools
from humungousaur.tools.file_tools import (
    ALLOWED_SHELL_COMMANDS,
    BLOCKED_INLINE_SHELL_TOKENS,
    SHELL_COMMAND_PROFILES,
    SHELL_TIMEOUT_SECONDS,
)
from humungousaur.tools.plugin_tools import discover_plugin_manifests, plugin_manifest_roots


RISK_RANK = {"low": 0, "medium": 1, "high": 2, "blocked": 3}


def permissions_snapshot(
    config: AgentConfig,
    settings: dict[str, Any] | None = None,
    index_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = config.normalized()
    policy = PolicyEngine()
    tools = []
    groups: dict[str, dict[str, Any]] = {}
    plugin_manifests = discover_plugin_manifests(normalized)
    for tool in sorted(default_tools(normalized).values(), key=lambda item: item.name):
        decision = policy.evaluate(tool, approved=False)
        approved_decision = policy.evaluate(tool, approved=True)
        group = groups.setdefault(
            tool.capability_group,
            {
                "name": tool.capability_group,
                "tools": 0,
                "requires_approval": 0,
                "allowed_without_approval": 0,
                "highest_risk": "low",
            },
        )
        group["tools"] += 1
        if decision.requires_approval:
            group["requires_approval"] += 1
        if decision.allowed:
            group["allowed_without_approval"] += 1
        if RISK_RANK[tool.risk_level.value] > RISK_RANK[group["highest_risk"]]:
            group["highest_risk"] = tool.risk_level.value
        tools.append(
            {
                "name": tool.name,
                "capability_group": tool.capability_group,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "requires_approval": decision.requires_approval,
                "allowed_without_approval": decision.allowed,
                "allowed_with_approval": approved_decision.allowed,
                "policy_reason": decision.reason,
                "input_schema": tool.input_schema,
            }
        )

    return {
        "workspace": str(normalized.workspace),
        "data_dir": str(normalized.data_dir),
        "dry_run": normalized.dry_run,
        "allowed_read_roots": [str(path) for path in normalized.allowed_read_roots],
        "extra_read_roots": list(settings.get("extra_read_roots", [])) if settings else [],
        "allowed_write_roots": [str(path) for path in normalized.allowed_write_roots],
        "limits": {
            "max_file_bytes": normalized.max_file_bytes,
            "max_search_results": normalized.max_search_results,
        },
        "shell": {
            "allowed_commands": list(ALLOWED_SHELL_COMMANDS),
            "command_profiles": list(SHELL_COMMAND_PROFILES),
            "blocked_inline_tokens": list(BLOCKED_INLINE_SHELL_TOKENS),
            "timeout_seconds": SHELL_TIMEOUT_SECONDS,
            "runs_in_workspace": True,
        },
        "plugins": {
            "roots": [str(path) for path in plugin_manifest_roots(normalized)],
            "manifest_count": len(plugin_manifests),
            "declared_tool_count": sum(1 for manifest in plugin_manifests for tool in manifest.tools if tool.valid),
            "invalid_manifest_count": sum(1 for manifest in plugin_manifests if manifest.errors),
            "execution": "manifest-declared tools are visible but blocked until a trusted runtime is installed",
        },
        "capability_groups": sorted(groups.values(), key=lambda item: item["name"]),
        "tools": tools,
        "index": index_status,
    }
