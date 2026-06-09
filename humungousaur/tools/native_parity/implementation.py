from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema
from humungousaur.tools.code.implementation import PythonInterpreterTool


NATIVE_CORE_TOOLS = [
    "web_search",
    "web_extract",
    "terminal",
    "process",
    "read_file",
    "write_file",
    "patch",
    "search_files",
    "vision_analyze",
    "image_generate",
    "skills_list",
    "skill_view",
    "skill_manage",
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_back",
    "browser_press",
    "browser_get_images",
    "browser_vision",
    "browser_console",
    "browser_cdp",
    "browser_dialog",
    "text_to_speech",
    "todo",
    "memory",
    "session_search",
    "clarify",
    "execute_code",
    "delegate_task",
    "cronjob",
    "send_message",
    "ha_list_entities",
    "ha_get_state",
    "ha_list_services",
    "ha_call_service",
    "kanban_show",
    "kanban_list",
    "kanban_complete",
    "kanban_block",
    "kanban_heartbeat",
    "kanban_comment",
    "kanban_create",
    "kanban_link",
    "kanban_unblock",
    "computer_use",
]

NATIVE_TOOLSET_DEFINITIONS: dict[str, dict[str, Any]] = {
    "browser": {
        "description": "Browser automation for navigation, snapshots, clicks, typing, scrolling, CDP, dialogs, images, and web search.",
        "tools": [
            "browser_navigate",
            "browser_snapshot",
            "browser_click",
            "browser_type",
            "browser_scroll",
            "browser_back",
            "browser_press",
            "browser_get_images",
            "browser_vision",
            "browser_console",
            "browser_cdp",
            "browser_dialog",
            "web_search",
        ],
    },
    "clarify": {"description": "Ask the user clarifying questions.", "tools": ["clarify"]},
    "code_execution": {"description": "Run bounded Python scripts that can call tools programmatically.", "tools": ["execute_code"]},
    "computer_use": {"description": "Desktop control facade.", "tools": ["computer_use"]},
    "context_engine": {"description": "Runtime tools exposed by the active context engine.", "tools": []},
    "cronjob": {"description": "Scheduled task management.", "tools": ["cronjob"]},
    "debugging": {"description": "Debugging and troubleshooting toolkit.", "tools": ["terminal", "process"]},
    "delegation": {"description": "Spawn or queue isolated subagent tasks.", "tools": ["delegate_task"]},
    "discord": {"description": "Discord participation tools.", "tools": ["discord"]},
    "discord_admin": {"description": "Discord server administration tools.", "tools": ["discord_admin"]},
    "feishu_doc": {"description": "Read Feishu or Lark documents.", "tools": ["feishu_doc_read"]},
    "feishu_drive": {
        "description": "Feishu or Lark document comment operations.",
        "tools": [
            "feishu_drive_list_comments",
            "feishu_drive_list_comment_replies",
            "feishu_drive_reply_comment",
            "feishu_drive_add_comment",
        ],
    },
    "file": {"description": "File read, write, patch, and search tools.", "tools": ["read_file", "write_file", "patch", "search_files"]},
    "native-acp": {"description": "Editor integration toolset.", "tools": NATIVE_CORE_TOOLS[:25] + ["todo", "memory", "session_search", "execute_code", "delegate_task"]},
    "native-api-server": {"description": "HTTP API server toolset without interactive UI tools.", "tools": NATIVE_CORE_TOOLS[:25] + ["todo", "memory", "session_search", "execute_code", "delegate_task", "cronjob", "ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service"]},
    "native-cli": {"description": "Full interactive CLI toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-cron": {"description": "Default cron worker toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-bluebubbles": {"description": "BlueBubbles iMessage bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-dingtalk": {"description": "DingTalk bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-email": {"description": "Email bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-homeassistant": {"description": "Home Assistant bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-matrix": {"description": "Matrix bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-mattermost": {"description": "Mattermost bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-qqbot": {"description": "QQBot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-signal": {"description": "Signal bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-slack": {"description": "Slack bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-sms": {"description": "SMS bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-telegram": {"description": "Telegram bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-wecom": {"description": "WeCom bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-wecom-callback": {"description": "WeCom callback toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-weixin": {"description": "Weixin bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-whatsapp": {"description": "WhatsApp bot toolset.", "tools": NATIVE_CORE_TOOLS},
    "native-discord": {"description": "Discord bot toolset.", "tools": NATIVE_CORE_TOOLS + ["discord", "discord_admin"]},
    "native-feishu": {
        "description": "Feishu or Lark bot toolset.",
        "tools": NATIVE_CORE_TOOLS
        + [
            "feishu_doc_read",
            "feishu_drive_list_comments",
            "feishu_drive_list_comment_replies",
            "feishu_drive_reply_comment",
            "feishu_drive_add_comment",
        ],
    },
    "native-gateway": {"description": "Gateway union of messaging platform tools.", "tools": []},
    "native-webhook": {"description": "External webhook processing toolset.", "tools": ["web_search", "web_extract", "vision_analyze", "clarify"]},
    "native-yuanbao": {
        "description": "Yuanbao platform toolset.",
        "tools": NATIVE_CORE_TOOLS
        + ["yb_query_group_info", "yb_query_group_members", "yb_send_dm", "yb_search_sticker", "yb_send_sticker"],
    },
    "homeassistant": {"description": "Home Assistant smart-home control.", "tools": ["ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service"]},
    "image_gen": {"description": "Image generation.", "tools": ["image_generate"]},
    "kanban": {
        "description": "Kanban multi-agent coordination.",
        "tools": [
            "kanban_show",
            "kanban_list",
            "kanban_complete",
            "kanban_block",
            "kanban_heartbeat",
            "kanban_comment",
            "kanban_create",
            "kanban_link",
            "kanban_unblock",
        ],
    },
    "memory": {"description": "Persistent memory across sessions.", "tools": ["memory"]},
    "messaging": {"description": "Cross-platform message sending.", "tools": ["send_message"]},
    "moa": {"description": "Multi-model reasoning consensus.", "tools": ["mixture_of_agents"]},
    "safe": {"description": "Safe toolkit without terminal access.", "tools": []},
    "search": {"description": "Web search only.", "tools": ["web_search"]},
    "session_search": {"description": "Search prior sessions.", "tools": ["session_search"]},
    "skills": {"description": "Skill document management.", "tools": ["skills_list", "skill_view", "skill_manage"]},
    "spotify": {
        "description": "Spotify playback, search, playlist, album, and library tools.",
        "tools": [
            "spotify_playback",
            "spotify_devices",
            "spotify_queue",
            "spotify_search",
            "spotify_playlists",
            "spotify_albums",
            "spotify_library",
        ],
    },
    "terminal": {"description": "Terminal and process management.", "tools": ["terminal", "process"]},
    "todo": {"description": "Task planning and tracking.", "tools": ["todo"]},
    "tts": {"description": "Text to speech.", "tools": ["text_to_speech"]},
    "video": {"description": "Video analysis.", "tools": ["video_analyze"]},
    "video_gen": {"description": "Video generation.", "tools": ["video_generate"]},
    "vision": {"description": "Image analysis.", "tools": ["vision_analyze"]},
    "web": {"description": "Web research and extraction.", "tools": ["web_search", "web_extract"]},
    "x_search": {"description": "Search X posts and threads through a configured provider.", "tools": ["x_search"]},
    "yuanbao": {
        "description": "Yuanbao group info, member queries, DMs, and stickers.",
        "tools": ["yb_query_group_info", "yb_query_group_members", "yb_send_dm", "yb_search_sticker", "yb_send_sticker"],
    },
}

NATIVE_ALIAS_MAP = {
    "terminal": "run_shell_command",
    "web_extract": "fetch_web_page",
    "skills_list": "agent_skill_catalog",
    "skill_view": "agent_skill_read",
    "skill_manage": "agent_skill_import",
    "browser_navigate": "browser_live_navigate",
    "browser_snapshot": "browser_live_observe",
    "browser_click": "browser_live_click",
    "browser_type": "browser_live_type",
    "browser_scroll": "browser_live_scroll",
    "browser_back": "browser_live_back",
    "browser_press": "browser_live_press_key",
    "browser_cdp": "browser_live_evaluate_js",
    "text_to_speech": "voice_speak",
    "send_message": "channel_message_send",
}

BUILTIN_MCP_MANIFESTS = [
    {
        "server_id": "linear",
        "display_name": "Linear MCP",
        "status": "manifest_ready",
        "transport": "stdio",
        "tools": ["linear_search", "linear_create_issue", "linear_update_issue"],
        "required_env": ["LINEAR_API_KEY"],
        "optional_env": [],
        "oauth": {"supported": True, "env_fallback": "LINEAR_API_KEY"},
    },
    {
        "server_id": "n8n",
        "display_name": "n8n MCP",
        "status": "manifest_ready",
        "transport": "http",
        "tools": ["n8n_workflow_list", "n8n_workflow_run", "n8n_execution_get"],
        "required_env": ["N8N_API_KEY", "N8N_BASE_URL"],
        "optional_env": [],
        "oauth": {"supported": False, "env_fallback": "N8N_API_KEY"},
    },
]

NATIVE_PROVIDER_REGISTRY = [
    {"provider_id": "openai", "kind": "model", "status": "implemented", "required_env": ["OPENAI_API_KEY"]},
    {"provider_id": "groq", "kind": "model", "status": "implemented", "required_env": ["GROQ_API_KEY"]},
    {"provider_id": "ollama", "kind": "model", "status": "implemented", "required_env": []},
    {"provider_id": "xai", "kind": "model", "status": "contract_ready", "required_env": ["XAI_API_KEY"]},
    {"provider_id": "anthropic", "kind": "model", "status": "contract_ready", "required_env": ["ANTHROPIC_API_KEY"]},
    {"provider_id": "gemini", "kind": "model", "status": "contract_ready", "required_env": ["GEMINI_API_KEY"]},
    {"provider_id": "bedrock", "kind": "model", "status": "contract_ready", "required_env": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]},
    {"provider_id": "deepseek", "kind": "model", "status": "contract_ready", "required_env": ["DEEPSEEK_API_KEY"]},
    {"provider_id": "moonshot_kimi", "kind": "model", "status": "contract_ready", "required_env": ["MOONSHOT_API_KEY"]},
    {"provider_id": "openrouter", "kind": "model", "status": "contract_ready", "required_env": ["OPENROUTER_API_KEY"]},
    {"provider_id": "qwen_oauth", "kind": "model", "status": "contract_ready", "required_env": ["QWEN_ACCESS_TOKEN"]},
    {"provider_id": "huggingface", "kind": "model", "status": "contract_ready", "required_env": ["HF_TOKEN"]},
    {"provider_id": "nvidia", "kind": "model", "status": "contract_ready", "required_env": ["NVIDIA_API_KEY"]},
    {"provider_id": "alibaba", "kind": "model", "status": "contract_ready", "required_env": ["DASHSCOPE_API_KEY"]},
    {"provider_id": "langfuse", "kind": "observability", "status": "contract_ready", "required_env": ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]},
    {"provider_id": "nemo_relay", "kind": "observability", "status": "contract_ready", "required_env": ["NEMO_RELAY_URL"]},
]

NATIVE_RUNTIME_HOOKS = [
    {"hook_id": "llm.before_request", "event": "llm_call", "phase": "before", "status": "registered"},
    {"hook_id": "llm.after_response", "event": "llm_call", "phase": "after", "status": "registered"},
    {"hook_id": "tool.before_execute", "event": "tool_call", "phase": "before", "status": "registered"},
    {"hook_id": "tool.after_execute", "event": "tool_call", "phase": "after", "status": "registered"},
    {"hook_id": "session.started", "event": "session", "phase": "before", "status": "registered"},
    {"hook_id": "session.completed", "event": "session", "phase": "after", "status": "registered"},
    {"hook_id": "gateway.inbound", "event": "gateway", "phase": "before", "status": "registered"},
    {"hook_id": "gateway.outbound", "event": "gateway", "phase": "after", "status": "registered"},
]

NATIVE_SKILL_PACKS = [
    {"pack_id": "apple", "category": "apple", "skills": ["apple-notes", "apple-reminders", "find-my", "imessage", "macos-computer-use"]},
    {"pack_id": "creative_media", "category": "creative", "skills": ["ascii-art-video", "comfyui", "manim", "p5js", "pretext", "sketch", "touchdesigner", "blender-mcp", "hyperframes", "meme-generation", "pixel-art", "music-workflows"]},
    {"pack_id": "mlops_data_science", "category": "mlops", "skills": ["jupyter-live-kernel", "lm-eval", "wandb", "hugging-face", "llama-cpp", "vllm", "chroma", "faiss", "qdrant", "pinecone", "peft", "modal", "lambda-labs", "pytorch", "tensorrt-llm", "axolotl", "trl", "unsloth", "whisper", "dspy", "stable-diffusion", "llava"]},
    {"pack_id": "research_security", "category": "research", "skills": ["polymarket", "llm-wiki", "osint", "bioinformatics", "drug-discovery", "domain-intel", "gitnexus", "scrapling", "searxng", "duckduckgo", "parallel-research", "sherlock", "onepassword", "oss-forensics", "web-pentest"]},
    {"pack_id": "productivity_commerce", "category": "productivity", "skills": ["shopify", "shop-app", "canvas", "here-now", "memento-flashcards", "siyuan", "telephony", "agentmail", "himalaya", "openhue", "x-social", "finance-modeling"]},
    {"pack_id": "autonomous_devops", "category": "devops", "skills": ["agent-delegation", "honcho", "openhands", "antigravity-cli", "blackbox", "grok", "docker-management", "s6-supervision", "pinggy-tunnels", "watchers", "kanban-orchestrator", "kanban-worker"]},
]


class ClarifyTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="clarify",
            description="Ask the user for clarification with optional choices before continuing.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "question": {"type": "string", "description": "Question to ask the user."},
                    "options": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                    "allow_freeform": {"type": "boolean"},
                },
                required=["question"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        question = str(tool_input.get("question") or "").strip()
        if not question:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Clarification question is required.")
        options = [str(item).strip() for item in tool_input.get("options", []) if str(item).strip()]
        return ToolResult(
            self.name,
            ActionStatus.NEEDS_APPROVAL,
            self.risk_level,
            "Clarification requested.",
            {"question": question, "options": options, "allow_freeform": bool(tool_input.get("allow_freeform", True))},
        )


class TodoTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="todo",
            description="Create, list, update, remove, or clear durable session todo items.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["add", "list", "update", "remove", "clear"]},
                    "todo_id": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "blocked"]},
                    "notes": {"type": "string"},
                },
                required=["action"],
            ),
            capability_group="workflow",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        action = str(tool_input.get("action") or "").strip().lower()
        todos = _load_json(_todo_path(config), default=[])
        if not isinstance(todos, list):
            todos = []
        if action == "list":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(todos)} todo item(s).", {"todos": todos})
        if action == "clear":
            _save_json(_todo_path(config), [])
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Cleared todo list.", {"todos": []})
        if action == "add":
            title = str(tool_input.get("title") or "").strip()
            if not title:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Todo title is required.")
            item = {
                "todo_id": str(tool_input.get("todo_id") or f"todo-{uuid4().hex[:10]}"),
                "title": title,
                "status": str(tool_input.get("status") or "pending"),
                "notes": str(tool_input.get("notes") or ""),
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            todos.append(item)
            _save_json(_todo_path(config), todos)
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Added todo {item['todo_id']}.", {"todo": item, "todos": todos})
        todo_id = str(tool_input.get("todo_id") or "").strip()
        if not todo_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "todo_id is required.")
        index = next((idx for idx, item in enumerate(todos) if item.get("todo_id") == todo_id), None)
        if index is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown todo id: {todo_id}")
        if action == "remove":
            removed = todos.pop(index)
            _save_json(_todo_path(config), todos)
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Removed todo {todo_id}.", {"removed": removed, "todos": todos})
        if action == "update":
            item = dict(todos[index])
            for key in ("title", "status", "notes"):
                if key in tool_input and tool_input.get(key) is not None:
                    item[key] = str(tool_input.get(key))
            item["updated_at"] = time.time()
            todos[index] = item
            _save_json(_todo_path(config), todos)
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Updated todo {todo_id}.", {"todo": item, "todos": todos})
        return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported todo action: {action}.")


class SessionSearchTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="session_search",
            description="Search Humungousaur notes, run records, and text artifacts for cross-session recall.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                required=["query"],
            ),
            capability_group="memory",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        query = str(tool_input.get("query") or "").strip().casefold()
        if not query:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Session search query is required.")
        limit = max(1, min(int(tool_input.get("limit") or 10), 50))
        roots = [config.data_dir / "notes", config.data_dir / "runs", config.data_dir / "memory", config.data_dir]
        matches: list[dict[str, Any]] = []
        seen: set[Path] = set()
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path in seen or not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".json", ".jsonl"}:
                    continue
                seen.add(path)
                if path.stat().st_size > config.max_file_bytes:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if query in line.casefold():
                        matches.append({"path": _relative(path, config), "line": line_number, "text": line.strip()[:500]})
                        if len(matches) >= limit:
                            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(matches)} session match(es).", {"matches": matches})
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(matches)} session match(es).", {"matches": matches})


class CronjobTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="cronjob",
            description="Create, list, update, pause, resume, remove, or trigger scheduled natural-language jobs.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["create", "list", "update", "pause", "resume", "remove", "trigger"]},
                    "job_id": {"type": "string"},
                    "name": {"type": "string"},
                    "schedule": {"type": "string", "description": "Cron expression or natural-language schedule label."},
                    "prompt": {"type": "string", "description": "Task prompt to run when triggered."},
                    "delivery_channel": {"type": "string"},
                },
                required=["action"],
            ),
            capability_group="workflow",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        action = str(tool_input.get("action") or "").strip().lower()
        jobs = _load_json(_cron_path(config), default={})
        if not isinstance(jobs, dict):
            jobs = {}
        if action == "list":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(jobs)} cronjob(s).", {"jobs": list(jobs.values())})
        if action == "create":
            name = str(tool_input.get("name") or "").strip()
            prompt = str(tool_input.get("prompt") or "").strip()
            schedule = str(tool_input.get("schedule") or "").strip()
            if not name or not prompt or not schedule:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Cronjob name, schedule, and prompt are required.")
            job_id = str(tool_input.get("job_id") or f"cron-{uuid4().hex[:10]}")
            job = {
                "job_id": job_id,
                "name": name,
                "schedule": schedule,
                "prompt": prompt,
                "delivery_channel": str(tool_input.get("delivery_channel") or ""),
                "status": "active",
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            jobs[job_id] = job
            _save_json(_cron_path(config), jobs)
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Created cronjob {job_id}.", {"job": job})
        job_id = str(tool_input.get("job_id") or "").strip()
        if not job_id or job_id not in jobs:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown cronjob id: {job_id}")
        job = dict(jobs[job_id])
        if action == "remove":
            removed = jobs.pop(job_id)
            _save_json(_cron_path(config), jobs)
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Removed cronjob {job_id}.", {"removed": removed})
        if action in {"pause", "resume"}:
            job["status"] = "paused" if action == "pause" else "active"
        elif action == "update":
            for key in ("name", "schedule", "prompt", "delivery_channel"):
                if key in tool_input and tool_input.get(key) is not None:
                    job[key] = str(tool_input.get(key))
        elif action == "trigger":
            job["last_triggered_at"] = time.time()
            jobs[job_id] = job
            _save_json(_cron_path(config), jobs)
            return ToolResult(
                self.name,
                ActionStatus.SUCCEEDED,
                self.risk_level,
                f"Triggered cronjob {job_id}.",
                {"job": job, "prompt": job.get("prompt", ""), "delivery_channel": job.get("delivery_channel", "")},
            )
        else:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported cronjob action: {action}.")
        job["updated_at"] = time.time()
        jobs[job_id] = job
        _save_json(_cron_path(config), jobs)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Updated cronjob {job_id}.", {"job": job})


class DelegateTaskTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="delegate_task",
            description="Create a durable isolated subtask handoff packet for a subagent or worker.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "task": {"type": "string"},
                    "goal": {"type": "string"},
                    "toolsets": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                    "context": {"type": "string"},
                },
                required=["task"],
            ),
            capability_group="delegation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        task = str(tool_input.get("task") or "").strip()
        if not task:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Delegated task text is required.")
        record = {
            "delegation_id": f"delegation-{uuid4().hex[:10]}",
            "task": task,
            "goal": str(tool_input.get("goal") or ""),
            "toolsets": [str(item) for item in tool_input.get("toolsets", [])],
            "context": str(tool_input.get("context") or ""),
            "status": "queued",
            "created_at": time.time(),
        }
        path = _delegations_path(config)
        records = _load_json(path, default=[])
        if not isinstance(records, list):
            records = []
        records.append(record)
        _save_json(path, records)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Queued delegation {record['delegation_id']}.", {"delegation": record})


class ExecuteCodeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="execute_code",
            description="native-compatible wrapper for Humungousaur's bounded Python interpreter.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "code": {"type": "string"},
                    "script": {"type": "string"},
                    "reason": {"type": "string"},
                    "sandbox_profile": {"type": "string", "enum": ["read_only", "data_write", "workspace_write", "trusted_dev"]},
                    "import_mode": {"type": "string", "enum": ["stdlib", "allowlist", "all"]},
                    "allowed_imports": {"type": "array", "items": {"type": "string"}},
                },
                required=["reason"],
            ),
            capability_group="code",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        code = str(tool_input.get("code") or tool_input.get("script") or "")
        if not code.strip():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "execute_code requires code or script.")
        payload = {
            "code": code,
            "reason": str(tool_input.get("reason") or "execute_code wrapper"),
            "sandbox_profile": str(tool_input.get("sandbox_profile") or "read_only"),
            "import_mode": str(tool_input.get("import_mode") or "stdlib"),
            "allowed_imports": tool_input.get("allowed_imports", []),
        }
        result = PythonInterpreterTool().execute(payload, config)
        result.tool_name = self.name
        return result


class NativeToolsetCatalogTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="native_toolset_catalog",
            description="List native Humungousaur records for native-compatible toolsets, including custom workspace toolsets.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "query": {"type": "string"},
                    "include_tools": {"type": "boolean"},
                    "only_missing": {"type": "boolean"},
                }
            ),
            capability_group="toolsets",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        tools = _tool_registry(config)
        query = str(tool_input.get("query") or "").strip().casefold()
        include_tools = bool(tool_input.get("include_tools", False))
        only_missing = bool(tool_input.get("only_missing", False))
        items = []
        for name, definition in _load_toolsets(config).items():
            if query and query not in name.casefold() and query not in str(definition.get("description", "")).casefold():
                continue
            record = _toolset_status(name, definition, tools)
            if only_missing and not record["missing_tools"]:
                continue
            if not include_tools:
                record.pop("tools", None)
            items.append(record)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(items)} native-compatible toolset record(s).",
            {"toolsets": items, "roots": [str(path) for path in _toolset_roots(config)], "alias_map": NATIVE_ALIAS_MAP},
        )


class NativeToolsetDescribeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="native_toolset_describe",
            description="Describe one native-compatible toolset and report exact available, alias-backed, and missing tools.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"toolset": {"type": "string"}}, required=["toolset"]),
            capability_group="toolsets",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        name = str(tool_input.get("toolset") or "").strip()
        definition = _load_toolsets(config).get(name)
        if definition is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown native toolset: {name}")
        record = _toolset_status(name, definition, _tool_registry(config))
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Described native toolset {name}: {record['status']}.",
            {"toolset": record, "alias_map": NATIVE_ALIAS_MAP},
        )


class McpServerCatalogTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="mcp_server_catalog",
            description="List built-in and workspace MCP server manifests with credential readiness and transport metadata.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"server_id": {"type": "string"}, "include_tools": {"type": "boolean"}}),
            capability_group="mcp",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        load_workspace_environment(config.normalized().workspace)
        server_id = str(tool_input.get("server_id") or "").strip()
        include_tools = bool(tool_input.get("include_tools", False))
        manifests = _load_mcp_manifests(config)
        if server_id:
            manifests = [manifest for manifest in manifests if manifest.get("server_id") == server_id]
        items = [_mcp_summary(manifest, include_tools=include_tools) for manifest in manifests]
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Found {len(items)} MCP server manifest(s).",
            {"servers": items, "roots": [str(path) for path in _mcp_roots(config)]},
        )


class McpServerManifestTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="mcp_server_manifest",
            description="Read one MCP server manifest by server_id.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"server_id": {"type": "string"}}, required=["server_id"]),
            capability_group="mcp",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        server_id = str(tool_input.get("server_id") or "").strip()
        manifest = _find_mcp_manifest(config, server_id)
        if manifest is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown MCP server: {server_id}")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Read MCP server manifest {server_id}.",
            {"manifest": _redact_manifest(manifest), "readiness": _credential_readiness(manifest)},
        )


class McpServerLaunchTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="mcp_server_launch",
            description="Prepare or record launch of a manifest-backed MCP server. Actual process starts require approval and a command in the manifest.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "server_id": {"type": "string"},
                    "approved": {"type": "boolean"},
                    "dry_run": {"type": "boolean"},
                },
                required=["server_id"],
            ),
            capability_group="mcp",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        server_id = str(tool_input.get("server_id") or "").strip()
        manifest = _find_mcp_manifest(config, server_id)
        if manifest is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown MCP server: {server_id}")
        command = _manifest_argv(manifest)
        if not command:
            return ToolResult(
                self.name,
                ActionStatus.BLOCKED,
                self.risk_level,
                f"MCP server {server_id} has no local launch command.",
                {"manifest": _redact_manifest(manifest), "readiness": _credential_readiness(manifest)},
            )
        if not bool(tool_input.get("approved", False)):
            return ToolResult(
                self.name,
                ActionStatus.NEEDS_APPROVAL,
                self.risk_level,
                f"Launching MCP server {server_id} requires approval.",
                {"server_id": server_id, "argv": command, "readiness": _credential_readiness(manifest)},
            )
        record = {
            "launch_id": f"mcp-launch-{uuid4().hex[:10]}",
            "server_id": server_id,
            "argv": command,
            "created_at": time.time(),
            "dry_run": bool(tool_input.get("dry_run", False) or config.dry_run),
            "status": "prepared" if bool(tool_input.get("dry_run", False) or config.dry_run) else "ready_for_supervisor",
        }
        launches = _load_json(_mcp_launch_path(config), default=[])
        if not isinstance(launches, list):
            launches = []
        launches.append(record)
        _save_json(_mcp_launch_path(config), launches)
        status = ActionStatus.SKIPPED if record["dry_run"] else ActionStatus.SUCCEEDED
        return ToolResult(self.name, status, self.risk_level, f"Recorded MCP launch packet for {server_id}.", {"launch": record})


class McpToolDiscoverTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="mcp_tool_discover",
            description="Discover declared tools for a manifest-backed MCP server.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"server_id": {"type": "string"}}, required=["server_id"]),
            capability_group="mcp",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        server_id = str(tool_input.get("server_id") or "").strip()
        manifest = _find_mcp_manifest(config, server_id)
        if manifest is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown MCP server: {server_id}")
        tools = manifest.get("tools", [])
        if not isinstance(tools, list):
            tools = []
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Discovered {len(tools)} declared MCP tool(s) for {server_id}.",
            {"server_id": server_id, "tools": tools, "dynamic_discovery": "Use mcp_tool_call only after a trusted MCP runtime is configured."},
        )


class McpToolCallTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="mcp_tool_call",
            description="Approval-gated MCP tool invocation contract for configured MCP servers.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "server_id": {"type": "string"},
                    "tool": {"type": "string"},
                    "arguments": {"type": "object"},
                    "approved": {"type": "boolean"},
                },
                required=["server_id", "tool", "arguments"],
            ),
            capability_group="mcp",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        server_id = str(tool_input.get("server_id") or "").strip()
        tool = str(tool_input.get("tool") or "").strip()
        manifest = _find_mcp_manifest(config, server_id)
        if manifest is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown MCP server: {server_id}")
        declared_tools = [str(item) for item in manifest.get("tools", [])] if isinstance(manifest.get("tools"), list) else []
        if declared_tools and tool not in declared_tools:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Tool {tool} is not declared by MCP server {server_id}.")
        if not bool(tool_input.get("approved", False)):
            return ToolResult(
                self.name,
                ActionStatus.NEEDS_APPROVAL,
                self.risk_level,
                f"Calling MCP tool {server_id}.{tool} requires approval.",
                {"server_id": server_id, "tool": tool, "arguments": tool_input.get("arguments", {})},
            )
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                f"Dry run: would call MCP tool {server_id}.{tool}.",
                {"server_id": server_id, "tool": tool, "arguments": tool_input.get("arguments", {})},
            )
        return ToolResult(
            self.name,
            ActionStatus.BLOCKED,
            self.risk_level,
            "MCP runtime invocation is blocked until a trusted server transport is active.",
            {"server_id": server_id, "tool": tool, "manifest": _redact_manifest(manifest)},
        )


class McpOauthStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="mcp_oauth_status",
            description="Report OAuth/API-key readiness for MCP server manifests without exposing secret values.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"server_id": {"type": "string"}}),
            capability_group="mcp",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        server_id = str(tool_input.get("server_id") or "").strip()
        manifests = _load_mcp_manifests(config)
        if server_id:
            manifests = [manifest for manifest in manifests if manifest.get("server_id") == server_id]
        items = [{"server_id": manifest.get("server_id", ""), **_credential_readiness(manifest)} for manifest in manifests]
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Read OAuth readiness for {len(items)} MCP server(s).", {"servers": items})


class PluginStateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="plugin_state",
            description="List, enable, disable, or inspect native plugin state records without installing arbitrary code.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["list", "enable", "disable", "inspect"]},
                    "plugin_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["action"],
            ),
            capability_group="plugins",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        action = str(tool_input.get("action") or "").strip().lower()
        state = _load_json(_plugin_state_path(config), default={})
        if not isinstance(state, dict):
            state = {}
        if action == "list":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(state)} plugin state record(s).", {"plugins": state})
        plugin_id = str(tool_input.get("plugin_id") or "").strip()
        if not plugin_id:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "plugin_id is required.")
        if action == "inspect":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Read plugin state for {plugin_id}.", {"plugin": state.get(plugin_id, {"plugin_id": plugin_id, "enabled": False})})
        record = dict(state.get(plugin_id, {"plugin_id": plugin_id}))
        record["enabled"] = action == "enable"
        record["updated_at"] = time.time()
        record["reason"] = str(tool_input.get("reason") or "")
        state[plugin_id] = record
        _save_json(_plugin_state_path(config), state)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"{'Enabled' if record['enabled'] else 'Disabled'} plugin {plugin_id}.", {"plugin": record})


class ProviderRegistryTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="provider_registry",
            description="List native-relevant model, media, and observability provider contracts and credential readiness.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"kind": {"type": "string"}, "provider_id": {"type": "string"}}),
            capability_group="providers",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        load_workspace_environment(config.normalized().workspace)
        kind = str(tool_input.get("kind") or "").strip()
        provider_id = str(tool_input.get("provider_id") or "").strip()
        items = []
        for provider in NATIVE_PROVIDER_REGISTRY:
            if kind and provider.get("kind") != kind:
                continue
            if provider_id and provider.get("provider_id") != provider_id:
                continue
            required_env = [str(item) for item in provider.get("required_env", [])]
            items.append({**provider, "configured": all(os.environ.get(name) for name in required_env), "missing_env": [name for name in required_env if not os.environ.get(name)]})
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(items)} provider record(s).", {"providers": items})


class RuntimeHookCatalogTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="runtime_hook_catalog",
            description="List native observer and middleware hook contracts for LLM calls, tool calls, sessions, and gateway events.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"event": {"type": "string"}}),
            capability_group="runtime",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        event = str(tool_input.get("event") or "").strip()
        hooks = [hook for hook in NATIVE_RUNTIME_HOOKS if not event or hook.get("event") == event]
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(hooks)} runtime hook(s).", {"hooks": hooks})


class MemoryCompatTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="memory",
            description="native-compatible memory facade over Humungousaur memory search, write, summary, and profile tools.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["search", "write", "summary", "profile"]},
                    "query": {"type": "string"},
                    "kind": {"type": "string"},
                    "text": {"type": "string"},
                    "period": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                required=["action"],
            ),
            capability_group="memory",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        action = str(tool_input.get("action") or "").strip().lower()
        from humungousaur.tools.memory.implementation import MemoryProfileTool, MemorySearchTool, MemorySummaryTool, MemoryWriteTool

        if action == "search":
            result = MemorySearchTool().execute({"query": tool_input.get("query", ""), "limit": tool_input.get("limit", 8)}, config)
        elif action == "write":
            result = MemoryWriteTool().execute({"kind": tool_input.get("kind", "note"), "text": tool_input.get("text", "")}, config)
        elif action == "summary":
            result = MemorySummaryTool().execute({"period": tool_input.get("period", "today"), "query": tool_input.get("query", ""), "limit": tool_input.get("limit", 20)}, config)
        elif action == "profile":
            result = MemoryProfileTool().execute({"limit": tool_input.get("limit", 20)}, config)
        else:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported memory action: {action}.")
        result.tool_name = self.name
        return result


class BrowserCompatFeatureTool(Tool):
    def __init__(self, name: str, description: str, *, requires_approval: bool = False) -> None:
        super().__init__(
            name=name,
            description=description,
            risk_level=RiskLevel.HIGH if requires_approval else RiskLevel.LOW,
            requires_approval=requires_approval,
            input_schema=object_input_schema(
                {
                    "live_session_id": {"type": "string"},
                    "query": {"type": "string"},
                    "code": {"type": "string"},
                    "action": {"type": "string"},
                    "prompt": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["live_session_id"],
            ),
            capability_group="browser",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        tools = _tool_registry(config)
        live_session_id = str(tool_input.get("live_session_id") or "").strip()
        if self.name == "browser_get_images":
            result = tools["browser_live_extract"].execute({"live_session_id": live_session_id, "query": tool_input.get("query") or "images on this page", "include_images": True}, config)
        elif self.name == "browser_console":
            result = tools["browser_live_evaluate_js"].execute({"live_session_id": live_session_id, "code": "console.history || []", "reason": tool_input.get("reason") or "Inspect browser console history.", "max_chars": 8000}, config)
        elif self.name == "browser_vision":
            result = tools["browser_live_screenshot"].execute({"live_session_id": live_session_id, "reason": tool_input.get("reason") or "Capture browser view for visual analysis."}, config)
        elif self.name == "browser_dialog":
            return ToolResult(
                self.name,
                ActionStatus.BLOCKED if not config.dry_run else ActionStatus.SKIPPED,
                self.risk_level,
                "Browser dialog control requires an active live browser runtime dialog event.",
                {"live_session_id": live_session_id, "action": tool_input.get("action", ""), "dry_run": config.dry_run},
            )
        else:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported browser compatibility tool: {self.name}.")
        result.tool_name = self.name
        return result


class ComputerUseCompatTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="computer_use",
            description="native-compatible desktop control facade over Humungousaur OS observation, screenshot, keyboard, mouse, and app tools.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["observe", "screenshot", "active_window", "click", "type", "keys"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "text": {"type": "string"},
                    "keys": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["action"],
            ),
            capability_group="os",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        tools = _tool_registry(config)
        action = str(tool_input.get("action") or "").strip().lower()
        if action == "active_window":
            result = tools["os_active_window"].execute({}, config)
        elif action == "observe":
            result = tools["os_observe_ui"].execute({}, config)
        elif action == "screenshot":
            result = tools["screenshot_capture"].execute({"reason": tool_input.get("reason") or "computer_use screenshot"}, config)
        elif action == "click":
            result = tools["os_click_coordinates"].execute({"x": tool_input.get("x"), "y": tool_input.get("y"), "reason": tool_input.get("reason") or "computer_use click"}, config)
        elif action == "type":
            result = tools["os_type_text"].execute({"text": tool_input.get("text", ""), "reason": tool_input.get("reason") or "computer_use type"}, config)
        elif action == "keys":
            result = tools["os_send_keys"].execute({"keys": tool_input.get("keys", []), "reason": tool_input.get("reason") or "computer_use keys"}, config)
        else:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported computer_use action: {action}.")
        result.tool_name = self.name
        return result


class KanbanTool(Tool):
    def __init__(self, name: str) -> None:
        mutating = name not in {"kanban_show", "kanban_list"}
        super().__init__(
            name=name,
            description=f"native-compatible local kanban operation: {name}.",
            risk_level=RiskLevel.MEDIUM if mutating else RiskLevel.LOW,
            requires_approval=mutating,
            input_schema=object_input_schema(
                {
                    "board_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                    "comment": {"type": "string"},
                    "blocked_reason": {"type": "string"},
                    "target_task_id": {"type": "string"},
                    "heartbeat": {"type": "string"},
                    "assignee": {"type": "string"},
                }
            ),
            capability_group="kanban",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        state = _load_kanban(config)
        board_id = str(tool_input.get("board_id") or "default").strip() or "default"
        board = state.setdefault(board_id, {"board_id": board_id, "tasks": {}, "created_at": time.time()})
        tasks = board.setdefault("tasks", {})
        if self.name == "kanban_list":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(tasks)} kanban task(s).", {"board": _board_view(board)})
        task_id = str(tool_input.get("task_id") or "").strip()
        if self.name == "kanban_create":
            title = str(tool_input.get("title") or "").strip()
            if not title:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Kanban task title is required.")
            task_id = task_id or f"task-{uuid4().hex[:10]}"
            task = {
                "task_id": task_id,
                "title": title,
                "description": str(tool_input.get("description") or ""),
                "status": str(tool_input.get("status") or "pending"),
                "assignee": str(tool_input.get("assignee") or ""),
                "comments": [],
                "links": [],
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            tasks[task_id] = task
            _save_kanban(config, state)
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Created kanban task {task_id}.", {"task": task, "board": _board_view(board)})
        if not task_id or task_id not in tasks:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown kanban task id: {task_id}")
        task = dict(tasks[task_id])
        if self.name == "kanban_show":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Read kanban task {task_id}.", {"task": task, "board_id": board_id})
        if self.name == "kanban_complete":
            task["status"] = "completed"
        elif self.name == "kanban_block":
            task["status"] = "blocked"
            task["blocked_reason"] = str(tool_input.get("blocked_reason") or tool_input.get("comment") or "")
        elif self.name == "kanban_unblock":
            task["status"] = "pending"
            task.pop("blocked_reason", None)
        elif self.name == "kanban_heartbeat":
            task["last_heartbeat"] = {"text": str(tool_input.get("heartbeat") or ""), "at": time.time()}
        elif self.name == "kanban_comment":
            comment = {"comment_id": f"comment-{uuid4().hex[:8]}", "text": str(tool_input.get("comment") or ""), "created_at": time.time()}
            task.setdefault("comments", []).append(comment)
        elif self.name == "kanban_link":
            target = str(tool_input.get("target_task_id") or "").strip()
            if not target:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "target_task_id is required.")
            task.setdefault("links", []).append({"target_task_id": target, "created_at": time.time()})
        else:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported kanban operation: {self.name}.")
        task["updated_at"] = time.time()
        tasks[task_id] = task
        _save_kanban(config, state)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Updated kanban task {task_id}.", {"task": task, "board": _board_view(board)})


class MediaCompatTool(Tool):
    def __init__(self, name: str) -> None:
        risk = RiskLevel.MEDIUM if name in {"vision_analyze", "video_analyze"} else RiskLevel.HIGH
        super().__init__(
            name=name,
            description=f"native-compatible media capability: {name}.",
            risk_level=risk,
            requires_approval=name in {"image_generate", "video_generate"},
            input_schema=object_input_schema(
                {
                    "prompt": {"type": "string"},
                    "image_url": {"type": "string"},
                    "video_url": {"type": "string"},
                    "path": {"type": "string"},
                    "provider": {"type": "string"},
                    "reason": {"type": "string"},
                }
            ),
            capability_group="media",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        if self.name == "image_generate":
            return _write_generation_spec(self.name, config, "image", tool_input)
        if self.name == "video_generate":
            return _write_generation_spec(self.name, config, "video", tool_input)
        subject = str(tool_input.get("path") or tool_input.get("image_url") or tool_input.get("video_url") or "").strip()
        if not subject:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"{self.name} requires path, image_url, or video_url.")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Prepared {self.name} analysis packet.",
            {"subject": subject, "provider": str(tool_input.get("provider") or "configured_default"), "analysis_status": "requires_model_provider_for_semantic_analysis"},
        )


class MixtureOfAgentsTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="mixture_of_agents",
            description="Create a multi-model consensus request packet with provider readiness checks.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "prompt": {"type": "string"},
                    "models": {"type": "array", "items": {"type": "string"}},
                    "strategy": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["prompt"],
            ),
            capability_group="analysis",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        models = [str(item) for item in tool_input.get("models", [])] if isinstance(tool_input.get("models"), list) else []
        record = {
            "moa_id": f"moa-{uuid4().hex[:10]}",
            "prompt": str(tool_input.get("prompt") or ""),
            "models": models,
            "strategy": str(tool_input.get("strategy") or "consensus"),
            "status": "queued" if not config.dry_run else "dry_run",
            "created_at": time.time(),
        }
        path = config.data_dir / "mixture_of_agents.json"
        records = _load_json(path, default=[])
        if not isinstance(records, list):
            records = []
        records.append(record)
        _save_json(path, records)
        return ToolResult(self.name, ActionStatus.SKIPPED if config.dry_run else ActionStatus.SUCCEEDED, self.risk_level, f"Recorded mixture-of-agents request {record['moa_id']}.", {"request": record})


class ServiceContractTool(Tool):
    def __init__(
        self,
        name: str,
        *,
        group: str,
        required_env: list[str],
        mutating: bool = False,
        actions: list[str] | None = None,
    ) -> None:
        properties = {
            "action": {"type": "string"},
            "query": {"type": "string"},
            "id": {"type": "string"},
            "entity_id": {"type": "string"},
            "service": {"type": "string"},
            "domain": {"type": "string"},
            "payload": {"type": "object"},
            "text": {"type": "string"},
            "reason": {"type": "string"},
        }
        if actions:
            properties["action"]["enum"] = actions
        super().__init__(
            name=name,
            description=f"Credential-gated native-compatible {group} adapter for {name}.",
            risk_level=RiskLevel.HIGH if mutating else RiskLevel.MEDIUM,
            requires_approval=mutating,
            input_schema=object_input_schema(properties),
            capability_group=group,
        )
        self.required_env = required_env

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        load_workspace_environment(config.normalized().workspace)
        missing = [name for name in self.required_env if not os.environ.get(name)]
        packet = {
            "tool": self.name,
            "input": _safe_contract_input(tool_input),
            "required_env": self.required_env,
            "missing_env": missing,
            "configured": not missing,
            "status_recorded_at": time.time(),
        }
        if missing:
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, f"{self.name} is not configured.", packet)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would execute {self.name}.", packet)
        return ToolResult(
            self.name,
            ActionStatus.BLOCKED,
            self.risk_level,
            f"{self.name} has credentials but no trusted live connector session is active.",
            {**packet, "next_step": "Enable the matching channel/provider runtime or MCP connector before live execution."},
        )


class GatewayControlTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="gateway_control",
            description="Manage native gateway authorization, pairing, session keys, interrupts, slash commands, and mirroring state.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["status", "pair", "authorize", "revoke", "interrupt", "slash_command", "mirror"]},
                    "channel_id": {"type": "string"},
                    "session_id": {"type": "string"},
                    "principal": {"type": "string"},
                    "command": {"type": "string"},
                    "enabled": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                required=["action"],
            ),
            capability_group="gateway",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        action = str(tool_input.get("action") or "").strip().lower()
        state = _load_json(_gateway_state_path(config), default={"sessions": {}, "pairings": {}, "interrupts": [], "slash_commands": [], "mirrors": {}})
        if not isinstance(state, dict):
            state = {"sessions": {}, "pairings": {}, "interrupts": [], "slash_commands": [], "mirrors": {}}
        if action == "status":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Read gateway control state.", {"gateway": state})
        session_id = str(tool_input.get("session_id") or f"gateway-session-{uuid4().hex[:10]}")
        channel_id = str(tool_input.get("channel_id") or "").strip()
        if action in {"pair", "authorize"}:
            state.setdefault("sessions", {})[session_id] = {
                "session_id": session_id,
                "channel_id": channel_id,
                "principal": str(tool_input.get("principal") or ""),
                "authorized": action == "authorize",
                "created_at": time.time(),
            }
        elif action == "revoke":
            state.setdefault("sessions", {}).setdefault(session_id, {"session_id": session_id})["authorized"] = False
        elif action == "interrupt":
            state.setdefault("interrupts", []).append({"session_id": session_id, "reason": str(tool_input.get("reason") or ""), "created_at": time.time()})
        elif action == "slash_command":
            state.setdefault("slash_commands", []).append({"session_id": session_id, "command": str(tool_input.get("command") or ""), "created_at": time.time()})
        elif action == "mirror":
            state.setdefault("mirrors", {})[channel_id or session_id] = {"enabled": bool(tool_input.get("enabled", True)), "updated_at": time.time()}
        else:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unsupported gateway action: {action}.")
        _save_json(_gateway_state_path(config), state)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Updated gateway state with action {action}.", {"gateway": state})


class ChannelDeliveryTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="channel_delivery",
            description="Record and inspect channel-aware delivery packets for cron/background jobs.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["list", "record", "mark_sent", "mark_failed"]},
                    "delivery_id": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "job_id": {"type": "string"},
                    "message": {"type": "string"},
                    "error": {"type": "string"},
                },
                required=["action"],
            ),
            capability_group="gateway",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        deliveries = _load_json(_channel_delivery_path(config), default=[])
        if not isinstance(deliveries, list):
            deliveries = []
        action = str(tool_input.get("action") or "").strip().lower()
        if action == "list":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(deliveries)} delivery packet(s).", {"deliveries": deliveries})
        delivery_id = str(tool_input.get("delivery_id") or f"delivery-{uuid4().hex[:10]}")
        if action == "record":
            record = {
                "delivery_id": delivery_id,
                "channel_id": str(tool_input.get("channel_id") or ""),
                "job_id": str(tool_input.get("job_id") or ""),
                "message": str(tool_input.get("message") or ""),
                "status": "queued",
                "created_at": time.time(),
            }
            deliveries.append(record)
        else:
            record = next((item for item in deliveries if item.get("delivery_id") == delivery_id), None)
            if record is None:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown delivery id: {delivery_id}")
            record["status"] = "sent" if action == "mark_sent" else "failed"
            record["error"] = str(tool_input.get("error") or "")
            record["updated_at"] = time.time()
        _save_json(_channel_delivery_path(config), deliveries)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Updated delivery {delivery_id}.", {"delivery": record, "deliveries": deliveries})


class SecurityPolicyTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="native_security_policy",
            description="Shared native URL/SSRF and command/content threat scan policy for web, browser, vision, gateway media, terminal, process, patch, and code tools.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "url": {"type": "string"},
                    "command": {"type": "string"},
                    "content": {"type": "string"},
                    "context": {"type": "string"},
                }
            ),
            capability_group="security",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        findings = []
        url = str(tool_input.get("url") or "")
        command = str(tool_input.get("command") or "")
        content = str(tool_input.get("content") or "")
        if url.startswith(("file://", "ftp://")) or "169.254.169.254" in url or "localhost" in url or "127.0.0.1" in url:
            findings.append({"severity": "block", "kind": "ssrf_url", "text": "URL targets local or metadata resources."})
        dangerous_terms = ["rm -rf", "curl | sh", "sudo ", "chmod 777", "mkfs", ":(){:|:&};:"]
        for term in dangerous_terms:
            if term in command:
                findings.append({"severity": "block", "kind": "dangerous_command", "text": term})
        if "BEGIN PRIVATE KEY" in content or "sk-" in content:
            findings.append({"severity": "warning", "kind": "secret_like_content", "text": "Content may contain credentials."})
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Security policy scan produced {len(findings)} finding(s).",
            {"findings": findings, "allowed": not any(item["severity"] == "block" for item in findings)},
        )


class CredentialFilePolicyTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="credential_file_policy",
            description="Declare and inspect credential-file passthrough requirements for native and imported skills without storing secret contents.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["list", "declare"]},
                    "skill_id": {"type": "string"},
                    "paths": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["action"],
            ),
            capability_group="security",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        records = _load_json(_credential_policy_path(config), default=[])
        if not isinstance(records, list):
            records = []
        if str(tool_input.get("action") or "") == "list":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(records)} credential-file declaration(s).", {"declarations": records})
        record = {
            "skill_id": str(tool_input.get("skill_id") or ""),
            "paths": [str(item) for item in tool_input.get("paths", [])] if isinstance(tool_input.get("paths"), list) else [],
            "reason": str(tool_input.get("reason") or ""),
            "created_at": time.time(),
        }
        records.append(record)
        _save_json(_credential_policy_path(config), records)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, "Declared credential-file passthrough policy.", {"declaration": record})


class OptionalDependencyInstallerTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="optional_dependency_installer",
            description="Record or dry-run optional dependency installation requests with explicit opt-out and approval controls.",
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "package": {"type": "string"},
                    "manager": {"type": "string"},
                    "version": {"type": "string"},
                    "opt_out": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                required=["package", "reason"],
            ),
            capability_group="system",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        record = {
            "request_id": f"dep-{uuid4().hex[:10]}",
            "package": str(tool_input.get("package") or ""),
            "manager": str(tool_input.get("manager") or "pip"),
            "version": str(tool_input.get("version") or ""),
            "opt_out": bool(tool_input.get("opt_out", False)),
            "reason": str(tool_input.get("reason") or ""),
            "created_at": time.time(),
            "status": "opted_out" if bool(tool_input.get("opt_out", False)) else ("dry_run" if config.dry_run else "recorded_for_operator"),
        }
        records = _load_json(_dependency_requests_path(config), default=[])
        if not isinstance(records, list):
            records = []
        records.append(record)
        _save_json(_dependency_requests_path(config), records)
        status = ActionStatus.SKIPPED if config.dry_run or record["opt_out"] else ActionStatus.SUCCEEDED
        return ToolResult(self.name, status, self.risk_level, f"Recorded optional dependency request {record['request_id']}.", {"request": record})


class ToolOutputStoreTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="tool_output_store",
            description="Store, list, and retrieve bounded large tool outputs for resumable follow-up without flooding prompts.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "action": {"type": "string", "enum": ["store", "list", "read"]},
                    "output_id": {"type": "string"},
                    "tool_name": {"type": "string"},
                    "content": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200000},
                },
                required=["action"],
            ),
            capability_group="runtime",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        root = config.data_dir / "tool_outputs"
        index = _load_json(root / "index.json", default=[])
        if not isinstance(index, list):
            index = []
        action = str(tool_input.get("action") or "").strip()
        if action == "list":
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(index)} stored output(s).", {"outputs": index})
        if action == "store":
            content = str(tool_input.get("content") or "")
            output_id = str(tool_input.get("output_id") or f"output-{uuid4().hex[:10]}")
            path = root / f"{output_id}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            record = {"output_id": output_id, "tool_name": str(tool_input.get("tool_name") or ""), "path": str(path), "bytes": len(content.encode("utf-8")), "created_at": time.time()}
            index.append(record)
            _save_json(root / "index.json", index)
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Stored tool output {output_id}.", {"output": record})
        output_id = str(tool_input.get("output_id") or "")
        record = next((item for item in index if item.get("output_id") == output_id), None)
        if record is None:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown output id: {output_id}")
        text = Path(record["path"]).read_text(encoding="utf-8", errors="replace")
        limit = max(1, min(int(tool_input.get("limit") or 8000), 200000))
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Read stored output {output_id}.", {"output": record, "content": text[:limit], "truncated": len(text) > limit})


class NativeSkillPackCatalogTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="native_skill_pack_catalog",
            description="List native capability skill packs by category before building Humungousaur-owned skill files.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"category": {"type": "string"}}),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        category = str(tool_input.get("category") or "").strip()
        packs = [pack for pack in NATIVE_SKILL_PACKS if not category or pack["category"] == category]
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(packs)} native skill pack(s).", {"packs": packs})


class NativeSkillPackBuildTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="native_skill_pack_build",
            description="Build native capability skill packs as native Humungousaur SKILL.md files with provenance and security review metadata.",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema=object_input_schema(
                {
                    "pack_ids": {"type": "array", "items": {"type": "string"}},
                    "overwrite": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                required=["pack_ids", "reason"],
            ),
            capability_group="skills",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        requested = {str(item) for item in tool_input.get("pack_ids", [])} if isinstance(tool_input.get("pack_ids"), list) else set()
        packs = [pack for pack in NATIVE_SKILL_PACKS if pack["pack_id"] in requested]
        if not packs:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "No known pack_ids were requested.")
        builds = _load_json(_skill_pack_build_path(config), default=[])
        if not isinstance(builds, list):
            builds = []
        overwrite = bool(tool_input.get("overwrite", False))
        records = []
        for pack in packs:
            skill_records = []
            for skill_name in pack["skills"]:
                path = _native_skill_path(config, pack["category"], skill_name)
                existed = path.exists()
                if existed and not overwrite:
                    status = "already_native"
                else:
                    if not config.dry_run:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(_native_skill_markdown(pack, skill_name), encoding="utf-8")
                    status = "dry_run" if config.dry_run else "built_native"
                skill_records.append({"skill": skill_name, "path": str(path), "status": status})
            record = {
                "build_id": f"skill-build-{uuid4().hex[:10]}",
                "pack_id": pack["pack_id"],
                "category": pack["category"],
                "skills": skill_records,
                "reason": str(tool_input.get("reason") or ""),
                "provenance_review": "native_humungousaur_authored",
                "security_review": "passed_contract_review",
                "upstream_imported": False,
                "created_at": time.time(),
            }
            builds.append(record)
            records.append(record)
        _save_json(_skill_pack_build_path(config), builds)
        status = ActionStatus.SKIPPED if config.dry_run else ActionStatus.SUCCEEDED
        return ToolResult(self.name, status, self.risk_level, f"Built {len(records)} native capability skill pack(s).", {"builds": records})


def default_native_parity_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        ClarifyTool(),
        TodoTool(),
        SessionSearchTool(),
        CronjobTool(),
        DelegateTaskTool(),
        ExecuteCodeTool(),
        NativeToolsetCatalogTool(),
        NativeToolsetDescribeTool(),
        McpServerCatalogTool(),
        McpServerManifestTool(),
        McpServerLaunchTool(),
        McpToolDiscoverTool(),
        McpToolCallTool(),
        McpOauthStatusTool(),
        PluginStateTool(),
        ProviderRegistryTool(),
        RuntimeHookCatalogTool(),
        MemoryCompatTool(),
        BrowserCompatFeatureTool("browser_get_images", "Extract image URLs and metadata from a live browser page."),
        BrowserCompatFeatureTool("browser_console", "Inspect live browser console history or console-like page diagnostics."),
        BrowserCompatFeatureTool("browser_vision", "Capture a live browser screenshot for visual analysis."),
        BrowserCompatFeatureTool("browser_dialog", "Handle live browser dialogs when a dialog event is active.", requires_approval=True),
        ComputerUseCompatTool(),
        MixtureOfAgentsTool(),
        MediaCompatTool("vision_analyze"),
        MediaCompatTool("video_analyze"),
        MediaCompatTool("image_generate"),
        MediaCompatTool("video_generate"),
        GatewayControlTool(),
        ChannelDeliveryTool(),
        SecurityPolicyTool(),
        CredentialFilePolicyTool(),
        OptionalDependencyInstallerTool(),
        ToolOutputStoreTool(),
        NativeSkillPackCatalogTool(),
        NativeSkillPackBuildTool(),
    ]
    tools.extend(KanbanTool(name) for name in [
        "kanban_show",
        "kanban_list",
        "kanban_complete",
        "kanban_block",
        "kanban_heartbeat",
        "kanban_comment",
        "kanban_create",
        "kanban_link",
        "kanban_unblock",
    ])
    tools.extend(_service_contract_tools())
    return {tool.name: tool for tool in tools}


def _todo_path(config: AgentConfig) -> Path:
    return config.data_dir / "todos.json"


def _cron_path(config: AgentConfig) -> Path:
    return config.data_dir / "cronjobs.json"


def _delegations_path(config: AgentConfig) -> Path:
    return config.data_dir / "delegations.json"


def _load_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _relative(path: Path, config: AgentConfig) -> str:
    try:
        return str(path.relative_to(config.workspace))
    except ValueError:
        try:
            return str(path.relative_to(config.data_dir))
        except ValueError:
            return str(path)


def _tool_registry(config: AgentConfig) -> dict[str, Tool]:
    from humungousaur.tools import default_tools

    return default_tools(config)


def _toolset_roots(config: AgentConfig) -> list[Path]:
    normalized = config.normalized()
    return [normalized.workspace / ".umang" / "toolsets", normalized.data_dir / "toolsets"]


def _load_toolsets(config: AgentConfig) -> dict[str, dict[str, Any]]:
    records = {name: {"description": str(meta.get("description", "")), "tools": list(meta.get("tools", [])), "source": "builtin"} for name, meta in NATIVE_TOOLSET_DEFINITIONS.items()}
    for root in _toolset_roots(config):
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.glob("*.json"))[:100]:
            payload = _load_json(path, default={})
            if not isinstance(payload, dict):
                continue
            name = str(payload.get("name") or path.stem).strip()
            tools = payload.get("tools", [])
            if not name or not isinstance(tools, list):
                continue
            records[name] = {
                "description": str(payload.get("description") or ""),
                "tools": [str(item) for item in tools if str(item)],
                "source": str(path),
            }
    return dict(sorted(records.items()))


def _toolset_status(name: str, definition: dict[str, Any], tools: dict[str, Tool]) -> dict[str, Any]:
    expected = [str(item) for item in definition.get("tools", []) if str(item)]
    available: list[str] = []
    alias_backed: list[dict[str, str]] = []
    missing: list[str] = []
    for tool_name in expected:
        if tool_name in tools:
            available.append(tool_name)
            target = NATIVE_ALIAS_MAP.get(tool_name)
            if target:
                alias_backed.append({"tool": tool_name, "target": target})
        else:
            missing.append(tool_name)
    if expected and not missing:
        status = "implemented"
    elif available:
        status = "partial"
    else:
        status = "empty" if not expected else "missing"
    return {
        "name": name,
        "description": str(definition.get("description") or ""),
        "source": str(definition.get("source") or "builtin"),
        "status": status,
        "tool_count": len(expected),
        "available_count": len(available),
        "missing_count": len(missing),
        "tools": expected,
        "available_tools": available,
        "alias_backed_tools": alias_backed,
        "missing_tools": missing,
    }


def _mcp_roots(config: AgentConfig) -> list[Path]:
    normalized = config.normalized()
    return [normalized.workspace / ".umang" / "mcp", normalized.data_dir / "mcp"]


def _load_mcp_manifests(config: AgentConfig) -> list[dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {
        str(item.get("server_id")): {**item, "source": "builtin"} for item in BUILTIN_MCP_MANIFESTS if item.get("server_id")
    }
    for root in _mcp_roots(config):
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.glob("*.json"))[:100]:
            payload = _load_json(path, default={})
            candidates = payload.get("servers") if isinstance(payload, dict) else None
            if isinstance(candidates, list):
                manifest_items = [item for item in candidates if isinstance(item, dict)]
            elif isinstance(payload, dict):
                manifest_items = [payload]
            else:
                manifest_items = []
            for manifest in manifest_items:
                server_id = str(manifest.get("server_id") or manifest.get("name") or "").strip()
                if not server_id:
                    continue
                manifests[server_id] = {**manifest, "server_id": server_id, "source": str(path)}
    return [manifests[name] for name in sorted(manifests)]


def _find_mcp_manifest(config: AgentConfig, server_id: str) -> dict[str, Any] | None:
    for manifest in _load_mcp_manifests(config):
        if manifest.get("server_id") == server_id:
            return manifest
    return None


def _mcp_summary(manifest: dict[str, Any], *, include_tools: bool) -> dict[str, Any]:
    readiness = _credential_readiness(manifest)
    record = {
        "server_id": str(manifest.get("server_id", "")),
        "display_name": str(manifest.get("display_name") or manifest.get("server_id") or ""),
        "status": str(manifest.get("status") or "manifest_ready"),
        "transport": str(manifest.get("transport") or ""),
        "source": str(manifest.get("source") or ""),
        "configured": readiness["configured"],
        "missing_env": readiness["missing_env"],
        "tool_count": len(manifest.get("tools", [])) if isinstance(manifest.get("tools"), list) else 0,
    }
    if include_tools:
        record["tools"] = manifest.get("tools", []) if isinstance(manifest.get("tools"), list) else []
    return record


def _credential_readiness(manifest: dict[str, Any]) -> dict[str, Any]:
    required_env = [str(item) for item in manifest.get("required_env", [])] if isinstance(manifest.get("required_env"), list) else []
    optional_env = [str(item) for item in manifest.get("optional_env", [])] if isinstance(manifest.get("optional_env"), list) else []
    missing_env = [name for name in required_env if not os.environ.get(name)]
    configured_optional_env = [name for name in optional_env if os.environ.get(name)]
    return {
        "required_env": required_env,
        "optional_env": optional_env,
        "missing_env": missing_env,
        "configured_optional_env": configured_optional_env,
        "configured": not missing_env,
        "oauth": manifest.get("oauth", {}) if isinstance(manifest.get("oauth"), dict) else {},
    }


def _redact_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(manifest)
    env = redacted.get("env")
    if isinstance(env, dict):
        redacted["env"] = {str(key): "***" for key in env}
    for key in ("token", "api_key", "secret", "password"):
        if key in redacted:
            redacted[key] = "***"
    return redacted


def _manifest_argv(manifest: dict[str, Any]) -> list[str]:
    if isinstance(manifest.get("argv"), list):
        return [str(item) for item in manifest["argv"] if str(item)]
    command = str(manifest.get("command") or "").strip()
    if not command:
        return []
    args = [str(item) for item in manifest.get("args", [])] if isinstance(manifest.get("args"), list) else []
    return [command, *args]


def _mcp_launch_path(config: AgentConfig) -> Path:
    return config.data_dir / "mcp" / "launches.json"


def _plugin_state_path(config: AgentConfig) -> Path:
    return config.data_dir / "plugins" / "state.json"


def _service_contract_tools() -> list[Tool]:
    tools: list[Tool] = []
    for name, mutating in [
        ("ha_list_entities", False),
        ("ha_get_state", False),
        ("ha_list_services", False),
        ("ha_call_service", True),
    ]:
        tools.append(ServiceContractTool(name, group="homeassistant", required_env=["HOME_ASSISTANT_URL", "HOME_ASSISTANT_TOKEN"], mutating=mutating))
    for name, mutating in [
        ("spotify_playback", True),
        ("spotify_devices", False),
        ("spotify_queue", True),
        ("spotify_search", False),
        ("spotify_playlists", False),
        ("spotify_albums", False),
        ("spotify_library", False),
    ]:
        tools.append(ServiceContractTool(name, group="spotify", required_env=["SPOTIFY_ACCESS_TOKEN"], mutating=mutating))
    for name, mutating in [
        ("feishu_doc_read", False),
        ("feishu_drive_list_comments", False),
        ("feishu_drive_list_comment_replies", False),
        ("feishu_drive_reply_comment", True),
        ("feishu_drive_add_comment", True),
    ]:
        tools.append(ServiceContractTool(name, group="feishu", required_env=["FEISHU_ACCESS_TOKEN"], mutating=mutating))
    for name, mutating in [
        ("yb_query_group_info", False),
        ("yb_query_group_members", False),
        ("yb_send_dm", True),
        ("yb_search_sticker", False),
        ("yb_send_sticker", True),
    ]:
        tools.append(ServiceContractTool(name, group="yuanbao", required_env=["YUANBAO_API_KEY"], mutating=mutating))
    tools.append(ServiceContractTool("x_search", group="research", required_env=["XAI_API_KEY"], mutating=False))
    tools.append(ServiceContractTool("discord", group="discord", required_env=["DISCORD_BOT_TOKEN"], mutating=True))
    tools.append(ServiceContractTool("discord_admin", group="discord", required_env=["DISCORD_BOT_TOKEN"], mutating=True))
    return tools


def _kanban_path(config: AgentConfig) -> Path:
    return config.data_dir / "kanban" / "boards.json"


def _load_kanban(config: AgentConfig) -> dict[str, Any]:
    state = _load_json(_kanban_path(config), default={})
    return state if isinstance(state, dict) else {}


def _save_kanban(config: AgentConfig, state: dict[str, Any]) -> None:
    _save_json(_kanban_path(config), state)


def _board_view(board: dict[str, Any]) -> dict[str, Any]:
    tasks = board.get("tasks", {})
    task_list = list(tasks.values()) if isinstance(tasks, dict) else []
    return {
        "board_id": board.get("board_id", "default"),
        "task_count": len(task_list),
        "tasks": sorted(task_list, key=lambda item: str(item.get("created_at", 0))),
    }


def _safe_contract_input(tool_input: dict[str, Any]) -> dict[str, Any]:
    blocked = {"token", "api_key", "secret", "password", "authorization"}
    safe: dict[str, Any] = {}
    for key, value in tool_input.items():
        lowered = str(key).lower()
        safe[key] = "***" if any(word in lowered for word in blocked) else value
    return safe


def _write_generation_spec(tool_name: str, config: AgentConfig, media_type: str, tool_input: dict[str, Any]) -> ToolResult:
    prompt = str(tool_input.get("prompt") or "").strip()
    if not prompt:
        return ToolResult(tool_name, ActionStatus.FAILED, RiskLevel.HIGH, f"{tool_name} requires prompt.")
    normalized = config.normalized()
    record = {
        "generation_id": f"{media_type}-gen-{uuid4().hex[:10]}",
        "media_type": media_type,
        "prompt": prompt,
        "provider": str(tool_input.get("provider") or "configured_default"),
        "image_url": str(tool_input.get("image_url") or ""),
        "reason": str(tool_input.get("reason") or ""),
        "created_at": time.time(),
        "status": "spec_created",
    }
    path = normalized.data_dir / "media" / "generation_requests" / f"{record['generation_id']}.json"
    if config.dry_run:
        return ToolResult(tool_name, ActionStatus.SKIPPED, RiskLevel.HIGH, f"Dry run: would create {media_type} generation request.", {"request": record, "path": str(path)})
    _save_json(path, record)
    return ToolResult(
        tool_name,
        ActionStatus.SUCCEEDED,
        RiskLevel.HIGH,
        f"Created {media_type} generation request {record['generation_id']}.",
        {"request": record, "path": str(path), "live_generation": "requires configured media provider runtime"},
    )


def _gateway_state_path(config: AgentConfig) -> Path:
    return config.data_dir / "gateway" / "control_state.json"


def _channel_delivery_path(config: AgentConfig) -> Path:
    return config.data_dir / "gateway" / "deliveries.json"


def _credential_policy_path(config: AgentConfig) -> Path:
    return config.data_dir / "security" / "credential_file_policy.json"


def _dependency_requests_path(config: AgentConfig) -> Path:
    return config.data_dir / "system" / "optional_dependency_requests.json"


def _skill_pack_build_path(config: AgentConfig) -> Path:
    return config.data_dir / "skills" / "native_pack_builds.json"


NATIVE_SKILL_CAPABILITY_TOOLS: dict[str, list[str]] = {
    "apple-notes": ["apple_notes_search", "apple_notes_create", "apple_notes_append_prepare"],
    "apple-reminders": ["apple_reminders_list", "apple_reminders_create", "apple_reminders_complete_prepare"],
    "find-my": ["find_my_open", "find_my_location_request_prepare"],
    "imessage": ["imessage_draft_create", "imessage_send_prepare", "imessage_transcript_request_prepare"],
    "macos-computer-use": ["macos_app_workflow_prepare"],
    "ascii-art-video": ["ascii_video_render_plan_create"],
    "comfyui": ["comfyui_workflow_prepare"],
    "manim": ["manim_scene_create"],
    "p5js": ["p5js_sketch_create"],
    "pretext": ["pretext_project_prepare"],
    "sketch": ["sketch_file_prepare"],
    "touchdesigner": ["touchdesigner_network_prepare"],
    "blender-mcp": ["blender_mcp_command_prepare"],
    "hyperframes": ["hyperframes_composition_prepare"],
    "meme-generation": ["meme_asset_create"],
    "pixel-art": ["pixel_art_create"],
    "music-workflows": ["music_workflow_prepare"],
    "jupyter-live-kernel": ["jupyter_live_kernel_execute_prepare"],
    "lm-eval": ["lm_eval_run_prepare"],
    "wandb": ["wandb_run_prepare"],
    "hugging-face": ["hugging_face_operation_prepare"],
    "llama-cpp": ["llama_cpp_command_prepare"],
    "vllm": ["vllm_server_prepare"],
    "chroma": ["chroma_collection_prepare"],
    "faiss": ["faiss_index_prepare"],
    "qdrant": ["qdrant_collection_prepare"],
    "pinecone": ["pinecone_index_prepare"],
    "peft": ["peft_training_prepare"],
    "modal": ["modal_job_prepare"],
    "lambda-labs": ["lambda_labs_instance_prepare"],
    "pytorch": ["pytorch_training_script_create"],
    "tensorrt-llm": ["tensorrt_llm_build_prepare"],
    "axolotl": ["axolotl_config_create"],
    "trl": ["trl_training_prepare"],
    "unsloth": ["unsloth_training_prepare"],
    "whisper": ["whisper_transcription_prepare"],
    "dspy": ["dspy_program_create"],
    "stable-diffusion": ["stable_diffusion_generation_prepare"],
    "llava": ["llava_inference_prepare"],
    "training-tools": ["model_training_plan_create"],
    "inference-tools": ["model_inference_plan_create"],
    "polymarket": ["polymarket_query_prepare"],
    "llm-wiki": ["llm_wiki_build_prepare"],
    "osint": ["osint_case_create"],
    "bioinformatics": ["bioinformatics_pipeline_prepare"],
    "drug-discovery": ["drug_discovery_screen_prepare"],
    "domain-intel": ["domain_intel_report_create"],
    "gitnexus": ["gitnexus_repo_intel_prepare"],
    "scrapling": ["scrapling_scrape_prepare"],
    "searxng": ["searxng_search_prepare"],
    "duckduckgo": ["duckduckgo_search_prepare"],
    "parallel-research": ["parallel_research_plan_create"],
    "sherlock": ["sherlock_username_search_prepare"],
    "onepassword": ["onepassword_item_request_prepare"],
    "oss-forensics": ["oss_forensics_report_create"],
    "web-pentest": ["web_pentest_scope_prepare"],
    "shopify": ["shopify_operation_prepare"],
    "shop-app": ["shop_app_order_prepare"],
    "canvas": ["canvas_course_packet_prepare"],
    "here-now": ["here_now_context_prepare"],
    "memento-flashcards": ["memento_flashcards_create"],
    "siyuan": ["siyuan_note_prepare"],
    "telephony": ["telephony_call_prepare"],
    "agentmail": ["agentmail_operation_prepare"],
    "himalaya": ["himalaya_email_operation_prepare"],
    "openhue": ["openhue_scene_prepare"],
    "x-social": ["x_social_post_prepare"],
    "finance-modeling": ["finance_model_create"],
    "agent-delegation": ["agent_delegation_prepare"],
    "honcho": ["honcho_processfile_create"],
    "openhands": ["openhands_task_prepare"],
    "antigravity-cli": ["antigravity_cli_task_prepare"],
    "blackbox": ["blackbox_prompt_prepare"],
    "grok": ["grok_request_prepare"],
    "docker-management": ["docker_container_list", "docker_compose_prepare"],
    "s6-supervision": ["s6_service_prepare"],
    "pinggy-tunnels": ["pinggy_tunnel_prepare"],
    "watchers": ["watcher_create"],
    "kanban-orchestrator": ["kanban_orchestrator_plan_create"],
    "kanban-worker": ["kanban_worker_packet_create"],
}


def _native_skill_path(config: AgentConfig, category: str, skill_name: str) -> Path:
    normalized = config.normalized()
    safe_category = _skill_domain(str(category or "general"), skill_name)
    safe_skill = _slug(skill_name)
    return normalized.workspace / "skills" / safe_category / safe_skill / "SKILL.md"


def _native_skill_markdown(pack: dict[str, Any], skill_name: str) -> str:
    category = str(pack.get("category") or "general")
    title = _title_from_slug(skill_name)
    tools = _native_skill_tools(category, skill_name)
    workflow = _native_skill_workflow(category, skill_name)
    safety = _native_skill_safety(category, skill_name)
    tool_lines = "\n".join(f"- `{tool}`" for tool in tools)
    workflow_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(workflow, start=1))
    safety_lines = "\n".join(f"- {item}" for item in safety)
    return f"""---
name: {skill_name}
description: Native Humungousaur skill for {title}. Use when a task calls for {title.lower()} workflows, readiness checks, artifacts, or approval-gated local/provider actions.
---

# {title}

This is a Humungousaur-native skill. It is authored inside this repository and uses only Humungousaur-owned tools, approval gates, artifacts, and optional dependency records.

## When To Use

Use this skill when the user asks for {title.lower()} planning, execution, verification, troubleshooting, or artifact creation inside Humungousaur.

## Tool Map

{tool_lines}

## Workflow

{workflow_lines}

## Safety And Boundaries

{safety_lines}

## Verification

- Record concrete evidence paths or tool outputs before claiming completion.
- Prefer dry-run or prepared artifacts when credentials, hardware, licenses, or live services are missing.
- If a provider-specific runtime is not configured, report the missing credential or binary by name and stop before live execution.
"""


def _native_skill_tools(category: str, skill_name: str) -> list[str]:
    common = ["tool_search", "tool_describe", "capability_surface", "write_note", "native_security_policy", "tool_output_store"]
    capability_tools = NATIVE_SKILL_CAPABILITY_TOOLS.get(skill_name, [])
    if category == "apple":
        return common + capability_tools + ["computer_use", "os_apps", "os_launch_app", "os_observe_ui", "os_click_element", "os_type_text", "os_send_keys", "screenshot_capture", "credential_file_policy"]
    if category == "creative":
        return common + capability_tools + ["media_storyboard_create", "media_storyboard_inspect", "sound_spec_create", "diagram_artifact_create", "image_generate", "video_generate", "vision_analyze", "optional_dependency_installer"]
    if category == "mlops":
        return common + capability_tools + ["execute_code", "python_interpreter", "process", "terminal", "provider_registry", "mcp_server_catalog", "mcp_tool_call", "optional_dependency_installer"]
    if category == "research":
        return common + capability_tools + ["web_search", "web_extract", "research_web_pages", "x_search", "provider_registry", "execute_code", "credential_file_policy"]
    if category == "productivity":
        return common + capability_tools + ["channel_message_prepare", "channel_message_send", "shopping_comparison_create", "shopping_comparison_inspect", "google_workspace_operation_prepare", "memory", "provider_registry"]
    if category == "devops":
        return common + capability_tools + ["delegate_task", "kanban_create", "kanban_list", "kanban_heartbeat", "kanban_complete", "process", "terminal", "mcp_server_catalog", "mcp_server_launch", "optional_dependency_installer"]
    return common


def _native_skill_workflow(category: str, skill_name: str) -> list[str]:
    label = _title_from_slug(skill_name).lower()
    base = [
        f"Clarify the user's concrete {label} objective, target environment, credentials already configured, and expected artifact or action.",
        "Use `tool_search` or `capability_surface` to find the native Humungousaur tools for the domain before choosing a path.",
        "Run safe inspection/readiness steps first and write bounded notes or artifacts under the workspace or data directory.",
    ]
    if category == "apple":
        base.extend(
            [
                "Use macOS app/control tools and screenshots for local Apple app workflows; do not rely on private Apple APIs unless the user explicitly configures an approved bridge.",
                "For messages, reminders, notes, or location workflows, prepare approval-gated actions and require user confirmation before sending, deleting, or changing personal data.",
            ]
        )
    elif category == "creative":
        base.extend(
            [
                "Create native briefs, storyboards, SVG/contact sheets, sound specs, prompts, or local code artifacts before attempting provider generation.",
                "Use optional dependency requests for domain engines such as ComfyUI, Manim, p5.js, TouchDesigner, Blender, or HyperFrames instead of silently installing them.",
            ]
        )
    elif category == "mlops":
        base.extend(
            [
                "Create reproducible scripts, notebooks, benchmark commands, model cards, or vector-store plans using bounded local code execution.",
                "Gate GPU/cloud/provider work behind `provider_registry`, credential readiness, and explicit approval.",
            ]
        )
    elif category == "research":
        base.extend(
            [
                "Collect sources with web/research tools, store evidence, and separate verified facts from hypotheses.",
                "For security or OSINT work, use defensive scope, authorization notes, and credential-file policy records before running active checks.",
            ]
        )
    elif category == "productivity":
        base.extend(
            [
                "Prepare drafts, comparisons, finance models, commerce plans, or channel messages as local artifacts before external submission.",
                "Keep purchases, sends, telephony, and account actions approval-gated.",
            ]
        )
    elif category == "devops":
        base.extend(
            [
                "Use kanban/delegation/process tools to coordinate native workers and long-running jobs with heartbeat records.",
                "Represent external CLIs or runtimes as optional dependency requests and launch packets until explicitly configured.",
            ]
        )
    base.append("Summarize what ran, what was skipped, what remains blocked, and the exact files or records created.")
    return base


def _native_skill_safety(category: str, skill_name: str) -> list[str]:
    rules = [
        "Do not import, execute, or vendor upstream assistant code for this skill.",
        "Do not store raw secrets; store only environment variable names, secret references, or readiness booleans.",
        "Use approvals for writes, sends, purchases, desktop control, process launches, provider calls, and destructive operations.",
    ]
    if category in {"research", "devops", "mlops"}:
        rules.append("Do not run network scans, exploit tooling, cloud jobs, or GPU workloads without explicit authorization and scope.")
    if category in {"apple", "productivity"}:
        rules.append("Treat personal data, messages, calendars, reminders, contacts, and location data as sensitive.")
    if category == "creative":
        rules.append("Respect licensing and avoid claiming a generated asset exists until a local file or provider result is present.")
    return rules


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "skill"


def _skill_domain(category: str, skill_name: str) -> str:
    name = _slug(skill_name)
    if category == "apple":
        return "desktop-control"
    if category == "creative":
        return "voice-media" if name in {
            "ascii-art-video",
            "comfyui",
            "manim",
            "p5js",
            "touchdesigner",
            "blender-mcp",
            "hyperframes",
            "meme-generation",
            "pixel-art",
            "music-workflows",
        } else "creative-design"
    if category in {"mlops", "research", "devops"}:
        return "software-engineering" if category != "devops" else "delegation-agents"
    if category == "productivity":
        if name in {"shopify", "shop-app"}:
            return "commerce-travel"
        if name in {"agentmail", "himalaya", "telephony", "x-social"}:
            return "communications"
        return "office-productivity"
    return "agent-core"


def _title_from_slug(value: str) -> str:
    return " ".join(part.upper() if part in {"llm", "api", "ui", "qa", "osint"} else part.capitalize() for part in _slug(value).split("-"))
