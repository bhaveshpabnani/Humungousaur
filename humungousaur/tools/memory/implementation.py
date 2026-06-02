from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.memory.event_store import EventStore
from humungousaur.memory.profile import PROFILE_LIMIT, build_user_profile
from humungousaur.memory.summary import SUMMARY_LIMIT, SUMMARY_PERIODS, summarize_memory
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.activity_tools import ActivityPolicyStore, _activity_event_visible, activity_policy_path
from humungousaur.tools.base import Tool, object_input_schema


MEMORY_SEARCH_LIMIT = 20
MEMORY_TEXT_LIMIT = 4_000


class MemorySearchTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="memory_search",
            description="Search local assistant memory events for prior tasks, preferences, and saved facts.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "query": {"type": "string", "description": "Text to search in local memory."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MEMORY_SEARCH_LIMIT},
                },
                required=["query"],
            ),
            capability_group="memory",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        query = str(tool_input.get("query", "")).strip()
        if not query:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Memory query is empty.")
        limit = min(int(tool_input.get("limit") or 8), MEMORY_SEARCH_LIMIT)
        activity_policy = ActivityPolicyStore(activity_policy_path(config)).load()
        matches = [
            event
            for event in EventStore(config.memory_db_path).search(query, limit=limit * 3)
            if event.get("event_type") != "activity_event" or _activity_event_visible(event, activity_policy)
        ][:limit]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(matches)} memory events.",
            {"query": query, "matches": matches, "source": "local_memory"},
        )


class MemoryWriteTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="memory_write",
            description="Save an explicit user-approved fact, preference, or task note to local memory.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "kind": {
                        "type": "string",
                        "description": "Memory category such as preference, fact, task_note, or workflow.",
                    },
                    "text": {"type": "string", "description": "Memory text to store locally."},
                },
                required=["kind", "text"],
            ),
            capability_group="memory",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        kind = str(tool_input.get("kind", "note")).strip().lower() or "note"
        text = str(tool_input.get("text", "")).strip()
        if not text:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Memory text is empty.")
        if len(text) > MEMORY_TEXT_LIMIT:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Memory text exceeds configured limit.")
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                "Dry run: would write memory.",
                {"kind": kind, "text": text},
            )
        event_id = EventStore(config.memory_db_path).append(
            "user_memory",
            {
                "kind": kind,
                "text": text,
                "source": "memory_write_tool",
            },
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Saved memory {event_id}.",
            {"event_id": event_id, "kind": kind, "text": text},
        )


class MemorySummaryTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="memory_summary",
            description="Summarize local assistant memory for today, yesterday, the last week, or recent activity.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "period": {
                        "type": "string",
                        "enum": sorted(SUMMARY_PERIODS),
                        "description": "Memory recap window.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional text filter applied to events in the selected period.",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": SUMMARY_LIMIT},
                },
                required=["period"],
            ),
            capability_group="memory",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        period = str(tool_input.get("period", "today"))
        query = str(tool_input.get("query", ""))
        limit = min(int(tool_input.get("limit") or SUMMARY_LIMIT), SUMMARY_LIMIT)
        activity_policy = ActivityPolicyStore(activity_policy_path(config)).load()
        summary = summarize_memory(
            EventStore(config.memory_db_path),
            period=period,
            query=query,
            limit=limit,
            event_filter=lambda event: event.get("event_type") != "activity_event"
            or _activity_event_visible(event, activity_policy),
        )
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            summary["summary"],
            {**summary, "source": "local_memory"},
        )


class MemoryProfileTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="memory_profile",
            description="Build an inspectable local user profile from explicit remembered preferences, facts, workflows, and notes.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": PROFILE_LIMIT,
                        "description": "Maximum explicit memory events to project into the profile.",
                    },
                }
            ),
            capability_group="memory",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        limit = min(int(tool_input.get("limit") or PROFILE_LIMIT), PROFILE_LIMIT)
        profile = build_user_profile(EventStore(config.memory_db_path), limit=limit)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            profile["summary"],
            {**profile, "source": "local_memory"},
        )


def default_memory_tools() -> dict[str, Tool]:
    tools: list[Tool] = [MemorySearchTool(), MemoryWriteTool(), MemorySummaryTool(), MemoryProfileTool()]
    return {tool.name: tool for tool in tools}
