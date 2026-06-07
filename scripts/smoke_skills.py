from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any
import uuid

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
            bool(tool_map) and not missing,
            {
                "skill_id": skill_id,
                "tool_map": tool_map,
                "native_tools": [entry for entry in tool_map if entry in tool_names],
                "skill_refs": [entry for entry in tool_map if entry in skill_names],
                "missing": missing,
                "has_tool_map": bool(tool_map),
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
    _smoke_office(record, tools, config)
    _smoke_channels(record, tools, config)
    _smoke_core_surfaces(record, tools, config)
    _smoke_skill_task_surfaces(record, tools, config)

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


def _smoke_office(record, tools: dict[str, Any], config: AgentConfig) -> None:
    docx = tools["docx_document_create"].execute(
        {
            "filename": "skill-smoke.docx",
            "title": "Humungousaur DOCX Skill Smoke",
            "reason": "Verify DOCX creation skill capability.",
            "sections": [
                {
                    "heading": "Summary",
                    "paragraphs": ["This DOCX was created by a native Humungousaur office tool."],
                    "bullets": ["Native artifact", "Inspectable text"],
                    "tables": [{"rows": [["Capability", "Status"], ["DOCX", "Created"]]}],
                }
            ],
        },
        config,
    )
    docx_inspect = tools["docx_document_inspect"].execute({"path": docx.output.get("path", ""), "sample_paragraphs": 10}, config) if _ok(docx) else docx
    record("office", "docx_document_create", _ok(docx), _tool_payload(docx))
    record(
        "office",
        "docx_document_inspect",
        _ok(docx_inspect) and "Humungousaur DOCX Skill Smoke" in docx_inspect.output.get("text_preview", ""),
        _tool_payload(docx_inspect),
    )

    pptx = tools["pptx_deck_create"].execute(
        {
            "filename": "skill-smoke.pptx",
            "title": "Humungousaur PPTX Skill Smoke",
            "reason": "Verify PPTX creation skill capability.",
            "slides": [
                {"title": "Capability", "bullets": ["Native PPTX artifact", "Inspectable slide text"]},
                {"title": "Verification", "bullets": ["File exists", "Slide count matches"]},
            ],
        },
        config,
    )
    pptx_inspect = tools["pptx_deck_inspect"].execute({"path": pptx.output.get("path", ""), "sample_slides": 5}, config) if _ok(pptx) else pptx
    record("office", "pptx_deck_create", _ok(pptx), _tool_payload(pptx))
    record(
        "office",
        "pptx_deck_inspect",
        _ok(pptx_inspect) and pptx_inspect.output.get("slide_count", 0) >= 3,
        _tool_payload(pptx_inspect),
    )


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
        requirements = tools["channel_setup_requirements"].execute({"channel_id": channel_id}, config)
        setup = tools["channel_setup_save"].execute(
            {
                "channel_id": channel_id,
                "enabled": True,
                "conversation_defaults": _channel_defaults(channel_id),
                "secret_refs": _channel_secret_refs(channel_id),
                "allowlist": ["user-smoke"],
                "group_allowlist": ["room-smoke"],
                "notes": f"Skill smoke setup for {channel_id}.",
            },
            config,
        )
        status = tools["channel_setup_status"].execute({"channel_id": channel_id}, config)
        listener = tools["channel_listener_status"].execute({"channel_id": channel_id}, config)
        prepared = tools["channel_message_prepare"].execute(
            {
                "channel_id": channel_id,
                "conversation_id": _channel_defaults(channel_id)["conversation_id"],
                "text": _channel_smoke_text(channel_id),
                "metadata": _channel_prepare_metadata(channel_id),
                "reason": f"Prepare a non-sending {channel_id} channel smoke envelope.",
            },
            config,
        )
        webhook = tools["channel_webhook_ingest"].execute(
            {
                "channel_id": channel_id,
                "payload": _channel_webhook_payload(channel_id),
                "prepare_reply": True,
                "reason": f"Normalize and process a representative {channel_id} inbound event.",
            },
            config,
        )
        outbox = tools["channel_outbox"].execute({"limit": 20}, config)
        record("channels", f"{channel_id}_manifest", _ok(manifest), _tool_payload(manifest))
        record("channels", f"{channel_id}_doctor", _ok(doctor), _tool_payload(doctor))
        record("channels", f"{channel_id}_requirements", _ok(requirements), _tool_payload(requirements))
        record("channels", f"{channel_id}_setup_save", _ok(setup), _tool_payload(setup))
        record("channels", f"{channel_id}_setup_status", _ok(status), _tool_payload(status))
        record("channels", f"{channel_id}_listener_status", _ok(listener), _tool_payload(listener))
        record(
            "channels",
            f"{channel_id}_message_prepare",
            _ok(prepared) and prepared.output["message"]["status"] == "prepared_not_sent",
            _tool_payload(prepared),
        )
        record(
            "channels",
            f"{channel_id}_webhook_ingest",
            _ok(webhook) and webhook.output.get("message_count", 0) == 1,
            _tool_payload(webhook),
        )
        record(
            "channels",
            f"{channel_id}_outbox",
            _ok(outbox) and any(item.get("channel_id") == channel_id for item in outbox.output.get("messages", [])),
            _tool_payload(outbox),
        )


def _channel_defaults(channel_id: str) -> dict[str, str]:
    return {
        "slack": {"conversation_id": "D-SMOKE", "conversation_type": "im"},
        "whatsapp": {"conversation_id": "+15555550100", "conversation_type": "private"},
        "telegram": {"conversation_id": "420001", "conversation_type": "private"},
        "discord": {"conversation_id": "990001", "conversation_type": "dm"},
    }.get(channel_id, {"conversation_id": "smoke-room", "conversation_type": "dm"})


def _channel_secret_refs(channel_id: str) -> dict[str, str]:
    return {
        "slack": {"bot_token": "SLACK_BOT_TOKEN", "signing_secret": "SLACK_SIGNING_SECRET"},
        "whatsapp": {"access_token": "WHATSAPP_ACCESS_TOKEN", "phone_number_id": "WHATSAPP_PHONE_NUMBER_ID"},
        "telegram": {"bot_token": "TELEGRAM_BOT_TOKEN"},
        "discord": {"bot_token": "DISCORD_BOT_TOKEN"},
    }.get(channel_id, {})


def _channel_smoke_text(channel_id: str) -> str:
    if channel_id == "telegram":
        return "Skill smoke with image: ![chart](https://example.com/chart.png)"
    return f"Humungousaur {channel_id} channel skill smoke. This was not sent."


def _channel_prepare_metadata(channel_id: str) -> dict[str, Any]:
    if channel_id == "slack":
        return {"thread_ts": "1712023032.1234"}
    if channel_id == "discord":
        return {"thread_id": "990001"}
    return {}


def _channel_webhook_payload(channel_id: str) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:8]
    if channel_id == "slack":
        return {
            "event_id": f"EvSkillSmoke-{suffix}",
            "event": {
                "type": "message",
                "channel": "D-SMOKE",
                "channel_type": "im",
                "user": "U-SMOKE",
                "text": "Hello from Slack skill smoke.",
                "client_msg_id": f"slack-smoke-{suffix}",
            },
        }
    if channel_id == "telegram":
        return {
            "update_id": int(suffix[:6], 16),
            "message": {
                "message_id": int(suffix[-6:], 16),
                "chat": {"id": "420001", "type": "private"},
                "from": {"id": "7001", "is_bot": False},
                "text": "Hello from Telegram skill smoke.",
            },
        }
    if channel_id == "discord":
        return {
            "id": f"discord-smoke-{suffix}",
            "channel_id": "990001",
            "conversation_type": "dm",
            "author": {"id": "discord-user", "bot": False},
            "content": "Hello from Discord skill smoke.",
            "requires_response": True,
        }
    if channel_id == "whatsapp":
        return {"from": "+15555550100", "id": f"whatsapp-smoke-{suffix}", "text": "Hello from WhatsApp skill smoke."}
    return {"conversation_id": "smoke-room", "sender_id": "user-smoke", "text": f"Hello from {channel_id}."}


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


def _smoke_skill_task_surfaces(record, tools: dict[str, Any], config: AgentConfig) -> None:
    dry_config = AgentConfig(
        workspace=config.workspace,
        data_dir=config.data_dir,
        max_file_bytes=config.max_file_bytes,
        max_search_results=config.max_search_results,
        dry_run=True,
        planner_provider=config.planner_provider,
        model_provider=config.model_provider,
        model_name=config.model_name,
        model_base_url=config.model_base_url,
        model_api_key_env=config.model_api_key_env,
        model_timeout_seconds=config.model_timeout_seconds,
        runtime_secrets=config.runtime_secrets,
        allowed_read_roots=config.allowed_read_roots,
        allowed_write_roots=config.allowed_write_roots,
    ).normalized()
    scenarios = [
        ("capability_surfaces", "tool_describe", {"record_id": "tool:channel_message_prepare"}),
        ("capability_surfaces", "tool_search", {"query": "voice response", "limit": 5}),
        ("computer_use", "browser_live_status", {}),
        ("computer_use", "os_active_window", {}),
        ("speech", "voice_response_prepare", {"text": "Humungousaur voice skill smoke.", "reason": "Prepare a voice artifact without playback.", "tts_provider": "artifact"}),
        ("speech", "voice_responses", {"limit": 5}),
        ("codex_delegation", "codex_capability_status", {"include_tools": True, "limit": 20}),
        (
            "codex_delegation",
            "codex_cli_plan",
            {
                "objective": "Inspect the repository and summarize the test command without editing files.",
                "context": "Skill smoke dry-run only.",
                "working_directory": ".",
                "preferred_sandbox": "read-only",
                "max_timeout_seconds": 60,
            },
        ),
        (
            "taskflow",
            "autonomous_task_graph_create",
            {
                "goal_title": "Skill smoke task graph",
                "success_criteria": ["Task graph exists"],
                "tasks": [
                    {"task_id": "inspect", "title": "Inspect capability", "owner": "planner"},
                    {"task_id": "verify", "title": "Verify result", "owner": "reviewer", "depends_on": ["inspect"]},
                ],
            },
        ),
        (
            "taskflow",
            "multi_agent_coordinate",
            {
                "goal_title": "Skill smoke coordination",
                "success_criteria": ["Specialist graph exists"],
                "specialists": [
                    {"name": "planner", "purpose": "Plan the smoke", "contract": "Return exact verification steps.", "tools": ["tool_describe"]},
                    {"name": "reviewer", "purpose": "Review the smoke", "contract": "Check evidence before completion.", "tools": ["capability_surface"]},
                ],
                "tasks": [
                    {"task_id": "plan", "title": "Plan smoke", "owner": "planner"},
                    {"task_id": "review", "title": "Review smoke", "owner": "reviewer", "depends_on": ["plan"]},
                ],
            },
        ),
        ("taskflow", "multi_agent_board", {"limit": 10}),
        ("taskflow", "autonomous_queue_status", {"limit": 10}),
        ("external_cli_companions", "external_integrations_status", {"probe_screenpipe": False}),
    ]
    for section, tool_name, payload in scenarios:
        execution_config = dry_config if tool_name in {"codex_cli_plan"} else config
        result = tools[tool_name].execute(payload, execution_config)
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
