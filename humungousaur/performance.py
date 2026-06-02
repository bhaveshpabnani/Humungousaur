from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from typing import Any, Callable

from humungousaur.config import AgentConfig
from humungousaur.indexing import FileIndex
from humungousaur.memory.event_store import EventStore
from humungousaur.memory.profile import build_user_profile
from humungousaur.orchestrator import AgentOrchestrator
from humungousaur.planning.providers import ExplicitFallbackPlanProvider
from humungousaur.safety.permissions import permissions_snapshot
from humungousaur.tools.browser_tools import BrowserOpenTool, BrowserSessionStore, BrowserSessionsTool, FetchWebPageTool
from humungousaur.tools.file_tools import ListFilesTool, SearchWorkspaceTool, SummarizePDFsTool
from humungousaur.tools.memory_tools import MemorySearchTool, MemorySummaryTool, MemoryWriteTool
from humungousaur.tools.os_tools import ActiveWindowTool, ScreenCapturesTool, ScreenshotCaptureTool
from humungousaur.tools.validation import validate_tool_input


def run_benchmarks(config: AgentConfig, iterations: int = 3, query: str = "project") -> dict[str, Any]:
    normalized = config.normalized()
    count = max(1, min(iterations, 25))
    benchmark_config = replace(
        normalized,
        dry_run=True,
        data_dir=normalized.data_dir / "benchmarks",
        planner_provider="explicit",
    ).normalized()
    _seed_benchmark_context(benchmark_config)
    orchestrator = AgentOrchestrator(benchmark_config)

    benchmarks = [
        _measure("permissions_snapshot", count, lambda: permissions_snapshot(normalized), _count_tools),
        _measure("explicit_planner", count, lambda: ExplicitFallbackPlanProvider().plan('system_status {}'), _count_plan_steps),
        _measure("planning_context", count, lambda: orchestrator._planning_context(), _count_planning_context),
        _measure(
            "tool_schema_validation",
            count,
            lambda: validate_tool_input({"query": query, "limit": 5}, MemorySearchTool().input_schema),
            _count_validation,
        ),
        _measure("list_files_allowed_roots", count, lambda: ListFilesTool().execute({"path": "."}, normalized), _count_files),
        _measure("search_allowed_roots", count, lambda: SearchWorkspaceTool().execute({"query": query}, normalized), _count_matches),
        _measure("memory_search", count, lambda: MemorySearchTool().execute({"query": query, "limit": 5}, benchmark_config), _count_memory_matches),
        _measure("memory_summary", count, lambda: MemorySummaryTool().execute({"period": "recent", "query": query, "limit": 50}, benchmark_config), _count_memory_summary),
        _measure("memory_profile", count, lambda: build_user_profile(EventStore(benchmark_config.memory_db_path), limit=50), _count_memory_profile),
        _measure("memory_write_dry_run", count, lambda: MemoryWriteTool().execute({"kind": "benchmark", "text": query}, benchmark_config), _count_tool_status),
        _measure("os_active_window", count, lambda: ActiveWindowTool().execute({}, benchmark_config), _count_tool_status),
        _measure(
            "screenshot_capture_dry_run",
            count,
            lambda: ScreenshotCaptureTool().execute({"reason": "benchmark"}, benchmark_config),
            _count_tool_status,
        ),
        _measure(
            "screen_captures_metadata",
            count,
            lambda: ScreenCapturesTool().execute({"limit": 5}, benchmark_config),
            _count_screen_captures,
        ),
        _measure("summarize_pdfs", count, lambda: SummarizePDFsTool().execute({"path": "."}, normalized), _count_pdf_summaries),
        _measure("web_fetch_guard", count, lambda: FetchWebPageTool().execute({"url": "file:///secret.txt"}, normalized), _count_web_guard),
        _measure("browser_open_guard", count, lambda: BrowserOpenTool().execute({"url": "file:///secret.txt"}, normalized), _count_web_guard),
        _measure(
            "browser_sessions_metadata",
            count,
            lambda: BrowserSessionsTool().execute({"limit": 5}, benchmark_config),
            _count_browser_sessions,
        ),
        _measure("file_index_rebuild", count, lambda: FileIndex(benchmark_config.file_index_db_path).rebuild(normalized), _count_index),
        _measure("file_index_search", count, lambda: FileIndex(benchmark_config.file_index_db_path).search(query, normalized), _count_index_matches),
        _measure(
            "agent_dry_run_summary",
            count,
            lambda: orchestrator.run('list_files {"path":"."}'),
            _count_agent_results,
        ),
    ]
    return {
        "workspace": str(normalized.workspace),
        "data_dir": str(normalized.data_dir),
        "iterations": count,
        "query": query,
        "benchmarks": benchmarks,
    }


def _seed_benchmark_context(config: AgentConfig) -> None:
    memory = EventStore(config.memory_db_path)
    memory.append("benchmark_context", {"text": "project benchmark needle", "source": "benchmark"})
    memory.append("user_memory", {"kind": "preference", "text": "project benchmark preference", "source": "benchmark"})
    BrowserSessionStore(config.browser_sessions_db_path).create_or_update(
        {
            "url": "http://127.0.0.1/benchmark",
            "title": "Benchmark Browser Context",
            "text": "Synthetic local benchmark browser session.",
            "links": [],
            "forms": [],
        }
    )


def _measure(
    name: str,
    iterations: int,
    operation: Callable[[], Any],
    detail: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    durations: list[float] = []
    last_result: Any = None
    for _index in range(iterations):
        start = perf_counter()
        last_result = operation()
        durations.append(round((perf_counter() - start) * 1000, 3))
    return {
        "name": name,
        "iterations": iterations,
        "avg_ms": round(sum(durations) / len(durations), 3),
        "min_ms": min(durations),
        "max_ms": max(durations),
        "last": detail(last_result),
    }


def _count_tools(payload: dict[str, Any]) -> dict[str, Any]:
    return {"tools": len(payload.get("tools", [])), "read_roots": len(payload.get("allowed_read_roots", []))}


def _count_plan_steps(plan: Any) -> dict[str, Any]:
    return {"steps": len(plan.steps), "used_provider": plan.used_provider}


def _count_planning_context(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "keys": len(payload),
        "recent_memory": len(payload.get("recent_memory", [])),
        "browser_sessions": len(payload.get("browser_sessions", [])),
    }


def _count_validation(result: Any) -> dict[str, Any]:
    return {"valid": result is None}


def _count_files(result: Any) -> dict[str, Any]:
    return {"status": result.status.value, "files": len(result.output.get("files", []))}


def _count_matches(result: Any) -> dict[str, Any]:
    return {"status": result.status.value, "matches": len(result.output.get("matches", []))}


def _count_memory_matches(result: Any) -> dict[str, Any]:
    return {"status": result.status.value, "matches": len(result.output.get("matches", []))}


def _count_memory_summary(result: Any) -> dict[str, Any]:
    return {"status": result.status.value, "events": result.output.get("total_events", 0)}


def _count_memory_profile(result: dict[str, Any]) -> dict[str, Any]:
    return {"memories": result.get("total_memories", 0), "sections": len(result.get("kind_counts", {}))}


def _count_tool_status(result: Any) -> dict[str, Any]:
    return {"status": result.status.value, "summary": result.summary}


def _count_screen_captures(result: Any) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "captures": len(result.output.get("captures", [])),
        "image_bytes_served": result.output.get("image_bytes_served"),
    }


def _count_browser_sessions(result: Any) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "sessions": len(result.output.get("sessions", [])),
        "page_text_returned": result.output.get("page_text_returned"),
    }


def _count_index(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "usable": result["usable"],
        "indexed_files": result["indexed_files"],
        "indexed_lines": result["indexed_lines"],
    }


def _count_pdf_summaries(result: Any) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "summaries": len(result.output.get("summaries", [])),
        "errors": len(result.output.get("errors", [])),
    }


def _count_web_guard(result: Any) -> dict[str, Any]:
    return {"status": result.status.value, "summary": result.summary}


def _count_index_matches(result: list[dict[str, Any]]) -> dict[str, Any]:
    return {"matches": len(result)}


def _count_agent_results(result: Any) -> dict[str, Any]:
    return {"run_id": result.run_id, "tool_results": len(result.results), "approvals": len(result.approvals)}
