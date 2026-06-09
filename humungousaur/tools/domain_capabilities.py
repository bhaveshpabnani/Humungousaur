from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_TEXT_CHARS = 80_000
MAX_ITEMS = 500


class DomainCapabilityTool(Tool):
    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        super().__init__(
            name=str(spec["name"]),
            description=str(spec["description"]),
            risk_level=RiskLevel[str(spec.get("risk", "MEDIUM"))],
            requires_approval=bool(spec.get("requires_approval", False)),
            input_schema=object_input_schema(
                {
                    "title": {"type": "string", "description": "Human-readable title for the operation or artifact."},
                    "action": {"type": "string", "description": "Optional action override such as create, search, run, list, draft, or prepare."},
                    "query": {"type": "string", "description": "Search query, prompt, username, target, or domain depending on the tool."},
                    "content": {"type": "string", "description": "Primary body text, code, notes, prompt, or message content."},
                    "target": {"type": "string", "description": "Provider, local app, repo, URL, account, binary, model, device, or deployment target."},
                    "items": {"type": "array", "items": {"type": "object"}, "description": "Structured rows, tasks, scenes, flashcards, sections, or steps."},
                    "params": {"type": "object", "description": "Tool-specific structured parameters."},
                    "filename": {"type": "string", "description": "Optional output filename for created local artifacts."},
                    "approved": {"type": "boolean", "description": "Set true only after the user approves live local/provider side effects."},
                    "reason": {"type": "string", "description": "Why this capability tool should run."},
                },
                required=["reason"],
            ),
            capability_group=str(spec.get("group", "domain_capability")),
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        load_workspace_environment(normalized.workspace)
        title = _bounded_text(tool_input.get("title")) or _title_from_name(self.name)
        reason = _bounded_text(tool_input.get("reason"))
        if not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "A reason is required.")
        content = _bounded_text(tool_input.get("content"), MAX_TEXT_CHARS)
        query = _bounded_text(tool_input.get("query"))
        target = _bounded_text(tool_input.get("target"))
        params = tool_input.get("params") if isinstance(tool_input.get("params"), dict) else {}
        items = _object_list(tool_input.get("items"))
        readiness = _readiness(self.spec)
        if self.spec.get("live") and not bool(tool_input.get("approved", False)):
            packet = _capability_packet(self.spec, title=title, reason=reason, query=query, content=content, target=target, params=params, items=items, readiness=readiness)
            return ToolResult(self.name, ActionStatus.NEEDS_APPROVAL, self.risk_level, f"{self.name} requires approval before live execution.", {"packet": packet, "readiness": readiness})
        runner = _RUNNERS.get(self.name)
        if runner is not None:
            return runner(self, tool_input, config, title, reason, query, content, target, params, items, readiness)
        return _write_capability_artifact(self, tool_input, config, title, reason, query, content, target, params, items, readiness)


def build_domain_capability_tools(group: str) -> dict[str, Tool]:
    return {tool.name: tool for tool in [DomainCapabilityTool(spec) for spec in specs_for_group(group)]}


def specs_for_group(group: str) -> list[dict[str, Any]]:
    return [spec for spec in NATIVE_DOMAIN_CAPABILITY_SPECS if spec.get("group") == group]


def _write_capability_artifact(
    tool: DomainCapabilityTool,
    tool_input: dict[str, Any],
    config: AgentConfig,
    title: str,
    reason: str,
    query: str,
    content: str,
    target: str,
    params: dict[str, Any],
    items: list[dict[str, Any]],
    readiness: dict[str, Any],
    *,
    extra_files: dict[str, str] | None = None,
) -> ToolResult:
    normalized = config.normalized()
    packet = _capability_packet(tool.spec, title=title, reason=reason, query=query, content=content, target=target, params=params, items=items, readiness=readiness)
    subdir = str(tool.spec.get("subdir") or tool.spec.get("group") or "native")
    filename = _safe_filename(str(tool_input.get("filename") or f"{tool.name}-{uuid4().hex[:8]}.md"), ".md")
    markdown_path = (normalized.data_dir / "domain_capabilities" / subdir / filename).resolve()
    if not _is_within(markdown_path, normalized.allowed_write_roots):
        return ToolResult(tool.name, ActionStatus.BLOCKED, tool.risk_level, "Capability artifact path is outside allowed write roots.")
    markdown = _render_packet_markdown(packet)
    if config.dry_run:
        return ToolResult(tool.name, ActionStatus.SKIPPED, tool.risk_level, f"Dry run: would create native capability artifact {markdown_path}.", {"path": str(markdown_path), "packet": packet, "readiness": readiness})
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    json_path = markdown_path.with_suffix(".json")
    json_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    written = {"markdown_path": str(markdown_path), "json_path": str(json_path)}
    for suffix, text in (extra_files or {}).items():
        path = markdown_path.with_suffix(suffix)
        path.write_text(text, encoding="utf-8")
        written[f"{suffix.lstrip('.')}_path"] = str(path)
    return ToolResult(
        tool.name,
        ActionStatus.SUCCEEDED,
        tool.risk_level,
        f"Created native capability artifact {markdown_path}.",
        {"packet": packet, "readiness": readiness, **written, "source": tool.name},
    )


def _apple_notes_create(tool: DomainCapabilityTool, tool_input: dict[str, Any], config: AgentConfig, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> ToolResult:
    if config.dry_run:
        return _write_capability_artifact(tool, tool_input, config, title, reason, query, content, target, params, items, readiness)
    if platform.system() != "Darwin" or shutil.which("osascript") is None:
        return ToolResult(tool.name, ActionStatus.BLOCKED, tool.risk_level, "Apple Notes live create requires macOS with osascript.", {"readiness": readiness})
    if not content.strip():
        return ToolResult(tool.name, ActionStatus.FAILED, tool.risk_level, "content is required to create an Apple Note.")
    script = [
        "osascript",
        "-e",
        'tell application "Notes"',
        "-e",
        f'make new note with properties {{name:{json.dumps(title)}, body:{json.dumps(content)}}}',
        "-e",
        "end tell",
    ]
    result = subprocess.run(script, text=True, capture_output=True, timeout=20)
    status = ActionStatus.SUCCEEDED if result.returncode == 0 else ActionStatus.FAILED
    return ToolResult(tool.name, status, tool.risk_level, "Created Apple Note." if status == ActionStatus.SUCCEEDED else "Apple Notes create failed.", {"stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:], "readiness": readiness})


def _apple_notes_search(tool: DomainCapabilityTool, tool_input: dict[str, Any], config: AgentConfig, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> ToolResult:
    if platform.system() != "Darwin" or shutil.which("osascript") is None:
        return _write_capability_artifact(tool, tool_input, config, title, reason, query, content, target, params, items, readiness)
    if not query.strip():
        return ToolResult(tool.name, ActionStatus.FAILED, tool.risk_level, "query is required to search Apple Notes.")
    script = "\n".join(
        [
            'tell application "Notes"',
            "set output to {}",
            "repeat with n in notes",
            f'if name of n contains {json.dumps(query)} or body of n contains {json.dumps(query)} then set end of output to name of n',
            "end repeat",
            "return output as string",
            "end tell",
        ]
    )
    result = subprocess.run(["osascript", "-e", script], text=True, capture_output=True, timeout=20)
    status = ActionStatus.SUCCEEDED if result.returncode == 0 else ActionStatus.FAILED
    return ToolResult(tool.name, status, tool.risk_level, "Searched Apple Notes." if status == ActionStatus.SUCCEEDED else "Apple Notes search failed.", {"matches_text": result.stdout[:8000], "stderr": result.stderr[-4000:], "readiness": readiness})


def _apple_reminders_create(tool: DomainCapabilityTool, tool_input: dict[str, Any], config: AgentConfig, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> ToolResult:
    if config.dry_run:
        return _write_capability_artifact(tool, tool_input, config, title, reason, query, content, target, params, items, readiness)
    if platform.system() != "Darwin" or shutil.which("osascript") is None:
        return ToolResult(tool.name, ActionStatus.BLOCKED, tool.risk_level, "Apple Reminders live create requires macOS with osascript.", {"readiness": readiness})
    body = content or query or title
    script = [
        "osascript",
        "-e",
        'tell application "Reminders"',
        "-e",
        f'make new reminder with properties {{name:{json.dumps(body)}}}',
        "-e",
        "end tell",
    ]
    result = subprocess.run(script, text=True, capture_output=True, timeout=20)
    status = ActionStatus.SUCCEEDED if result.returncode == 0 else ActionStatus.FAILED
    return ToolResult(tool.name, status, tool.risk_level, "Created Apple Reminder." if status == ActionStatus.SUCCEEDED else "Apple Reminders create failed.", {"stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:], "readiness": readiness})


def _apple_reminders_list(tool: DomainCapabilityTool, tool_input: dict[str, Any], config: AgentConfig, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> ToolResult:
    if platform.system() != "Darwin" or shutil.which("osascript") is None:
        return _write_capability_artifact(tool, tool_input, config, title, reason, query, content, target, params, items, readiness)
    script = 'tell application "Reminders" to return name of reminders whose completed is false as string'
    result = subprocess.run(["osascript", "-e", script], text=True, capture_output=True, timeout=20)
    status = ActionStatus.SUCCEEDED if result.returncode == 0 else ActionStatus.FAILED
    return ToolResult(tool.name, status, tool.risk_level, "Listed incomplete Apple Reminders." if status == ActionStatus.SUCCEEDED else "Apple Reminders list failed.", {"reminders_text": result.stdout[:8000], "stderr": result.stderr[-4000:], "readiness": readiness})


def _imessage_send_prepare(tool: DomainCapabilityTool, tool_input: dict[str, Any], config: AgentConfig, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> ToolResult:
    if not target:
        return ToolResult(tool.name, ActionStatus.FAILED, tool.risk_level, "target phone/email is required for iMessage send preparation.")
    if not content:
        return ToolResult(tool.name, ActionStatus.FAILED, tool.risk_level, "content is required for iMessage send preparation.")
    return _write_capability_artifact(tool, tool_input, config, title, reason, query, content, target, params, items, readiness)


def _docker_container_list(tool: DomainCapabilityTool, tool_input: dict[str, Any], config: AgentConfig, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> ToolResult:
    docker = shutil.which("docker")
    if docker is None:
        return ToolResult(tool.name, ActionStatus.BLOCKED, tool.risk_level, "Docker CLI is not installed or not on PATH.", {"readiness": readiness})
    result = subprocess.run([docker, "ps", "-a", "--format", "{{json .}}"], text=True, capture_output=True, timeout=20)
    if result.returncode != 0:
        return ToolResult(tool.name, ActionStatus.FAILED, tool.risk_level, "Docker container list failed.", {"stderr": result.stderr[-4000:], "readiness": readiness})
    containers = []
    for line in result.stdout.splitlines():
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            containers.append({"raw": line})
    return ToolResult(tool.name, ActionStatus.SUCCEEDED, tool.risk_level, f"Listed {len(containers)} Docker container(s).", {"containers": containers, "readiness": readiness})


def _creative_file(tool: DomainCapabilityTool, tool_input: dict[str, Any], config: AgentConfig, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> ToolResult:
    kind = str(tool.spec.get("kind") or "")
    extra = _creative_extra_files(kind, title, query, content, params, items)
    return _write_capability_artifact(tool, tool_input, config, title, reason, query, content, target, params, items, readiness, extra_files=extra)


def _cli_prepare(tool: DomainCapabilityTool, tool_input: dict[str, Any], config: AgentConfig, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> ToolResult:
    command = _command_for(tool.spec, query=query, content=content, target=target, params=params)
    params = {**params, "prepared_command": command, "runtime_readiness": readiness}
    return _write_capability_artifact(tool, tool_input, config, title, reason, query, content, target, params, items, readiness)


_RUNNERS: dict[str, Callable[..., ToolResult]] = {
    "apple_notes_create": _apple_notes_create,
    "apple_notes_search": _apple_notes_search,
    "apple_reminders_create": _apple_reminders_create,
    "apple_reminders_list": _apple_reminders_list,
    "imessage_send_prepare": _imessage_send_prepare,
    "docker_container_list": _docker_container_list,
}


def _spec(name: str, group: str, description: str, *, subdir: str = "", risk: str = "MEDIUM", live: bool = False, requires_approval: bool = False, env: list[str] | None = None, bins: list[str] | None = None, kind: str = "", runner: str = "") -> dict[str, Any]:
    return {"name": name, "group": group, "description": description, "subdir": subdir or group, "risk": risk, "live": live, "requires_approval": requires_approval, "env": env or [], "bins": bins or [], "kind": kind, "runner": runner}


NATIVE_DOMAIN_CAPABILITY_SPECS: list[dict[str, Any]] = [
    _spec("apple_notes_search", "apple", "Search Apple Notes through the local macOS Notes app when available, otherwise create a bounded search packet.", subdir="apple/notes", risk="LOW", bins=["osascript"]),
    _spec("apple_notes_create", "apple", "Create an Apple Note through the local macOS Notes app after approval, or create a note packet in dry-run/unavailable environments.", subdir="apple/notes", live=True, requires_approval=True, bins=["osascript"]),
    _spec("apple_notes_append_prepare", "apple", "Prepare an Apple Notes append/update packet with target note, content, and approval metadata.", subdir="apple/notes"),
    _spec("apple_reminders_list", "apple", "List incomplete Apple Reminders through the local macOS Reminders app when available, otherwise create a bounded list packet.", subdir="apple/reminders", risk="LOW", bins=["osascript"]),
    _spec("apple_reminders_create", "apple", "Create an Apple Reminder through the local macOS Reminders app after approval, or create a reminder packet in dry-run/unavailable environments.", subdir="apple/reminders", live=True, requires_approval=True, bins=["osascript"]),
    _spec("apple_reminders_complete_prepare", "apple", "Prepare an approval-gated Apple Reminders completion packet.", subdir="apple/reminders"),
    _spec("find_my_open", "apple", "Open or prepare a Find My app workflow packet with platform readiness and privacy boundary.", subdir="apple/find-my", bins=["open"]),
    _spec("find_my_location_request_prepare", "apple", "Prepare a privacy-gated Find My location request packet without scraping location data.", subdir="apple/find-my", requires_approval=True),
    _spec("imessage_draft_create", "apple", "Create a local iMessage draft artifact for review before any send action.", subdir="apple/imessage"),
    _spec("imessage_send_prepare", "apple", "Prepare an approval-gated iMessage send packet with recipient and message body.", subdir="apple/imessage", requires_approval=True, bins=["osascript"]),
    _spec("imessage_transcript_request_prepare", "apple", "Prepare a privacy-scoped iMessage transcript request packet.", subdir="apple/imessage", requires_approval=True),
    _spec("macos_app_workflow_prepare", "apple", "Prepare a native macOS app-control workflow with UI observations, intended actions, and approval gates.", subdir="apple/macos"),
    _spec("ascii_video_render_plan_create", "media", "Create an ASCII/video render plan plus local text frame artifact.", subdir="creative/ascii-video", kind="ascii"),
    _spec("comfyui_workflow_prepare", "media", "Create a ComfyUI workflow JSON packet with prompts, nodes, model requirements, and local server readiness.", subdir="creative/comfyui", bins=["python"]),
    _spec("manim_scene_create", "media", "Create a Manim scene Python file and render command packet.", subdir="creative/manim", bins=["manim"], kind="manim"),
    _spec("p5js_sketch_create", "media", "Create a p5.js sketch HTML/JS artifact.", subdir="creative/p5js", kind="p5js"),
    _spec("pretext_project_prepare", "media", "Create a PreTeXt XML source artifact and build command packet.", subdir="creative/pretext", bins=["pretext"], kind="pretext"),
    _spec("sketch_file_prepare", "media", "Create a Sketch design handoff packet with layers, assets, and export intent.", subdir="creative/sketch"),
    _spec("touchdesigner_network_prepare", "media", "Create a TouchDesigner network specification packet.", subdir="creative/touchdesigner"),
    _spec("blender_mcp_command_prepare", "media", "Create a Blender MCP command/script packet with scene operations and readiness.", subdir="creative/blender", bins=["blender"], kind="blender"),
    _spec("hyperframes_composition_prepare", "media", "Create a HyperFrames composition HTML packet and render command.", subdir="creative/hyperframes", bins=["hyperframes"], kind="hyperframes"),
    _spec("meme_asset_create", "media", "Create a local meme SVG asset and metadata packet.", subdir="creative/meme", kind="meme"),
    _spec("pixel_art_create", "media", "Create a local pixel-art SVG asset and palette metadata.", subdir="creative/pixel-art", kind="pixel"),
    _spec("music_workflow_prepare", "media", "Create a specialist music workflow packet with arrangement, stems, model/provider boundary, and review steps.", subdir="creative/music"),
]

NATIVE_DOMAIN_CAPABILITY_SPECS += [
    _spec("jupyter_live_kernel_execute_prepare", "mlops", "Prepare or run a Jupyter live-kernel execution packet with notebook/script boundaries.", subdir="mlops/jupyter", bins=["jupyter"], runner="cli"),
    _spec("lm_eval_run_prepare", "mlops", "Prepare an lm-eval benchmark command with model, tasks, batch, and output settings.", subdir="mlops/lm-eval", bins=["lm_eval"], runner="cli"),
    _spec("wandb_run_prepare", "mlops", "Prepare a W&B run, sweep, artifact, or report packet with credential readiness.", subdir="mlops/wandb", env=["WANDB_API_KEY"], bins=["wandb"], runner="cli"),
    _spec("hugging_face_operation_prepare", "mlops", "Prepare Hugging Face Hub/model/dataset operations with token readiness.", subdir="mlops/hugging-face", env=["HF_TOKEN"], bins=["huggingface-cli"], runner="cli"),
    _spec("llama_cpp_command_prepare", "mlops", "Prepare llama.cpp build, quantize, server, or inference command packets.", subdir="mlops/llama-cpp", bins=["llama-cli"], runner="cli"),
    _spec("vllm_server_prepare", "mlops", "Prepare a vLLM server/inference command packet with GPU/runtime readiness.", subdir="mlops/vllm", bins=["python"], runner="cli"),
    _spec("chroma_collection_prepare", "mlops", "Prepare a Chroma collection ingest/query packet.", subdir="mlops/chroma", runner="cli"),
    _spec("faiss_index_prepare", "mlops", "Prepare a FAISS index build/search packet.", subdir="mlops/faiss", runner="cli"),
    _spec("qdrant_collection_prepare", "mlops", "Prepare a Qdrant collection operation packet with endpoint readiness.", subdir="mlops/qdrant", env=["QDRANT_URL"], runner="cli"),
    _spec("pinecone_index_prepare", "mlops", "Prepare a Pinecone index operation packet with API-key readiness.", subdir="mlops/pinecone", env=["PINECONE_API_KEY"], runner="cli"),
    _spec("peft_training_prepare", "mlops", "Prepare a PEFT training configuration packet.", subdir="mlops/peft", runner="cli"),
    _spec("modal_job_prepare", "mlops", "Prepare a Modal job/deploy packet with token readiness.", subdir="mlops/modal", env=["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"], bins=["modal"], runner="cli"),
    _spec("lambda_labs_instance_prepare", "mlops", "Prepare a Lambda Labs instance/job request packet with API-key readiness.", subdir="mlops/lambda-labs", env=["LAMBDA_API_KEY"], runner="cli"),
    _spec("pytorch_training_script_create", "mlops", "Create a PyTorch training script artifact and run packet.", subdir="mlops/pytorch", bins=["python"], kind="python"),
    _spec("tensorrt_llm_build_prepare", "mlops", "Prepare a TensorRT-LLM build/serve packet with GPU readiness.", subdir="mlops/tensorrt-llm", runner="cli"),
    _spec("axolotl_config_create", "mlops", "Create an Axolotl training configuration packet.", subdir="mlops/axolotl", bins=["axolotl"], runner="cli"),
    _spec("trl_training_prepare", "mlops", "Prepare a TRL training or RLHF packet.", subdir="mlops/trl", runner="cli"),
    _spec("unsloth_training_prepare", "mlops", "Prepare an Unsloth fine-tuning packet.", subdir="mlops/unsloth", runner="cli"),
    _spec("whisper_transcription_prepare", "mlops", "Prepare a Whisper transcription command packet.", subdir="mlops/whisper", bins=["whisper"], runner="cli"),
    _spec("dspy_program_create", "mlops", "Create a DSPy program/evaluation artifact.", subdir="mlops/dspy", kind="python"),
    _spec("stable_diffusion_generation_prepare", "mlops", "Prepare a Stable Diffusion generation packet with model/provider readiness.", subdir="mlops/stable-diffusion", runner="cli"),
    _spec("llava_inference_prepare", "mlops", "Prepare an LLaVA multimodal inference packet.", subdir="mlops/llava", runner="cli"),
    _spec("model_training_plan_create", "mlops", "Create a general model training plan with data, eval, hardware, and rollback sections.", subdir="mlops/training"),
    _spec("model_inference_plan_create", "mlops", "Create a general model inference/deployment plan with latency, cost, and safety boundaries.", subdir="mlops/inference"),
]

NATIVE_DOMAIN_CAPABILITY_SPECS += [
    _spec("polymarket_query_prepare", "research", "Prepare a Polymarket market lookup/research packet.", subdir="research/polymarket"),
    _spec("llm_wiki_build_prepare", "research", "Prepare an LLM wiki build/index/query packet.", subdir="research/llm-wiki"),
    _spec("osint_case_create", "research", "Create a defensive OSINT case packet with scope, sources, and evidence boundaries.", subdir="research/osint"),
    _spec("bioinformatics_pipeline_prepare", "research", "Prepare a bioinformatics pipeline packet with input data, tools, and reproducibility notes.", subdir="research/bioinformatics"),
    _spec("drug_discovery_screen_prepare", "research", "Prepare a drug discovery screening packet with targets, compounds, and safety boundaries.", subdir="research/drug-discovery"),
    _spec("domain_intel_report_create", "research", "Create a domain intelligence report packet with DNS, WHOIS, web, and certificate evidence slots.", subdir="research/domain-intel"),
    _spec("gitnexus_repo_intel_prepare", "research", "Prepare a Git repository intelligence packet.", subdir="research/gitnexus"),
    _spec("scrapling_scrape_prepare", "research", "Prepare a Scrapling extraction packet with selectors and rate limits.", subdir="research/scrapling", bins=["python"]),
    _spec("searxng_search_prepare", "research", "Prepare a SearXNG search packet with endpoint readiness.", subdir="research/searxng", env=["SEARXNG_URL"]),
    _spec("duckduckgo_search_prepare", "research", "Prepare a DuckDuckGo search packet with query and source-citation boundaries.", subdir="research/duckduckgo"),
    _spec("parallel_research_plan_create", "research", "Create a parallel research plan with source lanes, synthesis rules, and verification checklist.", subdir="research/parallel"),
    _spec("sherlock_username_search_prepare", "research", "Prepare a Sherlock username-search packet with authorization and rate-limit notes.", subdir="research/sherlock", bins=["sherlock"]),
    _spec("onepassword_item_request_prepare", "research", "Prepare a 1Password item request packet without exposing raw secrets.", subdir="research/onepassword", bins=["op"]),
    _spec("oss_forensics_report_create", "research", "Create an open-source software forensics report packet.", subdir="research/oss-forensics"),
    _spec("web_pentest_scope_prepare", "research", "Prepare a defensive web pentest scope packet with authorization boundaries.", subdir="research/web-pentest", requires_approval=True),
]

NATIVE_DOMAIN_CAPABILITY_SPECS += [
    _spec("shopify_operation_prepare", "commerce", "Prepare a Shopify product/order/customer/admin operation packet with credential readiness.", subdir="productivity/shopify", env=["SHOPIFY_ADMIN_TOKEN"]),
    _spec("shop_app_order_prepare", "commerce", "Prepare a Shop app order tracking or shopping workflow packet.", subdir="productivity/shop-app"),
    _spec("canvas_course_packet_prepare", "productivity", "Prepare a Canvas LMS course/assignment/page operation packet.", subdir="productivity/canvas", env=["CANVAS_API_TOKEN"]),
    _spec("here_now_context_prepare", "productivity", "Create a Here Now context packet for local presence, focus, or room-state workflows.", subdir="productivity/here-now"),
    _spec("memento_flashcards_create", "productivity", "Create a flashcard deck artifact compatible with spaced-repetition workflows.", subdir="productivity/memento"),
    _spec("siyuan_note_prepare", "productivity", "Prepare a SiYuan note/block operation packet.", subdir="productivity/siyuan", env=["SIYUAN_TOKEN"]),
    _spec("telephony_call_prepare", "productivity", "Prepare a telephony call/SMS packet with approval and provider readiness.", subdir="productivity/telephony", env=["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"], requires_approval=True),
    _spec("agentmail_operation_prepare", "productivity", "Prepare an AgentMail send/search/mailbox operation packet.", subdir="productivity/agentmail", env=["AGENTMAIL_API_KEY"], requires_approval=True),
    _spec("himalaya_email_operation_prepare", "productivity", "Prepare a Himalaya CLI email operation packet.", subdir="productivity/himalaya", bins=["himalaya"], requires_approval=True),
    _spec("openhue_scene_prepare", "productivity", "Prepare an OpenHue scene/light operation packet.", subdir="productivity/openhue", env=["HUE_BRIDGE_URL", "HUE_API_KEY"], requires_approval=True),
    _spec("x_social_post_prepare", "productivity", "Prepare an X/social post, thread, or search packet with provider readiness.", subdir="productivity/x-social", env=["XAI_API_KEY"], requires_approval=True),
    _spec("finance_model_create", "productivity", "Create a finance-model artifact with assumptions, cash flows, scenarios, and sensitivity tables.", subdir="productivity/finance", kind="finance"),
]

NATIVE_DOMAIN_CAPABILITY_SPECS += [
    _spec("agent_delegation_prepare", "devops", "Prepare a native agent delegation packet with objective, constraints, tools, and verification gates.", subdir="devops/delegation"),
    _spec("honcho_processfile_create", "devops", "Create a Honcho/Procfile process orchestration artifact.", subdir="devops/honcho", bins=["honcho"], kind="procfile"),
    _spec("openhands_task_prepare", "devops", "Prepare an OpenHands task handoff packet.", subdir="devops/openhands", requires_approval=True),
    _spec("antigravity_cli_task_prepare", "devops", "Prepare an Antigravity CLI task packet.", subdir="devops/antigravity", bins=["antigravity"], requires_approval=True),
    _spec("blackbox_prompt_prepare", "devops", "Prepare a Blackbox coding task packet.", subdir="devops/blackbox", requires_approval=True),
    _spec("grok_request_prepare", "devops", "Prepare a Grok/xAI request packet with API readiness.", subdir="devops/grok", env=["XAI_API_KEY"], requires_approval=True),
    _spec("docker_container_list", "devops", "List local Docker containers through the Docker CLI.", subdir="devops/docker", risk="LOW", bins=["docker"]),
    _spec("docker_compose_prepare", "devops", "Prepare a Docker Compose service packet.", subdir="devops/docker", bins=["docker"]),
    _spec("s6_service_prepare", "devops", "Prepare an s6 service definition packet.", subdir="devops/s6", bins=["s6-svscan"]),
    _spec("pinggy_tunnel_prepare", "devops", "Prepare a Pinggy tunnel command packet with exposure warnings.", subdir="devops/pinggy", bins=["ssh"], requires_approval=True),
    _spec("watcher_create", "devops", "Create a file/process watcher packet with trigger, debounce, and action boundaries.", subdir="devops/watchers"),
    _spec("kanban_orchestrator_plan_create", "devops", "Create a kanban orchestrator plan with lanes, dependencies, workers, and review gates.", subdir="devops/kanban"),
    _spec("kanban_worker_packet_create", "devops", "Create a kanban worker packet with assigned task, context, heartbeat, and done criteria.", subdir="devops/kanban"),
]


for spec in NATIVE_DOMAIN_CAPABILITY_SPECS:
    if spec.get("runner") == "cli":
        _RUNNERS.setdefault(str(spec["name"]), _cli_prepare)
    if spec.get("kind") in {"ascii", "manim", "p5js", "pretext", "blender", "hyperframes", "meme", "pixel", "python", "finance", "procfile"}:
        _RUNNERS.setdefault(str(spec["name"]), _creative_file)


def _readiness(spec: dict[str, Any]) -> dict[str, Any]:
    missing_env = [name for name in spec.get("env", []) if not os.environ.get(str(name))]
    missing_bins = [name for name in spec.get("bins", []) if shutil.which(str(name)) is None]
    return {
        "platform": platform.system(),
        "required_env": list(spec.get("env", [])),
        "missing_env": missing_env,
        "required_binaries": list(spec.get("bins", [])),
        "missing_binaries": missing_bins,
        "configured": not missing_env and not missing_bins,
    }


def _capability_packet(spec: dict[str, Any], *, title: str, reason: str, query: str, content: str, target: str, params: dict[str, Any], items: list[dict[str, Any]], readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "packet_id": f"{spec['name']}-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool": spec["name"],
        "group": spec.get("group", ""),
        "title": title,
        "reason": reason,
        "query": query,
        "target": target,
        "content": content,
        "items": items[:MAX_ITEMS],
        "params": _json_safe(params),
        "readiness": readiness,
        "approval_required": bool(spec.get("requires_approval") or spec.get("live")),
        "live_action": bool(spec.get("live")),
        "implementation_boundary": "native_humungousaur_tool",
    }


def _render_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# {packet['title']}",
        "",
        f"- Tool: `{packet['tool']}`",
        f"- Packet: `{packet['packet_id']}`",
        f"- Created: {packet['created_at']}",
        f"- Approval required: {packet['approval_required']}",
        f"- Live action: {packet['live_action']}",
        "",
        "## Reason",
        packet["reason"] or "-",
        "",
        "## Target",
        packet["target"] or "-",
        "",
        "## Query",
        packet["query"] or "-",
        "",
        "## Content",
        packet["content"] or "-",
        "",
        "## Items",
    ]
    if packet["items"]:
        for item in packet["items"]:
            lines.append(f"- {json.dumps(item, ensure_ascii=False, sort_keys=True)}")
    else:
        lines.append("-")
    lines.extend(["", "## Params", "```json", json.dumps(packet["params"], indent=2, ensure_ascii=False, sort_keys=True), "```", "", "## Readiness", "```json", json.dumps(packet["readiness"], indent=2, ensure_ascii=False, sort_keys=True), "```"])
    return "\n".join(lines) + "\n"


def _creative_extra_files(kind: str, title: str, query: str, content: str, params: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, str]:
    prompt = content or query or title
    if kind == "ascii":
        return {".txt": _ascii_frame(title, prompt)}
    if kind == "manim":
        return {".py": f"from manim import *\n\nclass NativeScene(Scene):\n    def construct(self):\n        title = Text({json.dumps(title)})\n        self.play(Write(title))\n        self.wait(1)\n"}
    if kind == "p5js":
        return {".html": f"<main></main><script src=\"https://cdn.jsdelivr.net/npm/p5@1.9.0/lib/p5.min.js\"></script><script>function setup(){{createCanvas(800,450);}}function draw(){{background(250);textSize(32);text({json.dumps(title)},40,80);}}</script>\n"}
    if kind == "pretext":
        return {".xml": f"<pretext><article><title>{_xml_escape(title)}</title><p>{_xml_escape(prompt)}</p></article></pretext>\n"}
    if kind == "blender":
        return {".py": f"import bpy\nbpy.ops.object.text_add()\nbpy.context.object.data.body = {json.dumps(title)}\n"}
    if kind == "hyperframes":
        return {".html": f"<section style=\"font:48px sans-serif;display:grid;place-items:center;height:100vh\"><h1>{_html_escape(title)}</h1></section>\n"}
    if kind == "meme":
        return {".svg": _svg_card(title, prompt, width=900, height=700)}
    if kind == "pixel":
        return {".svg": _pixel_svg(title, items)}
    if kind == "python":
        return {".py": f"def main():\n    print({json.dumps(title)})\n\nif __name__ == '__main__':\n    main()\n"}
    if kind == "finance":
        rows = items or [{"label": "Base", "value": params.get("base_value", 0)}, {"label": "Upside", "value": params.get("upside_value", 0)}]
        csv = "scenario,value\n" + "\n".join(f"{_csv_cell(str(row.get('label','scenario')))},{_csv_cell(str(row.get('value',0)))}" for row in rows) + "\n"
        return {".csv": csv}
    if kind == "procfile":
        rows = items or [{"name": "web", "command": content or "python app.py"}]
        return {".procfile": "\n".join(f"{row.get('name','worker')}: {row.get('command','echo ready')}" for row in rows) + "\n"}
    return {}


def _command_for(spec: dict[str, Any], *, query: str, content: str, target: str, params: dict[str, Any]) -> list[str]:
    name = str(spec["name"])
    model = target or str(params.get("model") or "")
    if name == "lm_eval_run_prepare":
        return ["lm_eval", "--model", model or "hf", "--tasks", query or str(params.get("tasks") or "hellaswag")]
    if name == "wandb_run_prepare":
        return ["wandb", "init", "--project", target or str(params.get("project") or "humungousaur")]
    if name == "hugging_face_operation_prepare":
        return ["huggingface-cli", "download", model or query or "<repo-id>"]
    if name == "vllm_server_prepare":
        return ["python", "-m", "vllm.entrypoints.openai.api_server", "--model", model or "<model>"]
    if name == "whisper_transcription_prepare":
        return ["whisper", target or "<audio-file>"]
    if name == "modal_job_prepare":
        return ["modal", "run", target or "app.py"]
    return [str(params.get("binary") or name.replace("_prepare", "").replace("_create", "")), query or target or "<target>"]


def _bounded_text(value: Any, limit: int = 10_000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    output = []
    for item in value[:MAX_ITEMS]:
        if isinstance(item, dict):
            output.append(_json_safe(item))
        else:
            output.append({"value": str(item)[:1000]})
    return output


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_json_safe(item) for item in value]
        return str(value)


def _safe_filename(value: str, suffix: str) -> str:
    name = Path(value).name.strip() or f"artifact{suffix}"
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in name)
    if not cleaned.lower().endswith(suffix):
        cleaned += suffix
    return cleaned


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _title_from_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split("_"))


def _ascii_frame(title: str, prompt: str) -> str:
    body = prompt[:60] or title
    border = "+" + "-" * 70 + "+"
    return f"{border}\n| {title[:66].center(66)} |\n| {body[:66].center(66)} |\n{border}\n"


def _svg_card(title: str, prompt: str, *, width: int, height: int) -> str:
    return f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\"><rect width=\"100%\" height=\"100%\" fill=\"#f8f5ef\"/><text x=\"40\" y=\"90\" font-size=\"48\" font-family=\"Arial\" fill=\"#111\">{_html_escape(title)}</text><text x=\"40\" y=\"170\" font-size=\"28\" font-family=\"Arial\" fill=\"#333\">{_html_escape(prompt[:80])}</text></svg>\n"


def _pixel_svg(title: str, items: list[dict[str, Any]]) -> str:
    colors = [str(item.get("color") or "#222222") for item in items[:64]] or ["#111111", "#e4572e", "#17bebb", "#ffc914"]
    size = 24
    rects = []
    for index in range(64):
        x = (index % 8) * size
        y = (index // 8) * size
        rects.append(f"<rect x=\"{x}\" y=\"{y}\" width=\"{size}\" height=\"{size}\" fill=\"{_html_escape(colors[index % len(colors)])}\"/>")
    return f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"192\" height=\"230\" viewBox=\"0 0 192 230\">{''.join(rects)}<text x=\"0\" y=\"220\" font-size=\"16\" font-family=\"monospace\">{_html_escape(title[:18])}</text></svg>\n"


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _html_escape(value: str) -> str:
    return _xml_escape(value).replace('"', "&quot;")


def _csv_cell(value: str) -> str:
    if "," in value or "\n" in value or '"' in value:
        return '"' + value.replace('"', '""') + '"'
    return value
