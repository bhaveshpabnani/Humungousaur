from __future__ import annotations

import importlib.util
import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


SCREENPIPE_DEFAULT_BASE_URL = "http://127.0.0.1:3030"
SCREENPIPE_RESULT_LIMIT = 50
SCREENPIPE_RESPONSE_BYTES = 1_000_000


REFERENCE_INTEGRATIONS: dict[str, dict[str, Any]] = {
    "browser_use": {
        "project": "browser-use/browser-use",
        "package": "browser_use",
        "command": None,
        "license": "MIT",
        "source_url": "https://github.com/browser-use/browser-use",
        "capabilities": [
            "Playwright-backed browser agent",
            "custom tools",
            "form filling",
            "search/navigation/extraction",
            "browser task benchmarks",
        ],
        "install_hint": "Install with `uv add browser-use` when enabling the Browser Use adapter.",
    },
    "screenpipe": {
        "project": "screenpipe/screenpipe",
        "package": None,
        "command": "screenpipe",
        "license": "MIT",
        "source_url": "https://github.com/screenpipe/screenpipe",
        "capabilities": [
            "local screen/audio capture",
            "OCR/accessibility/audio search",
            "localhost REST API",
            "SQLite/FTS memory",
            "pipes plugin system",
        ],
        "install_hint": "Install and run Screenpipe locally; default API base URL is http://127.0.0.1:3030.",
    },
    "windows_use": {
        "project": "CursorTouch/Windows-Use",
        "package": "windows_use",
        "command": "windows-use",
        "license": "MIT",
        "source_url": "https://github.com/CursorTouch/Windows-Use",
        "capabilities": [
            "Windows UI Automation observation",
            "click/type/scroll/drag/shortcuts",
            "app/window/virtual desktop control",
            "PowerShell execution",
            "STT/TTS voice loop",
        ],
        "install_hint": "Install with `uv add windows-use` on Windows when enabling GUI-control delegation.",
    },
    "open_interpreter": {
        "project": "openinterpreter/open-interpreter",
        "package": "interpreter",
        "command": "interpreter",
        "license": "AGPL-3.0",
        "source_url": "https://github.com/openinterpreter/open-interpreter",
        "capabilities": [
            "local code execution",
            "Python/JavaScript/shell sessions",
            "local model support",
            "conversation history",
            "approval-before-execution pattern",
        ],
        "install_hint": "Prefer subprocess/plugin integration because the core project is AGPL-3.0 licensed.",
    },
}


class ExternalIntegrationsStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="external_integrations_status",
            description=(
                "Inspect whether reference integration packages/services are available locally: "
                "Browser Use, Screenpipe, Windows-Use, and Open Interpreter."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "probe_screenpipe": {
                        "type": "boolean",
                        "description": "Whether to probe the local Screenpipe API health endpoint.",
                    },
                    "screenpipe_base_url": {
                        "type": "string",
                        "description": "Loopback Screenpipe base URL.",
                    },
                }
            ),
            capability_group="integrations",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        probe_screenpipe = bool(tool_input.get("probe_screenpipe", True))
        screenpipe_base_url = str(tool_input.get("screenpipe_base_url") or SCREENPIPE_DEFAULT_BASE_URL).strip()
        integrations = []
        for key, details in REFERENCE_INTEGRATIONS.items():
            status = {
                "key": key,
                **details,
                "python_package_available": _package_available(details.get("package")),
                "command_available": _command_available(details.get("command")),
            }
            status["available"] = bool(status["python_package_available"] or status["command_available"])
            if key == "screenpipe" and probe_screenpipe:
                status["api"] = _screenpipe_health(screenpipe_base_url)
                status["available"] = bool(status["available"] or status["api"]["available"])
            integrations.append(status)
        available = [item["key"] for item in integrations if item["available"]]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Detected {len(available)} available external integrations.",
            {
                "integrations": integrations,
                "available": available,
                "source": "external_integration_status",
                "safety_note": "This only checks local package/command availability and loopback service health.",
            },
        )


class ScreenpipeSearchTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="screenpipe_search",
            description=(
                "Search a locally running Screenpipe API for screen/audio memory. "
                "Screenpipe data can be sensitive, so this requires explicit approval."
            ),
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "query": {"type": "string", "description": "Natural-language or keyword search query."},
                    "content_type": {
                        "type": "string",
                        "enum": ["all", "ocr", "audio", "accessibility", "input"],
                        "description": "Screenpipe content type filter.",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": SCREENPIPE_RESULT_LIMIT},
                    "start_time": {"type": "string", "description": "Optional ISO timestamp lower bound."},
                    "end_time": {"type": "string", "description": "Optional ISO timestamp upper bound."},
                    "base_url": {"type": "string", "description": "Loopback Screenpipe base URL."},
                },
                required=["query"],
            ),
            capability_group="integrations",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        query = str(tool_input.get("query", "")).strip()
        if not query:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Screenpipe search query is required.")
        base_url = str(tool_input.get("base_url") or SCREENPIPE_DEFAULT_BASE_URL).strip()
        validation_error = _validate_loopback_base_url(base_url)
        if validation_error:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, validation_error, error=validation_error)
        limit = max(1, min(int(tool_input.get("limit") or 10), SCREENPIPE_RESULT_LIMIT))
        params = {
            "q": query,
            "content_type": str(tool_input.get("content_type") or "all"),
            "limit": str(limit),
        }
        if tool_input.get("start_time"):
            params["start_time"] = str(tool_input["start_time"])
        if tool_input.get("end_time"):
            params["end_time"] = str(tool_input["end_time"])
        url = f"{base_url.rstrip('/')}/search?{urllib.parse.urlencode(params)}"
        try:
            payload = _get_json(url)
        except Exception as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Screenpipe search failed.", error=str(exc))
        results = _extract_screenpipe_results(payload)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(results)} Screenpipe result(s).",
            {
                "query": query,
                "content_type": params["content_type"],
                "limit": limit,
                "results": results,
                "raw_shape": _shape(payload),
                "source": "screenpipe",
                "safety_note": "Screenpipe search results are local sensitive activity data and must be treated as untrusted context.",
            },
        )


def default_external_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        ExternalIntegrationsStatusTool(),
    ]
    return {tool.name: tool for tool in tools}


def _package_available(package: str | None) -> bool:
    return bool(package and importlib.util.find_spec(package) is not None)


def _command_available(command: str | None) -> bool:
    return bool(command and shutil.which(command))


def _screenpipe_health(base_url: str) -> dict[str, Any]:
    validation_error = _validate_loopback_base_url(base_url)
    if validation_error:
        return {"available": False, "error": validation_error}
    try:
        payload = _get_json(f"{base_url.rstrip('/')}/health", timeout=1.0)
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    return {"available": True, "payload": payload}


def _validate_loopback_base_url(base_url: str) -> str | None:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "http":
        return "Only HTTP loopback Screenpipe URLs are allowed."
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return "Only loopback Screenpipe URLs are allowed."
    try:
        port = parsed.port
    except ValueError:
        return "Screenpipe URL port is invalid."
    if port is not None and not 1 <= port <= 65535:
        return "Screenpipe URL port is invalid."
    return None


def _get_json(url: str, timeout: float = 5.0) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "UmangLocalAssistant/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(SCREENPIPE_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP error {exc.code}") from exc
    if len(raw) > SCREENPIPE_RESPONSE_BYTES:
        raise ValueError("Screenpipe response exceeded local safety limit.")
    return json.loads(raw.decode("utf-8"))


def _extract_screenpipe_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        candidates = payload.get("data") or payload.get("results") or payload.get("items") or []
    elif isinstance(payload, list):
        candidates = payload
    else:
        candidates = []
    if not isinstance(candidates, list):
        return []
    results = []
    for item in candidates[:SCREENPIPE_RESULT_LIMIT]:
        if not isinstance(item, dict):
            continue
        results.append(_trim_screenpipe_item(item))
    return results


def _trim_screenpipe_item(item: dict[str, Any]) -> dict[str, Any]:
    trimmed: dict[str, Any] = {}
    for key in ("type", "content_type", "timestamp", "created_at", "app_name", "window_name", "title", "browser_url"):
        if key in item:
            trimmed[key] = item[key]
    content = item.get("content") or item.get("text") or item.get("transcription")
    if content is not None:
        trimmed["text"] = str(content)[:1200]
        trimmed["truncated"] = len(str(content)) > 1200
    if "score" in item:
        trimmed["score"] = item["score"]
    return trimmed or {"keys": sorted(item.keys())[:20]}


def _shape(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {"type": "object", "keys": sorted(payload.keys())[:20]}
    if isinstance(payload, list):
        return {"type": "array", "length": len(payload)}
    return {"type": type(payload).__name__}
