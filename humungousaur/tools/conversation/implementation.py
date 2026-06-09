from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.planning.model_clients import redact_secrets
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


class ConversationResponsePrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="conversation_response_prepare",
            description=(
                "Prepare a direct user-facing conversational reply when no external tool action is needed. "
                "Use this for greetings, brief chat, clarification, status acknowledgements, or lightweight responses."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "text": {"type": "string", "description": "The exact response text to show to the user."},
                    "reason": {"type": "string", "description": "Why a direct conversational response is sufficient."},
                    "tone": {"type": "string", "description": "Optional response tone, such as warm, concise, or calm."},
                },
                required=["text", "reason"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        text = redact_secrets(str(tool_input.get("text") or "").strip())
        reason = str(tool_input.get("reason") or "").strip()
        tone = str(tool_input.get("tone") or "").strip()
        if not text:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Conversation response text is required.")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            "Prepared direct conversational response.",
            {
                "text": text,
                "reason": reason,
                "tone": tone,
                "direct_user_response": True,
            },
        )


class TalkSessionStartTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="talk_session_start",
            description="Start a local native talk session record with activation names, provider hints, and fast context.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "activation_names": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                    "provider": {"type": "string"},
                    "mode": {"type": "string", "enum": ["voice", "text", "mixed"]},
                    "fast_context": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["mode", "reason"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        mode = str(tool_input.get("mode") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not mode or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Talk session mode and reason are required.")
        session_id = f"talk-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        payload = {
            "session_id": session_id,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "activation_names": _string_list(tool_input.get("activation_names"), limit=10),
            "provider": str(tool_input.get("provider") or "").strip(),
            "mode": mode,
            "fast_context": str(tool_input.get("fast_context") or "").strip()[:8000],
            "turn_context": "",
            "reason": reason,
            "transcript": [],
            "output_activity": [],
            "consults": [],
        }
        path = _talk_session_path(normalized, session_id)
        result = _write_json(normalized, path, payload, dry_run=config.dry_run)
        if result is not None:
            return result
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Started talk session {session_id}.", {"session": payload, "path": str(path)})


class TalkSessionRecordTurnTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="talk_session_record_turn",
            description="Append a user, assistant, system, or tool turn to a local talk session transcript.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "session_id": {"type": "string"},
                    "speaker": {"type": "string", "enum": ["user", "assistant", "system", "tool"]},
                    "text": {"type": "string"},
                    "modality": {"type": "string", "enum": ["text", "voice", "audio", "tool", "other"]},
                    "output_produced": {"type": "boolean"},
                },
                required=["session_id", "speaker", "text"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        session_id = str(tool_input.get("session_id") or "").strip()
        payload, path, error = _load_talk_session(normalized, session_id)
        if error:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, error)
        text = redact_secrets(str(tool_input.get("text") or "").strip())[:20_000]
        if not text:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Turn text is required.")
        turn = {
            "turn_id": f"turn-{uuid4().hex[:8]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "speaker": str(tool_input.get("speaker") or "").strip(),
            "modality": str(tool_input.get("modality") or "text").strip(),
            "text": text,
            "output_produced": bool(tool_input.get("output_produced", False)),
        }
        payload.setdefault("transcript", []).append(turn)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = _write_json(normalized, path, payload, dry_run=config.dry_run)
        if result is not None:
            return result
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Recorded talk turn for {session_id}.", {"turn": turn, "session_id": session_id})


class TalkContextUpdateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="talk_context_update",
            description="Update fast-context and turn-context notes for a local talk session.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "session_id": {"type": "string"},
                    "fast_context": {"type": "string"},
                    "turn_context": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["session_id", "reason"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        session_id = str(tool_input.get("session_id") or "").strip()
        payload, path, error = _load_talk_session(normalized, session_id)
        if error:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, error)
        if "fast_context" in tool_input:
            payload["fast_context"] = str(tool_input.get("fast_context") or "").strip()[:8000]
        if "turn_context" in tool_input:
            payload["turn_context"] = str(tool_input.get("turn_context") or "").strip()[:8000]
        payload["context_update_reason"] = str(tool_input.get("reason") or "").strip()
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = _write_json(normalized, path, payload, dry_run=config.dry_run)
        if result is not None:
            return result
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Updated talk context for {session_id}.", {"session_id": session_id, "fast_context": payload.get("fast_context", ""), "turn_context": payload.get("turn_context", "")})


class TalkOutputActivityRecordTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="talk_output_activity_record",
            description="Record whether a talk session produced usable output and in which modality.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "session_id": {"type": "string"},
                    "produced_output": {"type": "boolean"},
                    "modality": {"type": "string"},
                    "summary": {"type": "string"},
                },
                required=["session_id", "produced_output", "summary"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        session_id = str(tool_input.get("session_id") or "").strip()
        payload, path, error = _load_talk_session(normalized, session_id)
        if error:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, error)
        record = {
            "activity_id": f"activity-{uuid4().hex[:8]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "produced_output": bool(tool_input.get("produced_output", False)),
            "modality": str(tool_input.get("modality") or "").strip(),
            "summary": redact_secrets(str(tool_input.get("summary") or "").strip())[:4000],
        }
        payload.setdefault("output_activity", []).append(record)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = _write_json(normalized, path, payload, dry_run=config.dry_run)
        if result is not None:
            return result
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Recorded talk output activity for {session_id}.", {"activity": record})


class TalkSessionStatusTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="talk_session_status",
            description="Inspect one local talk session or list recent talk sessions.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "session_id": {"type": "string"},
                    "include_transcript": {"type": "boolean"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        session_id = str(tool_input.get("session_id") or "").strip()
        include_transcript = bool(tool_input.get("include_transcript", False))
        if session_id:
            payload, _, error = _load_talk_session(normalized, session_id)
            if error:
                return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, error)
            if not include_transcript:
                payload = {**payload, "transcript": []}
            return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Inspected talk session {session_id}.", {"session": payload})
        limit = max(1, min(int(tool_input.get("limit") or 10), 50))
        sessions = _list_talk_sessions(normalized, limit=limit)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Found {len(sessions)} talk session(s).", {"sessions": sessions})


class TalkTranscriptReadTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="talk_transcript_read",
            description="Read a bounded replay transcript for one local talk session.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"session_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, required=["session_id"]),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        session_id = str(tool_input.get("session_id") or "").strip()
        payload, _, error = _load_talk_session(normalized, session_id)
        if error:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, error)
        limit = max(1, min(int(tool_input.get("limit") or 50), 200))
        transcript = payload.get("transcript", [])[-limit:]
        replay = "\n".join(f"{turn.get('speaker', 'unknown')}: {turn.get('text', '')}" for turn in transcript)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Read {len(transcript)} talk transcript turn(s).", {"session_id": session_id, "transcript": transcript, "replay": replay[:40_000]})


class ConsultQuestionPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="consult_question_prepare",
            description="Prepare a human consult question, optionally blocking a talk session until answered.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "session_id": {"type": "string"},
                    "question": {"type": "string"},
                    "choices": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                    "blocking": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                required=["question", "reason"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        question = redact_secrets(str(tool_input.get("question") or "").strip())[:8000]
        reason = str(tool_input.get("reason") or "").strip()
        if not question or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Question and reason are required.")
        consult_id = f"consult-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        session_id = str(tool_input.get("session_id") or "").strip()
        payload = {
            "consult_id": consult_id,
            "session_id": session_id,
            "status": "awaiting_human",
            "blocking": bool(tool_input.get("blocking", True)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "choices": _string_list(tool_input.get("choices"), limit=10),
            "reason": reason,
            "answer": "",
            "resolved_at": "",
        }
        path = _consult_path(normalized, consult_id)
        result = _write_json(normalized, path, payload, dry_run=config.dry_run)
        if result is not None:
            return result
        if session_id:
            _attach_consult_to_session(normalized, session_id, consult_id)
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Prepared consult question {consult_id}.", {"consult": payload, "path": str(path)})


class ConsultQuestionResolveTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="consult_question_resolve",
            description="Resolve or cancel a prepared human consult question with the user's answer.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "consult_id": {"type": "string"},
                    "answer": {"type": "string"},
                    "status": {"type": "string", "enum": ["answered", "cancelled"]},
                },
                required=["consult_id", "status"],
            ),
            capability_group="conversation",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        consult_id = str(tool_input.get("consult_id") or "").strip()
        path = _consult_path(normalized, consult_id)
        payload = _load_json(path)
        if not payload:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Unknown consult question: {consult_id}")
        payload["status"] = str(tool_input.get("status") or "").strip()
        payload["answer"] = redact_secrets(str(tool_input.get("answer") or "").strip())[:8000]
        payload["resolved_at"] = datetime.now(timezone.utc).isoformat()
        result = _write_json(normalized, path, payload, dry_run=config.dry_run)
        if result is not None:
            return result
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, f"Resolved consult question {consult_id}.", {"consult": payload})


def default_conversation_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        ConversationResponsePrepareTool(),
        TalkSessionStartTool(),
        TalkSessionRecordTurnTool(),
        TalkContextUpdateTool(),
        TalkOutputActivityRecordTool(),
        TalkSessionStatusTool(),
        TalkTranscriptReadTool(),
        ConsultQuestionPrepareTool(),
        ConsultQuestionResolveTool(),
    ]
    return {tool.name: tool for tool in tools}


def _talk_dir(config: AgentConfig) -> Path:
    return config.normalized().data_dir / "talk_sessions"


def _talk_session_path(config: AgentConfig, session_id: str) -> Path:
    safe = _safe_id(session_id, prefix="talk")
    return (_talk_dir(config) / f"{safe}.json").resolve()


def _consult_path(config: AgentConfig, consult_id: str) -> Path:
    safe = _safe_id(consult_id, prefix="consult")
    return (config.normalized().data_dir / "consults" / f"{safe}.json").resolve()


def _load_talk_session(config: AgentConfig, session_id: str) -> tuple[dict[str, Any], Path, str]:
    if not session_id:
        return {}, _talk_session_path(config, "missing"), "Talk session id is required."
    path = _talk_session_path(config, session_id)
    payload = _load_json(path)
    if not payload:
        return {}, path, f"Unknown talk session: {session_id}"
    return payload, path, ""


def _list_talk_sessions(config: AgentConfig, *, limit: int) -> list[dict[str, Any]]:
    directory = _talk_dir(config)
    if not directory.exists():
        return []
    sessions = []
    for path in sorted(directory.glob("talk-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        payload = _load_json(path)
        if not payload:
            continue
        sessions.append(
            {
                "session_id": payload.get("session_id", path.stem),
                "status": payload.get("status", ""),
                "mode": payload.get("mode", ""),
                "turn_count": len(payload.get("transcript", [])) if isinstance(payload.get("transcript"), list) else 0,
                "consult_count": len(payload.get("consults", [])) if isinstance(payload.get("consults"), list) else 0,
                "updated_at": payload.get("updated_at", ""),
                "path": str(path),
            }
        )
    return sessions


def _attach_consult_to_session(config: AgentConfig, session_id: str, consult_id: str) -> None:
    payload, path, error = _load_talk_session(config, session_id)
    if error:
        return
    consults = payload.setdefault("consults", [])
    if consult_id not in consults:
        consults.append(consult_id)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(config, path, payload, dry_run=False)


def _write_json(config: AgentConfig, path: Path, payload: dict[str, Any], *, dry_run: bool) -> ToolResult | None:
    normalized = config.normalized()
    if not _is_within(path, normalized.allowed_write_roots):
        return ToolResult("conversation_state_write", ActionStatus.BLOCKED, RiskLevel.MEDIUM, "Conversation state path is outside allowed write roots.")
    if dry_run:
        return ToolResult("conversation_state_write", ActionStatus.SKIPPED, RiskLevel.MEDIUM, f"Dry run: would write {path}.", {"payload": payload, "path": str(path)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _string_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def _safe_id(value: str, *, prefix: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "-" for char in str(value or "")).strip("-_")
    if not cleaned.startswith(prefix):
        cleaned = f"{prefix}-{cleaned or uuid4().hex[:8]}"
    return cleaned


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
