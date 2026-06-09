from __future__ import annotations

from dataclasses import asdict
import os
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema
from humungousaur.tools.validation import ToolInputValidationError, validate_tool_input


CAPABILITY_SURFACES: tuple[dict[str, Any], ...] = (
    {
        "surface_id": "runtime",
        "display_name": "Runtime",
        "groups": ["shell", "code", "system"],
        "expected_tools": ["run_shell_command", "python_interpreter", "system_status"],
        "purpose": "Run commands, execute bounded code, inspect local runtime health, and manage process-like local work.",
    },
    {
        "surface_id": "files",
        "display_name": "Files",
        "groups": ["files"],
        "expected_tools": ["list_files", "read_file", "write_note", "search_workspace"],
        "purpose": "Read, search, summarize, and write approved workspace artifacts.",
    },
    {
        "surface_id": "web",
        "display_name": "Web",
        "groups": ["browser"],
        "expected_tools": ["fetch_web_page", "research_web_pages", "browser_live_search", "browser_live_extract"],
        "purpose": "Fetch pages, research provided URLs, and search or navigate with browser-backed tools.",
    },
    {
        "surface_id": "browser",
        "display_name": "Browser",
        "groups": ["browser"],
        "expected_tools": ["browser_open", "browser_observe", "browser_extract", "browser_live_open", "browser_live_observe", "browser_live_extract"],
        "purpose": "Operate static and live browser views with observation-first, approval-gated actions.",
    },
    {
        "surface_id": "messaging_channels",
        "display_name": "Messaging And Channels",
        "groups": ["channels"],
        "expected_tools": [
            "channel_catalog",
            "channel_manifest",
            "channel_setup_status",
            "channel_listener_status",
            "channel_listener_tick",
            "channel_webhook_ingest",
            "channel_message_prepare",
            "channel_message_send",
        ],
        "purpose": "Receive, listen to, prepare, and optionally send messages through configured chat and voice-call channels.",
    },
    {
        "surface_id": "sessions_agents",
        "display_name": "Sessions And Agents",
        "groups": ["cognition", "codex"],
        "expected_tools": ["cognitive_state", "autonomous_queue_status", "multi_agent_board", "multi_agent_coordinate", "codex_cli_plan", "codex_cli_run"],
        "purpose": "Inspect current work, delegate coding tasks, and coordinate durable agent state.",
    },
    {
        "surface_id": "automation",
        "display_name": "Automation",
        "groups": ["cognition"],
        "expected_tools": ["cognitive_wakeup_schedule", "cognitive_trigger_record", "autonomous_event_submit", "autonomous_cycle_run", "automation_daemon_status", "automation_daemon_configure", "automation_daemon_tick"],
        "purpose": "Schedule wakeups, evaluate structured triggers, and run bounded autonomous cycles.",
    },
    {
        "surface_id": "gateway_nodes",
        "display_name": "Gateway And Nodes",
        "groups": ["channels", "plugins", "system"],
        "expected_tools": ["channel_doctor", "plugin_setup_plan", "system_status"],
        "purpose": "Inspect channel setup, runtime readiness, local host state, and future node-style adapters.",
    },
    {
        "surface_id": "media_voice",
        "display_name": "Media And Voice",
        "groups": ["voice", "screen"],
        "expected_tools": ["voice_provider_status", "voice_transcribe", "voice_response_prepare", "voice_speak", "screenshot_capture"],
        "purpose": "Transcribe audio, prepare or speak responses, and capture approved local visual evidence.",
    },
    {
        "surface_id": "skills",
        "display_name": "Skills",
        "groups": ["skills", "codex", "cognition"],
        "expected_tools": [
            "agent_skill_catalog",
            "agent_skill_read",
            "agent_skill_import",
            "agent_skill_script_catalog",
            "agent_skill_script_read",
            "agent_skill_script_run",
            "codex_skill_catalog",
            "cognitive_skill_evolve",
            "skill_forge_draft",
            "skill_forge_packs",
        ],
        "purpose": "Discover reusable workflow instructions, run native skill capability scripts, import selected skills, and evolve durable skill memory.",
    },
    {
        "surface_id": "plugins",
        "display_name": "Plugins",
        "groups": ["plugins"],
        "expected_tools": ["plugin_catalog", "plugin_setup_plan", "plugin_manifests", "plugin_manifest", "plugin_state"],
        "purpose": "Expose Humungousaur-owned capability contracts plus local blocked plugin declarations and enablement state.",
    },
    {
        "surface_id": "native_toolsets_mcp",
        "display_name": "Native Toolsets And MCP",
        "groups": ["toolsets", "mcp", "providers", "runtime"],
        "expected_tools": [
            "native_toolset_catalog",
            "native_toolset_describe",
            "mcp_server_catalog",
            "mcp_server_manifest",
            "mcp_server_launch",
            "mcp_tool_discover",
            "mcp_tool_call",
            "mcp_oauth_status",
            "provider_registry",
            "runtime_hook_catalog",
        ],
        "purpose": "Expose native toolset records, MCP server manifests, provider readiness, and observer hook contracts.",
    },
    {
        "surface_id": "large_catalog_search",
        "display_name": "Large Catalog Search",
        "groups": ["capabilities"],
        "expected_tools": ["tool_search", "tool_describe", "capability_surface"],
        "purpose": "Search and describe the effective tool, skill, plugin, channel, and provider catalog without loading every detail into a prompt.",
    },
    {
        "surface_id": "workflow_plugins",
        "display_name": "Workflow Plugins",
        "groups": ["workflow", "capabilities"],
        "expected_tools": [
            "diff_render",
            "llm_task_json",
            "tokenjuice_compact",
            "lobster_workflow_start",
            "lobster_workflow_status",
            "lobster_workflow_approve",
            "canvas_a2ui_create",
            "canvas_a2ui_render",
            "tool_search",
        ],
        "purpose": "Render diffs, run JSON-only LLM workflow steps, compact noisy output, resume approval workflows, and create A2UI canvas artifacts.",
    },
    {
        "surface_id": "policy_safety",
        "display_name": "Policy And Safety",
        "groups": ["system", "activity", "browser", "screen", "shell", "os", "channels"],
        "expected_tools": ["system_status", "activity_policy", "browser_forget_session", "screen_capture_delete", "channel_doctor"],
        "purpose": "Keep permissions, approvals, privacy boundaries, and high-risk local actions explicit.",
    },
    {
        "surface_id": "memory_cognition",
        "display_name": "Memory And Cognition",
        "groups": ["memory", "cognition", "activity"],
        "expected_tools": ["memory_write", "memory_search", "memory_summary", "cognitive_state", "cognitive_memory_curate"],
        "purpose": "Persist, retrieve, curate, learn from, and forget local assistant memory.",
    },
)


class CapabilitySurfaceTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="capability_surface",
            description=(
                "Summarize the effective Humungousaur capability surface across tools, skills, plugins, "
                "channels, model providers, voice providers, automation, policy, memory, and delegation."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "include_records": {
                        "type": "boolean",
                        "description": "Include compact searchable catalog records for tools, skills, plugins, and channels.",
                    },
                    "include_tool_schemas": {
                        "type": "boolean",
                        "description": "Include full tool input schemas in returned tool records.",
                    },
                }
            ),
            capability_group="capabilities",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        surface = build_capability_surface(
            config,
            include_records=bool(tool_input.get("include_records", False)),
            include_tool_schemas=bool(tool_input.get("include_tool_schemas", False)),
        )
        missing_contracts = surface["integrity"]["missing_plugin_declared_tools"]
        status = "ready" if not missing_contracts else "needs_attention"
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Capability surface is {status}: {surface['counts']['tools']} tools, {surface['counts']['workspace_skills']} workspace skills, {surface['counts']['channels']} channels.",
            surface,
        )


class ToolSearchTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="tool_search",
            description=(
                "Search the effective capability catalog for exact tools, skills, plugins, channels, and providers. "
                "This is catalog retrieval only; broad task routing remains model-led."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "query": {"type": "string", "description": "Catalog search text such as voice, Slack, browser, approval, or wakeup."},
                    "kind": {
                        "type": "string",
                        "enum": ["all", "tool", "skill", "plugin", "channel", "surface", "provider", "toolset", "mcp_server"],
                        "description": "Optional record kind filter.",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "include_tool_schemas": {"type": "boolean", "description": "Include full tool input schemas in matching tool records."},
                },
                required=["query"],
            ),
            capability_group="capabilities",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        query = str(tool_input.get("query", "")).strip()
        if not query:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Catalog search query is required.")
        kind = str(tool_input.get("kind") or "all").strip().lower() or "all"
        limit = max(1, min(int(tool_input.get("limit") or 10), 50))
        records = capability_records(config, include_tool_schemas=bool(tool_input.get("include_tool_schemas", False)))
        if kind != "all":
            records = [record for record in records if record["kind"] == kind]
        matches = _search_records(query, records, limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(matches)} catalog match(es).",
            {
                "query": query,
                "kind": kind,
                "matches": matches,
                "safety_note": "Catalog search is not an intent router and does not execute tools.",
            },
        )


class ToolDescribeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="tool_describe",
            description="Describe one exact catalog record from tool_search, such as tool:voice_speak, plugin:channels.slack, or channel:whatsapp.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "record_id": {"type": "string", "description": "Exact record id returned by tool_search."},
                    "include_tool_schema": {"type": "boolean", "description": "Include full tool input schema for tool records."},
                },
                required=["record_id"],
            ),
            capability_group="capabilities",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        record_id = str(tool_input.get("record_id", "")).strip()
        if not record_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "record_id is required.")
        include_schema = bool(tool_input.get("include_tool_schema", True))
        for record in capability_records(config, include_tool_schemas=include_schema):
            if record["record_id"] == record_id:
                return ToolResult(
                    self.name,
                    ActionStatus.SUCCEEDED,
                    self.risk_level,
                    f"Described {record_id}.",
                    {"record": record, "safety_note": "Description is catalog metadata only and does not execute tools."},
                )
        return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown catalog record: {record_id}")


class ToolCallTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="tool_call",
            description=(
                "Invoke an available tool by exact name after discovering it through tool_search/tool_describe. "
                "This is the Humungousaur native equivalent of deferred tool invocation."
            ),
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "name": {"type": "string", "description": "Exact tool name to invoke."},
                    "arguments": {"type": "object", "description": "Arguments matching the target tool schema."},
                    "approved": {"type": "boolean", "description": "Set only after approval for approval-required target tools."},
                },
                required=["name", "arguments"],
            ),
            capability_group="capabilities",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        target_name = str(tool_input.get("name") or "").strip()
        if not target_name:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Target tool name is required.")
        if target_name in {"tool_call", "tool_search", "tool_describe", "capability_surface"}:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, f"tool_call cannot invoke bridge tool {target_name}.")
        arguments = tool_input.get("arguments")
        if not isinstance(arguments, dict):
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "tool_call arguments must be an object.")
        tools = _tool_registry(config)
        target = tools.get(target_name)
        if target is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown target tool: {target_name}.")
        if target.requires_approval and not bool(tool_input.get("approved", False)):
            return ToolResult(
                self.name,
                ActionStatus.NEEDS_APPROVAL,
                target.risk_level,
                f"Target tool {target_name} requires approval.",
                {"target_tool": target_name, "target_arguments": arguments, "target_risk_level": target.risk_level},
            )
        try:
            validate_tool_input(arguments, target.input_schema)
        except ToolInputValidationError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, target.risk_level, f"Invalid arguments for {target_name}.", error=str(exc))
        result = target.execute(arguments, config)
        return ToolResult(
            self.name,
            result.status,
            result.risk_level,
            f"Invoked {target_name}: {result.summary}",
            {"target_tool": target_name, "target_result": result.output},
            result.error,
        )


def default_capability_tools() -> dict[str, Tool]:
    tools: list[Tool] = [CapabilitySurfaceTool(), ToolSearchTool(), ToolDescribeTool(), ToolCallTool()]
    return {tool.name: tool for tool in tools}


def build_capability_surface(
    config: AgentConfig,
    *,
    include_records: bool = False,
    include_tool_schemas: bool = False,
) -> dict[str, Any]:
    normalized = config.normalized()
    _load_workspace_environment(normalized)
    tools = _tool_registry(normalized)
    workspace_skills = _workspace_skills(normalized)
    memory_skills = _memory_skills(normalized)
    plugins = _plugin_catalog()
    channels = _channel_catalog()
    voice_status = _voice_status(normalized)
    plugin_contracts = _plugin_tool_contracts(plugins, set(tools))
    groups = _tool_groups(tools)
    native_parity = _native_parity_status(normalized, tools)
    surface = {
        "workspace": str(normalized.workspace),
        "data_dir": str(normalized.data_dir),
        "counts": {
            "tools": len(tools),
            "tool_groups": len(groups),
            "workspace_skills": len(workspace_skills),
            "memory_skills": len(memory_skills),
            "plugins": len(plugins),
            "channels": len(channels),
            "native_toolsets": native_parity["toolset_count"],
            "mcp_servers": native_parity["mcp_server_count"],
        },
        "surfaces": [_surface_status(item, tools, groups) for item in CAPABILITY_SURFACES],
        "tool_groups": groups,
        "voice": voice_status,
        "model_providers": _model_provider_status(plugins),
        "channels": _channel_summary(channels),
        "plugins": _plugin_summary(plugins),
        "native_parity": native_parity,
        "skills": {
            "workspace": workspace_skills[:24],
            "memory": memory_skills[:24],
        },
        "integrity": {
            "missing_plugin_declared_tools": plugin_contracts["missing"],
            "available_plugin_declared_tools": plugin_contracts["available"],
            "note": "Missing items indicate catalog contract drift, not runtime execution.",
        },
        "policy_boundary": {
            "model_led_routing": True,
            "catalog_search_only": True,
            "high_risk_actions_require_approval": True,
            "no_natural_language_regex_routing": True,
        },
    }
    if include_records:
        surface["records"] = capability_records(normalized, include_tool_schemas=include_tool_schemas)
    return surface


def capability_records(config: AgentConfig, *, include_tool_schemas: bool = False) -> list[dict[str, Any]]:
    normalized = config.normalized()
    _load_workspace_environment(normalized)
    tools = _tool_registry(normalized)
    records: list[dict[str, Any]] = []
    for tool in sorted(tools.values(), key=lambda item: item.name):
        record = {
            "record_id": f"tool:{tool.name}",
            "kind": "tool",
            "name": tool.name,
            "display_name": tool.name,
            "description": tool.description,
            "capability_group": tool.capability_group,
            "risk_level": tool.risk_level.value,
            "requires_approval": tool.requires_approval,
            "status": "implemented",
            "schema_summary": _schema_summary(tool.input_schema),
        }
        if include_tool_schemas:
            record["input_schema"] = tool.input_schema
        records.append(_with_search_text(record))
    for skill in _workspace_skills(normalized):
        records.append(
            _with_search_text(
                {
                    "record_id": f"skill:{skill['skill_id']}",
                    "kind": "skill",
                    "name": skill["skill_id"],
                    "display_name": skill["name"],
                    "description": skill.get("description", ""),
                    "status": "workspace",
                    "relative_path": skill.get("relative_path", ""),
                }
            )
        )
    for skill in _memory_skills(normalized):
        records.append(
            _with_search_text(
                {
                    "record_id": f"skill:{skill.get('skill_id', skill.get('name', ''))}",
                    "kind": "skill",
                    "name": str(skill.get("skill_id") or skill.get("name") or ""),
                    "display_name": str(skill.get("name") or ""),
                    "description": str(skill.get("purpose") or skill.get("when_to_use") or ""),
                    "status": str(skill.get("status") or "memory"),
                    "tools": skill.get("tools", []),
                }
            )
        )
    for plugin in _plugin_catalog():
        records.append(
            _with_search_text(
                {
                    "record_id": f"plugin:{plugin.get('plugin_id', '')}",
                    "kind": "plugin",
                    "name": plugin.get("plugin_id", ""),
                    "display_name": plugin.get("display_name", ""),
                    "description": _plugin_description(plugin),
                    "status": plugin.get("status", ""),
                    "plugin_kind": plugin.get("kind", ""),
                    "tools": plugin.get("tools", []),
                    "skills": plugin.get("skills", []),
                    "channels": plugin.get("channels", []),
                    "providers": plugin.get("providers", []),
                    "setup": _setup_summary(plugin.get("setup", {})),
                    "contracts": plugin.get("contracts", {}),
                }
            )
        )
        for provider in plugin.get("providers", []) if isinstance(plugin.get("providers"), list) else []:
            records.append(
                _with_search_text(
                    {
                        "record_id": f"provider:{provider}",
                        "kind": "provider",
                        "name": provider,
                        "display_name": str(provider).replace("_", " ").title(),
                        "description": f"Provider exposed by {plugin.get('plugin_id', '')}.",
                        "status": plugin.get("status", ""),
                        "plugin_id": plugin.get("plugin_id", ""),
                    }
                )
            )
    for channel in _channel_catalog():
        records.append(
            _with_search_text(
                {
                    "record_id": f"channel:{channel.get('channel_id', '')}",
                    "kind": "channel",
                    "name": channel.get("channel_id", ""),
                    "display_name": channel.get("display_name", channel.get("name", "")),
                    "description": channel.get("transport", ""),
                    "status": channel.get("plugin_status", ""),
                    "setup_kind": channel.get("setup_kind", ""),
                    "supports_text": bool(channel.get("supports_text", False)),
                    "supports_media": bool(channel.get("supports_media", False)),
                    "supports_reactions": bool(channel.get("supports_reactions", False)),
                    "delivery": channel.get("delivery", {}),
                    "policies": channel.get("policies", {}),
                }
            )
        )
    for toolset in _native_toolset_records(normalized, tools):
        records.append(_with_search_text(toolset))
    for server in _mcp_server_records(normalized):
        records.append(_with_search_text(server))
    for surface in CAPABILITY_SURFACES:
        records.append(
            _with_search_text(
                {
                    "record_id": f"surface:{surface['surface_id']}",
                    "kind": "surface",
                    "name": surface["surface_id"],
                    "display_name": surface["display_name"],
                    "description": surface["purpose"],
                    "groups": surface["groups"],
                    "expected_tools": surface["expected_tools"],
                    "status": _surface_status(surface, tools, _tool_groups(tools))["status"],
                }
            )
        )
    return records


def _tool_registry(config: AgentConfig) -> dict[str, Tool]:
    from humungousaur.tools import default_tools

    return default_tools(config)


def _load_workspace_environment(config: AgentConfig) -> None:
    try:
        from humungousaur.env import load_workspace_environment

        load_workspace_environment(config.workspace)
    except Exception:
        return


def _workspace_skills(config: AgentConfig) -> list[dict[str, Any]]:
    try:
        from humungousaur.tools.skill_tools import discover_workspace_skills

        return [skill.summary() for skill in discover_workspace_skills(config)]
    except Exception:
        return []


def _memory_skills(config: AgentConfig) -> list[dict[str, Any]]:
    try:
        from humungousaur.cognition.skills import SkillStore

        return [asdict(skill) for skill in SkillStore(config.skill_library_path).list(limit=100, include_retired=False)]
    except Exception:
        return []


def _plugin_catalog() -> list[dict[str, Any]]:
    try:
        from humungousaur.tools.plugin_tools import load_plugin_catalog

        return load_plugin_catalog()
    except Exception:
        return []


def _channel_catalog() -> list[dict[str, Any]]:
    try:
        from humungousaur.integrations.channels import load_channel_catalog

        return load_channel_catalog()
    except Exception:
        return []


def _voice_status(config: AgentConfig) -> dict[str, Any]:
    try:
        from humungousaur.tools.voice_tools import VoiceProviderStatusTool

        result = VoiceProviderStatusTool().execute({}, config)
        return {"status": result.status.value, "summary": result.summary, **result.output}
    except Exception as exc:
        return {"status": "failed", "summary": str(exc)}


def _tool_groups(tools: dict[str, Tool]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for tool in tools.values():
        group = groups.setdefault(
            tool.capability_group,
            {"name": tool.capability_group, "tool_count": 0, "approval_required_count": 0, "risk_levels": {}},
        )
        group["tool_count"] += 1
        if tool.requires_approval:
            group["approval_required_count"] += 1
        risk_levels = group["risk_levels"]
        risk_levels[tool.risk_level.value] = risk_levels.get(tool.risk_level.value, 0) + 1
    return [groups[name] for name in sorted(groups)]


def _surface_status(surface: dict[str, Any], tools: dict[str, Tool], groups: list[dict[str, Any]]) -> dict[str, Any]:
    tool_names = set(tools)
    group_names = {group["name"] for group in groups}
    expected = [str(item) for item in surface.get("expected_tools", [])]
    missing = [name for name in expected if name not in tool_names]
    present = [name for name in expected if name in tool_names]
    groups_present = [name for name in surface.get("groups", []) if name in group_names]
    if expected and not missing:
        status = "implemented"
    elif present or groups_present:
        status = "partial"
    else:
        status = "missing"
    return {
        "surface_id": surface["surface_id"],
        "display_name": surface["display_name"],
        "status": status,
        "purpose": surface["purpose"],
        "groups": surface["groups"],
        "present_tools": present,
        "missing_expected_tools": missing,
        "group_count": sum(1 for group in groups if group["name"] in surface.get("groups", [])),
    }


def _channel_summary(channels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "channel_id": channel.get("channel_id", ""),
            "display_name": channel.get("display_name", channel.get("name", "")),
            "setup_kind": channel.get("setup_kind", ""),
            "status": channel.get("plugin_status", ""),
            "supports_text": bool(channel.get("supports_text", False)),
            "supports_media": bool(channel.get("supports_media", False)),
            "direct_send": bool(
                isinstance(channel.get("delivery"), dict)
                and isinstance(channel["delivery"].get("official_send"), dict)
                and channel["delivery"]["official_send"].get("implemented", False)
            ),
            "ambient": bool(isinstance(channel.get("policies"), dict) and channel["policies"].get("ambient_room_events_supported", False)),
            "bot_loop_protection": bool(isinstance(channel.get("policies"), dict) and channel["policies"].get("bot_loop_protection_supported", False)),
        }
        for channel in channels
    ]


def _plugin_summary(plugins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "plugin_id": plugin.get("plugin_id", ""),
            "display_name": plugin.get("display_name", ""),
            "kind": plugin.get("kind", ""),
            "status": plugin.get("status", ""),
            "tools": plugin.get("tools", []),
            "skills": plugin.get("skills", []),
            "channels": plugin.get("channels", []),
            "providers": plugin.get("providers", []),
            "setup": _setup_summary(plugin.get("setup", {})),
        }
        for plugin in plugins
    ]


def _model_provider_status(plugins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    providers = []
    for plugin in plugins:
        if plugin.get("kind") != "model_provider":
            continue
        setup = plugin.get("setup", {}) if isinstance(plugin.get("setup"), dict) else {}
        required_env = [str(item) for item in setup.get("required_env", []) if str(item)] if isinstance(setup.get("required_env"), list) else []
        providers.append(
            {
                "plugin_id": plugin.get("plugin_id", ""),
                "display_name": plugin.get("display_name", ""),
                "status": plugin.get("status", ""),
                "required_env": required_env,
                "configured": all(os.environ.get(name) for name in required_env),
                "contracts": plugin.get("contracts", {}),
            }
        )
    return providers


def _plugin_tool_contracts(plugins: list[dict[str, Any]], tool_names: set[str]) -> dict[str, list[dict[str, str]]]:
    missing: list[dict[str, str]] = []
    available: list[dict[str, str]] = []
    for plugin in plugins:
        plugin_id = str(plugin.get("plugin_id", ""))
        tools = plugin.get("tools", [])
        if not isinstance(tools, list):
            continue
        for tool_name in [str(item) for item in tools if str(item)]:
            record = {"plugin_id": plugin_id, "tool_name": tool_name}
            if tool_name in tool_names:
                available.append(record)
            else:
                missing.append(record)
    return {"missing": missing, "available": available}


def _native_parity_status(config: AgentConfig, tools: dict[str, Tool]) -> dict[str, Any]:
    try:
        from humungousaur.tools.native_parity.implementation import NATIVE_ALIAS_MAP, _load_mcp_manifests, _load_toolsets, _toolset_status

        toolsets = [_toolset_status(name, definition, tools) for name, definition in _load_toolsets(config).items()]
        mcp_servers = _load_mcp_manifests(config)
        missing_tools = sorted({tool for record in toolsets for tool in record["missing_tools"]})
        return {
            "toolset_count": len(toolsets),
            "implemented_toolsets": sum(1 for record in toolsets if record["status"] == "implemented"),
            "partial_toolsets": sum(1 for record in toolsets if record["status"] == "partial"),
            "missing_exact_tools": missing_tools,
            "missing_exact_tool_count": len(missing_tools),
            "alias_map": NATIVE_ALIAS_MAP,
            "mcp_server_count": len(mcp_servers),
            "mcp_servers": [
                {
                    "server_id": str(server.get("server_id", "")),
                    "status": str(server.get("status", "")),
                    "transport": str(server.get("transport", "")),
                    "tool_count": len(server.get("tools", [])) if isinstance(server.get("tools"), list) else 0,
                }
                for server in mcp_servers
            ],
        }
    except Exception as exc:
        return {
            "toolset_count": 0,
            "implemented_toolsets": 0,
            "partial_toolsets": 0,
            "missing_exact_tools": [],
            "missing_exact_tool_count": 0,
            "alias_map": {},
            "mcp_server_count": 0,
            "mcp_servers": [],
            "error": str(exc),
        }


def _native_toolset_records(config: AgentConfig, tools: dict[str, Tool]) -> list[dict[str, Any]]:
    try:
        from humungousaur.tools.native_parity.implementation import _load_toolsets, _toolset_status

        return [
            {
                "record_id": f"toolset:{name}",
                "kind": "toolset",
                "name": name,
                "display_name": name,
                "description": record["description"],
                "status": record["status"],
                "tool_count": record["tool_count"],
                "available_count": record["available_count"],
                "missing_count": record["missing_count"],
                "missing_tools": record["missing_tools"][:80],
                "alias_backed_tools": record["alias_backed_tools"][:80],
                "source": record["source"],
            }
            for name, definition in _load_toolsets(config).items()
            for record in [_toolset_status(name, definition, tools)]
        ]
    except Exception:
        return []


def _mcp_server_records(config: AgentConfig) -> list[dict[str, Any]]:
    try:
        from humungousaur.tools.native_parity.implementation import _credential_readiness, _load_mcp_manifests

        records = []
        for server in _load_mcp_manifests(config):
            readiness = _credential_readiness(server)
            records.append(
                {
                    "record_id": f"mcp_server:{server.get('server_id', '')}",
                    "kind": "mcp_server",
                    "name": str(server.get("server_id", "")),
                    "display_name": str(server.get("display_name") or server.get("server_id") or ""),
                    "description": f"MCP server manifest for {server.get('display_name') or server.get('server_id')}.",
                    "status": str(server.get("status") or "manifest_ready"),
                    "transport": str(server.get("transport") or ""),
                    "configured": readiness["configured"],
                    "missing_env": readiness["missing_env"],
                    "tools": server.get("tools", []) if isinstance(server.get("tools"), list) else [],
                    "source": str(server.get("source") or ""),
                }
            )
        return records
    except Exception:
        return []


def _schema_summary(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = schema.get("required", []) if isinstance(schema, dict) else []
    return {
        "required": list(required)[:20] if isinstance(required, list) else [],
        "fields": sorted(properties.keys())[:40] if isinstance(properties, dict) else [],
        "field_count": len(properties) if isinstance(properties, dict) else 0,
    }


def _setup_summary(setup: Any) -> dict[str, Any]:
    if not isinstance(setup, dict):
        return {"required_env": [], "optional_env": [], "required_binaries": []}
    required_env = [str(item) for item in setup.get("required_env", []) if str(item)] if isinstance(setup.get("required_env"), list) else []
    optional_env = [str(item) for item in setup.get("optional_env", []) if str(item)] if isinstance(setup.get("optional_env"), list) else []
    required_binaries = [str(item) for item in setup.get("required_binaries", []) if str(item)] if isinstance(setup.get("required_binaries"), list) else []
    return {
        "required_env": required_env,
        "optional_env": optional_env,
        "required_binaries": required_binaries,
        "missing_env": [name for name in required_env if not os.environ.get(name)],
        "configured_optional_env": [name for name in optional_env if os.environ.get(name)],
        "auth_choices": setup.get("auth_choices", []),
    }


def _plugin_description(plugin: dict[str, Any]) -> str:
    parts = [str(plugin.get("display_name", "")), str(plugin.get("kind", "")), str(plugin.get("runtime_adapter", ""))]
    channels = plugin.get("channels", [])
    if isinstance(channels, list) and channels:
        parts.append("channels " + ", ".join(str(item) for item in channels[:10]))
    providers = plugin.get("providers", [])
    if isinstance(providers, list) and providers:
        parts.append("providers " + ", ".join(str(item) for item in providers[:10]))
    return ". ".join(part for part in parts if part)


def _with_search_text(record: dict[str, Any]) -> dict[str, Any]:
    terms = [
        str(record.get("record_id", "")),
        str(record.get("kind", "")),
        str(record.get("name", "")),
        str(record.get("display_name", "")),
        str(record.get("description", "")),
        str(record.get("capability_group", "")),
        str(record.get("plugin_kind", "")),
        str(record.get("status", "")),
    ]
    for key in ("tools", "skills", "channels", "providers", "groups", "expected_tools"):
        value = record.get(key)
        if isinstance(value, list):
            terms.extend(str(item) for item in value[:50])
    record["search_text"] = " ".join(terms).casefold()
    return record


def _search_records(query: str, records: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    query_text = query.casefold()
    query_terms = [term for term in query_text.split() if term]
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in records:
        score = _record_score(query_text, query_terms, record)
        if score > 0:
            item = dict(record)
            item.pop("search_text", None)
            item["score"] = score
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("kind", ""), pair[1].get("name", "")))
    return [record for _score, record in scored[:limit]]


def _record_score(query_text: str, query_terms: list[str], record: dict[str, Any]) -> int:
    record_id = str(record.get("record_id", "")).casefold()
    name = str(record.get("name", "")).casefold()
    display_name = str(record.get("display_name", "")).casefold()
    search_text = str(record.get("search_text", ""))
    score = 0
    if query_text in {record_id, name, display_name}:
        score += 100
    if query_text and query_text in record_id:
        score += 30
    if query_text and query_text in name:
        score += 25
    if query_text and query_text in display_name:
        score += 20
    for term in query_terms:
        if term in search_text:
            score += 5
        if term in record_id or term in name:
            score += 5
    return score
