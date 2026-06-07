from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, ToolResult
from humungousaur.tools import default_tools
from humungousaur.tools.skill_tools import AgentSkillCatalogTool, AgentSkillReadTool, AgentSkillScriptCatalogTool, AgentSkillScriptReadTool, AgentSkillScriptRunTool


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke every Humungousaur workspace skill and representative task capability.")
    parser.add_argument("--workspace", type=Path, default=REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=Path("artifacts/skill-smoke"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = AgentConfig(workspace=args.workspace, data_dir=args.data_dir, planner_provider="explicit").normalized()
    tools = default_tools(config)
    tool_names = set(tools)
    sections: list[dict[str, Any]] = []

    def record(section: str, name: str, ok: bool, payload: Any) -> None:
        sections.append({"section": section, "name": name, "ok": ok, "payload": _jsonable(payload)})

    catalog = AgentSkillCatalogTool().execute({"source": "workspace", "limit": 300}, config)
    skills = catalog.output.get("workspace_skills", []) if catalog.status == ActionStatus.SUCCEEDED else []
    skill_names = {str(skill.get("name", "")) for skill in skills}
    record("skills", "catalog", catalog.status == ActionStatus.SUCCEEDED and len(skills) >= 100, _tool_payload(catalog))
    for skill in skills:
        skill_id = skill["skill_id"]
        read = AgentSkillReadTool().execute({"skill_id": skill_id}, config)
        content = read.output.get("content", "") if read.status == ActionStatus.SUCCEEDED else ""
        tool_map = _tool_map_entries(content)
        missing = [entry for entry in tool_map if entry not in tool_names and entry not in skill_names]
        record(
            "skills",
            f"read:{skill['name']}",
            read.status == ActionStatus.SUCCEEDED and "# " in content,
            {"skill_id": skill_id, "status": read.status.value, "summary": read.summary, "content_length": len(content)},
        )
        record(
            "skills",
            f"tool_map:{skill['name']}",
            not missing,
            {
                "skill_id": skill_id,
                "tool_map": tool_map,
                "native_tools": [entry for entry in tool_map if entry in tool_names],
                "skill_refs": [entry for entry in tool_map if entry in skill_names],
                "missing": missing,
            },
        )

    script_catalog = AgentSkillScriptCatalogTool().execute({"limit": 300}, config)
    scripts = script_catalog.output.get("scripts", []) if script_catalog.status == ActionStatus.SUCCEEDED else []
    record("skills", "script_catalog", script_catalog.status == ActionStatus.SUCCEEDED, _tool_payload(script_catalog))
    _prepare_script_fixtures(config)
    for script in scripts:
        script_read = AgentSkillScriptReadTool().execute({"script_id": script["script_id"]}, config)
        record(
            "skills",
            f"script_read:{script['name']}",
            script_read.status == ActionStatus.SUCCEEDED and bool(script.get("input_schema")),
            {"script_id": script["script_id"], "status": script_read.status.value, "summary": script_read.summary},
        )
        script_input = _script_smoke_input(script["name"], config)
        script_run = AgentSkillScriptRunTool().execute(
            {"script_id": script["script_id"], "input": script_input, "reason": f"Skill smoke for {script['name']}."},
            config,
        )
        record(
            "skills",
            f"script_run:{script['name']}",
            script_run.status == ActionStatus.SUCCEEDED,
            {
                "script_id": script["script_id"],
                "status": script_run.status.value,
                "summary": script_run.summary,
                "returncode": script_run.output.get("returncode"),
                "json": script_run.output.get("json"),
                "stderr": script_run.output.get("stderr", "")[-500:],
            },
        )

    _smoke_productivity(record, tools, config)
    _smoke_channels(record, tools, config)
    _smoke_core_surfaces(record, tools, config)

    failed = [item for item in sections if not item["ok"]]
    config.data_dir.mkdir(parents=True, exist_ok=True)
    result_path = config.data_dir / "skill-smoke-results.json"
    result_path.write_text(json.dumps({"sections": sections, "failed": failed}, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {"ok": not failed, "result_path": str(result_path), "section_count": len(sections), "failed_count": len(failed), "failed": failed[:20]}
    print(json.dumps(summary, indent=2 if args.json else None, ensure_ascii=False))
    return 0 if not failed else 1


def _smoke_productivity(record, tools: dict[str, Any], config: AgentConfig) -> None:
    gmail = tools["gmail_draft_prepare"].execute(
        {
            "to": ["person@example.com"],
            "subject": "Humungousaur skill smoke",
            "body": "Hi,\n\nThis is a local Gmail draft smoke. It was not sent.\n\nBest,\nHumungousaur",
            "reason": "Verify Gmail draft preparation skill capability.",
        },
        config,
    )
    record("productivity", "gmail_draft_prepare", _ok(gmail) and gmail.output["draft"]["send_status"] == "not_sent", _tool_payload(gmail))

    xlsx = tools["xlsx_workbook_create"].execute(
        {
            "filename": "skill-smoke.xlsx",
            "reason": "Verify Excel workbook skill capability.",
            "sheets": [{"name": "Summary", "rows": [["Metric", "Value"], ["Revenue", 100], ["Cost", 40], ["Profit", None]], "formulas": [{"cell": "B4", "formula": "=B2-B3"}]}],
        },
        config,
    )
    inspect = tools["xlsx_workbook_inspect"].execute({"path": xlsx.output.get("path", ""), "sample_rows": 5}, config) if _ok(xlsx) else xlsx
    formula_ok = _ok(inspect) and any(item.get("formula") == "=B2-B3" for item in inspect.output["sheets"][0]["formulas"])
    record("productivity", "xlsx_workbook_create", _ok(xlsx), _tool_payload(xlsx))
    record("productivity", "xlsx_workbook_inspect", formula_ok, _tool_payload(inspect))


def _prepare_script_fixtures(config: AgentConfig) -> None:
    fixtures = config.data_dir / "script-fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "sample.csv").write_text("name,score\nAda,10\nGrace,12\nAlan,\n", encoding="utf-8")
    (fixtures / "note-a.md").write_text("# Note A\n\nLinks to [[Note B]] and [web](https://example.com).\n", encoding="utf-8")
    (fixtures / "note-b.md").write_text("# Note B\n\nBacklink target.\n", encoding="utf-8")


def _script_smoke_input(name: str, config: AgentConfig) -> dict[str, Any]:
    fixtures = config.data_dir / "script-fixtures"
    if name == "inspect-repo":
        return {"path": ".", "max_files": 500}
    if name == "profile-csv":
        return {"path": str(fixtures / "sample.csv"), "max_rows": 100}
    if name == "build-markdown-index":
        return {"root": str(fixtures), "max_files": 20}
    if name == "redact-text":
        return {"text": "OPENAI_API_KEY=sk-test-secret and token ghp_testsecret", "replacement": "[REDACTED]"}
    if name == "inspect-skill-pack":
        return {"skill_dir": "skills/system-health-check"}
    if name == "check-readiness":
        return {"env_names": ["OPENAI_API_KEY", "GROQ_API_KEY"]}
    return {}


def _smoke_channels(record, tools: dict[str, Any], config: AgentConfig) -> None:
    for channel_id in ("slack", "whatsapp", "telegram", "discord"):
        manifest = tools["channel_manifest"].execute({"channel_id": channel_id}, config)
        doctor = tools["channel_doctor"].execute({"channel_id": channel_id}, config)
        record("channels", f"{channel_id}_manifest", _ok(manifest), _tool_payload(manifest))
        record("channels", f"{channel_id}_doctor", _ok(doctor), _tool_payload(doctor))


def _smoke_core_surfaces(record, tools: dict[str, Any], config: AgentConfig) -> None:
    scenarios = [
        ("files", "write_note", {"title": "skill smoke note", "content": "Skill smoke note."}),
        ("memory", "memory_write", {"text": "Skill smoke memory.", "kind": "observation", "source": "skill_smoke"}),
        ("system", "system_status", {}),
        ("voice", "voice_provider_status", {}),
        ("browser", "web_search", {"query": "Humungousaur local assistant", "limit": 1}),
        ("workflow", "diff_render", {"left_text": "old\n", "right_text": "new\n"}),
        ("workflow", "tokenjuice_compact", {"text": "\n".join(f"line {i}" for i in range(100)), "max_chars": 500}),
        ("capabilities", "capability_surface", {"include_tools": True, "include_plugins": True, "include_channels": True, "include_skills": True}),
    ]
    for section, tool_name, payload in scenarios:
        result = tools[tool_name].execute(payload, config)
        record(section, tool_name, result.status in {ActionStatus.SUCCEEDED, ActionStatus.SKIPPED}, _tool_payload(result))


def _ok(result: ToolResult) -> bool:
    return result.status == ActionStatus.SUCCEEDED


def _tool_payload(result: ToolResult) -> dict[str, Any]:
    return {"status": result.status.value, "summary": result.summary, "error": result.error, "output": result.output}


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


def _tool_map_entries(content: str) -> list[str]:
    entries: list[str] = []
    in_tool_map = False
    for line in content.splitlines():
        if line.strip().lower().startswith("## tool map"):
            in_tool_map = True
            continue
        if in_tool_map and line.startswith("## "):
            break
        if not in_tool_map:
            continue
        match = re.match(r"\s*-\s+`([^`]+)`", line)
        if match:
            entries.append(match.group(1))
    return entries


if __name__ == "__main__":
    sys.exit(main())
