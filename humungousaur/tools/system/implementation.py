from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


CRITICAL_FREE_BYTES = 50 * 1024 * 1024
LOW_FREE_BYTES = 250 * 1024 * 1024


class SystemStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="system_status",
            description="Report local runtime, workspace, and disk health without reading user content.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(),
            capability_group="system",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        status = collect_system_status(config)
        summary = f"System status: {status['overall_status']}."
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            summary,
            status,
        )


def collect_system_status(config: AgentConfig) -> dict[str, Any]:
    normalized = config.normalized()
    storage = [_storage_status("workspace", normalized.workspace), _storage_status("data", normalized.data_dir)]
    worst = _worst_storage_status(storage)
    return {
        "overall_status": worst,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "workspace": str(normalized.workspace),
        "data_dir": str(normalized.data_dir),
        "dry_run": normalized.dry_run,
        "storage": storage,
        "warnings": _storage_warnings(storage),
    }


def default_system_tools() -> dict[str, Tool]:
    tools: list[Tool] = [SystemStatusTool()]
    return {tool.name: tool for tool in tools}


def _storage_status(label: str, path: Path) -> dict[str, Any]:
    probe = _existing_probe_path(path)
    usage = shutil.disk_usage(probe)
    free_percent = round((usage.free / usage.total) * 100, 3) if usage.total else 0.0
    if usage.free < CRITICAL_FREE_BYTES or free_percent < 1.0:
        status = "critical"
    elif usage.free < LOW_FREE_BYTES or free_percent < 5.0:
        status = "low"
    else:
        status = "ok"
    return {
        "label": label,
        "path": str(path),
        "probe_path": str(probe),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_percent": free_percent,
        "status": status,
    }


def _existing_probe_path(path: Path) -> Path:
    current = path
    while not current.exists() and current.parent != current:
        current = current.parent
    return current if current.exists() else Path.cwd()


def _worst_storage_status(storage: list[dict[str, Any]]) -> str:
    ranks = {"ok": 0, "low": 1, "critical": 2}
    worst = max(storage, key=lambda item: ranks.get(str(item["status"]), 0))
    return "critical_disk" if worst["status"] == "critical" else "low_disk" if worst["status"] == "low" else "ok"


def _storage_warnings(storage: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for item in storage:
        if item["status"] == "critical":
            warnings.append(f"{item['label']} storage is critically low: {item['free_bytes']} bytes free.")
        elif item["status"] == "low":
            warnings.append(f"{item['label']} storage is low: {item['free_bytes']} bytes free.")
    return warnings
