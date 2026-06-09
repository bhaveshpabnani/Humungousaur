from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Callable

from humungousaur.cognition import CognitiveRecorder
from humungousaur.config import AgentConfig
from humungousaur.env import load_workspace_environment
from humungousaur.executor import Executor
from humungousaur.memory.event_store import EventStore
from humungousaur.memory.profile import build_user_profile, compact_user_profile
from humungousaur.planning.model_clients import ModelClient, ModelClientError, redact_secrets
from humungousaur.planning.model_factory import build_model_client
from humungousaur.planning.prompt_templates import load_prompt_template, render_prompt_template
from humungousaur.planning.providers import ExplicitFallbackPlanProvider, ModelPlanProvider, PlanProvider
from humungousaur.planning.structured import load_json_object
from humungousaur.planner import Planner
from humungousaur.safety.approvals import ApprovalStore
from humungousaur.safety.audit import AuditLog
from humungousaur.safety.policy import PolicyEngine
from humungousaur.schemas import ActionStatus, AgentRunResult, ApprovalRequest, PlannedStep, RiskLevel, ToolResult
from humungousaur.tools import default_tools
from humungousaur.tools.activity_tools import ActivityPolicyStore, _activity_event_visible, activity_policy_path
from humungousaur.tools.browser_tools import BrowserSessionStore
from humungousaur.tools.file_tools import summarize_text
from humungousaur.tools.os_tools import active_window_snapshot, list_screenshot_captures
from humungousaur.tools.system_tools import collect_system_status
from humungousaur.integrations.channels import load_channel_catalog
from humungousaur.tools.plugin_tools import load_plugin_catalog
from humungousaur.tools.skill_tools import discover_workspace_skills


MODEL_PLANNING_MAX_TURNS = 24
RESPONSE_PROMPT_RESOURCE = "resources/prompts/response.yaml"


class AgentOrchestrator:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config.normalized()
        load_workspace_environment(self.config.workspace)
        self.tools = default_tools(self.config)
        self.planner = Planner(self._build_plan_provider())
        self.audit = AuditLog(self.config.audit_db_path)
        self.approvals = ApprovalStore(self.config.approvals_db_path)
        self.memory = EventStore(self.config.memory_db_path)
        self.executor = Executor(self.tools, PolicyEngine())

    def _build_plan_provider(self) -> PlanProvider:
        fallback = ExplicitFallbackPlanProvider(set(self.tools.keys()))
        if self.config.planner_provider == "explicit":
            return fallback
        if self.config.planner_provider != "model":
            raise ValueError(f"Unknown planner provider: {self.config.planner_provider}")
        tool_catalog = {
            name: {
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "requires_approval": tool.requires_approval,
                "input_schema": tool.input_schema,
                "capability_group": tool.capability_group,
            }
            for name, tool in self.tools.items()
        }
        return ModelPlanProvider(
            self._build_model_client(),
            allowed_tools=set(self.tools.keys()),
            tool_catalog=tool_catalog,
            fallback=fallback,
        )

    def _build_model_client(self) -> ModelClient:
        return build_model_client(self.config)

    def run(
        self,
        request: str,
        approve_high_risk: bool = False,
        run_id: str | None = None,
        is_cancel_requested: Callable[[], bool] | None = None,
    ) -> AgentRunResult:
        run_id = self.audit.start_run(request, run_id=run_id)
        results: list[ToolResult] = []
        if self._cancel_requested(run_id, is_cancel_requested):
            return self._finish_cancelled(run_id, request, results)
        self.audit.log_run_event(run_id, "run_started", "Run started.", {"request": request})
        if self._cancel_requested(run_id, is_cancel_requested):
            return self._finish_cancelled(run_id, request, results)
        planning_context = {} if self.config.planner_provider == "explicit" else self._planning_context(request)
        self.audit.log_run_event(
            run_id,
            "planning_context_collected",
            "Collected compact local context for planning.",
            {"context_keys": sorted(planning_context.keys())},
        )
        plan = None
        if self.config.planner_provider == "model":
            plan = self._run_model_planning_loop(
                run_id,
                request,
                planning_context,
                results,
                approve_high_risk=approve_high_risk,
                is_cancel_requested=is_cancel_requested,
            )
            if self._cancel_requested(run_id, is_cancel_requested):
                return self._finish_cancelled(run_id, request, results)
        else:
            plan = self.planner.plan(request, context=planning_context)
            steps = self._normalize_steps(plan.steps)
            plan.steps = steps
            self._log_plan(run_id, plan, planning_context)
            if self._cancel_requested(run_id, is_cancel_requested):
                return self._finish_cancelled(run_id, request, results)
            if not steps:
                return self._finish_without_plan(run_id, request, plan, results)
            self._execute_steps(
                run_id,
                request,
                steps,
                results,
                approve_high_risk=approve_high_risk,
                is_cancel_requested=is_cancel_requested,
            )
            if self._cancel_requested(run_id, is_cancel_requested):
                return self._finish_cancelled(run_id, request, results)
        if not results and plan is not None:
            return self._finish_without_plan(run_id, request, plan, results)

        final_response = self._compose_response(request, results)
        if self._cancel_requested(run_id, is_cancel_requested):
            return self._finish_cancelled(run_id, request, results)
        note_path = self._write_summary_note(run_id, request, final_response, results)
        approvals = self._collect_approvals(results)
        status = self._run_status(results)
        if status == ActionStatus.NEEDS_APPROVAL:
            self.audit.pause_run(run_id, status, final_response)
            self.audit.log_run_event(
                run_id,
                "run_waiting_for_approval",
                "Run paused until a required approval is decided.",
                {"status": status.value, "approvals_requested": len(approvals), "note_path": note_path},
            )
        else:
            self.audit.finish_run(run_id, status, final_response)
            self.audit.log_run_event(
                run_id,
                "run_finished",
                f"Run finished with status {status.value}.",
                {
                    "status": status.value,
                    "approvals_requested": len(approvals),
                    "note_path": note_path,
                    "final_response": final_response,
                },
            )
        self.memory.append(
            "agent_run",
            {
                "run_id": run_id,
                "request": request,
                "status": status.value,
                "plan_provider": plan.used_provider,
                "plan_fallback_used": plan.fallback_used,
                "approvals_requested": len(approvals),
                "note_path": note_path,
            },
        )
        return AgentRunResult(
            run_id=run_id,
            request=request,
            final_response=final_response,
            results=results,
            approvals=approvals,
            note_path=note_path,
        )

    def _cancel_requested(self, run_id: str, is_cancel_requested: Callable[[], bool] | None) -> bool:
        return bool((is_cancel_requested and is_cancel_requested()) or self.audit.is_run_cancel_requested(run_id))

    def _finish_cancelled(self, run_id: str, request: str, results: list[ToolResult]) -> AgentRunResult:
        final_response = "Run cancelled before completing remaining actions."
        approvals = self._collect_approvals(results)
        self.audit.finish_run(run_id, ActionStatus.CANCELLED, final_response)
        self.audit.log_run_event(
            run_id,
            "run_cancelled",
            "Run stopped at a safe cancellation checkpoint.",
            {"completed_actions": len(results), "approvals_requested": len(approvals)},
        )
        self.memory.append(
            "agent_run",
            {
                "run_id": run_id,
                "request": request,
                "status": ActionStatus.CANCELLED.value,
                "approvals_requested": len(approvals),
                "note_path": None,
            },
        )
        return AgentRunResult(
            run_id=run_id,
            request=request,
            final_response=final_response,
            results=results,
            approvals=approvals,
            note_path=None,
        )

    def _finish_without_plan(self, run_id: str, request: str, plan: object, results: list[ToolResult]) -> AgentRunResult:
        error = getattr(plan, "error", None)
        final_response = (
            "I could not create a valid tool plan for that request. "
            "The model planner must return a structured plan, or the fallback must be an explicit command like "
            '`system_status {}` or a JSON object with `steps`.'
        )
        if error:
            final_response = f"{final_response}\n\nPlanner error: {error}"
        note_path = self._write_summary_note(run_id, request, final_response, results)
        self.audit.finish_run(run_id, ActionStatus.FAILED, final_response)
        self.audit.log_run_event(
            run_id,
            "run_finished",
            "Run finished without executable plan steps.",
            {"status": ActionStatus.FAILED.value, "note_path": note_path, "plan_error": error},
        )
        self.memory.append(
            "agent_run",
            {
                "run_id": run_id,
                "request": request,
                "status": ActionStatus.FAILED.value,
                "plan_provider": getattr(plan, "used_provider", ""),
                "plan_fallback_used": getattr(plan, "fallback_used", False),
                "approvals_requested": 0,
                "note_path": note_path,
            },
        )
        return AgentRunResult(
            run_id=run_id,
            request=request,
            final_response=final_response,
            results=results,
            approvals=[],
            note_path=note_path,
        )

    def _normalize_steps(self, steps: list[PlannedStep]) -> list[PlannedStep]:
        normalized: list[PlannedStep] = []
        for step in steps:
            if step.tool_name == "read_file":
                candidate = self.config.workspace / str(step.tool_input.get("path", ""))
                if not candidate.exists():
                    continue
            normalized.append(step)
        return normalized

    def _run_model_planning_loop(
        self,
        run_id: str,
        request: str,
        base_context: dict[str, object],
        results: list[ToolResult],
        *,
        approve_high_risk: bool,
        is_cancel_requested: Callable[[], bool] | None,
    ) -> object:
        last_plan: object | None = None
        seen_step_keys: set[str] = set()
        for turn_index in range(MODEL_PLANNING_MAX_TURNS):
            context = self._context_with_current_run(base_context, request, results, turn_index)
            plan = self._next_model_react_turn(request, context)
            last_plan = plan
            steps = self._normalize_steps(plan.steps)
            plan.steps = steps
            self._log_plan(run_id, plan, context)
            if self._cancel_requested(run_id, is_cancel_requested):
                break
            if not steps:
                break
            new_steps = self._dedupe_model_steps(steps, seen_step_keys)
            if not new_steps:
                repeated_result = ToolResult(
                    "model_planning_loop",
                    ActionStatus.SKIPPED,
                    RiskLevel.LOW,
                    "The model proposed an exact duplicate tool call; the loop will ask it to choose a different next action.",
                    {
                        "source": "model_planning_loop",
                        "turn_index": turn_index,
                        "repeated_steps": [
                            {"tool_name": step.tool_name, "tool_input": step.tool_input, "reason": step.reason}
                            for step in steps
                        ],
                    },
                    error="Duplicate model-planned tool call was rejected before execution.",
                )
                results.append(repeated_result)
                self.audit.log_action(run_id, {"turn_index": turn_index, "repeated_steps": [step.tool_name for step in steps]}, repeated_result)
                self.audit.log_run_event(
                    run_id,
                    "model_loop_duplicate_step",
                    "Rejected a duplicate model-planned tool input and continued the planning loop.",
                    {"turn_index": turn_index, "steps": [step.tool_name for step in steps]},
                )
                continue
            self._execute_steps(
                run_id,
                request,
                new_steps,
                results,
                approve_high_risk=approve_high_risk,
                is_cancel_requested=is_cancel_requested,
            )
            if self._model_loop_should_stop(new_steps, results) or self._cancel_requested(run_id, is_cancel_requested):
                break
        else:
            if not any(result.tool_name == "conversation_response_prepare" and result.status == ActionStatus.SUCCEEDED for result in results):
                result = ToolResult(
                    "model_planning_loop",
                    ActionStatus.FAILED,
                    RiskLevel.LOW,
                    "Reached the maximum model-planning turns before preparing a final answer.",
                    {
                        "source": "model_planning_loop",
                        "max_planning_turns": MODEL_PLANNING_MAX_TURNS,
                        "completed_actions": len(results),
                    },
                    error="Model planning loop exhausted without a final answer.",
                )
                results.append(result)
                self.audit.log_action(run_id, {"max_planning_turns": MODEL_PLANNING_MAX_TURNS}, result)
                self.audit.log_run_event(
                    run_id,
                    "model_loop_exhausted",
                    "Model planning loop reached the maximum turn count without a final answer.",
                    {"max_planning_turns": MODEL_PLANNING_MAX_TURNS, "completed_actions": len(results)},
                )
        return last_plan

    def _next_model_react_turn(self, request: str, context: dict[str, object]) -> object:
        react_step = getattr(self.planner.provider, "react_step", None)
        if callable(react_step):
            return react_step(request, context=context)
        return self.planner.plan(request, context=context)

    def _execute_steps(
        self,
        run_id: str,
        request: str,
        steps: list[PlannedStep],
        results: list[ToolResult],
        *,
        approve_high_risk: bool,
        is_cancel_requested: Callable[[], bool] | None,
    ) -> None:
        for step in steps:
            if self._cancel_requested(run_id, is_cancel_requested):
                return
            self.audit.log_run_event(
                run_id,
                "action_started",
                f"Starting {step.tool_name}.",
                {"tool_name": step.tool_name, "tool_input": step.tool_input, "reason": step.reason},
            )
            result = self.executor.execute(step, self.config, approved=approve_high_risk)
            results.append(result)
            self.audit.log_action(run_id, step.tool_input, result)
            self.audit.log_run_event(
                run_id,
                "action_finished",
                f"{step.tool_name} {result.status.value}.",
                {"tool_name": step.tool_name, "status": result.status.value, "summary": result.summary},
            )
            self._persist_approval_if_needed(run_id, request, result)
            if result.status == ActionStatus.NEEDS_APPROVAL or self._cancel_requested(run_id, is_cancel_requested):
                return

    def _log_plan(self, run_id: str, plan: object, context: dict[str, object]) -> None:
        self.audit.log_plan_trace(run_id, plan)
        steps = getattr(plan, "steps", [])
        self.audit.log_run_event(
            run_id,
            "plan_created",
            f"Planned {len(steps)} step(s) with {getattr(plan, 'used_provider', '')}.",
            {
                "requested_provider": getattr(plan, "requested_provider", ""),
                "used_provider": getattr(plan, "used_provider", ""),
                "fallback_used": getattr(plan, "fallback_used", False),
                "duration_ms": getattr(plan, "duration_ms", 0),
                "steps": [step.tool_name for step in steps],
                "planned_steps": [
                    {
                        "tool_name": step.tool_name,
                        "reason": step.reason,
                        "source": step.source,
                    }
                    for step in steps
                ],
                "active_workspace_skills": _compact_active_workspace_skills(
                    context.get("active_workspace_skills", [])
                ),
                "context_keys": sorted(context.keys()),
            },
        )

    def _context_with_current_run(
        self,
        base_context: dict[str, object],
        request: str,
        results: list[ToolResult],
        turn_index: int,
    ) -> dict[str, object]:
        context = dict(base_context)
        tool_counts = Counter(result.tool_name for result in results)
        repeated_tools = {name: count for name, count in sorted(tool_counts.items()) if count > 1}
        context["current_run"] = {
            "original_request": request,
            "planning_turn_index": turn_index,
            "max_planning_turns": MODEL_PLANNING_MAX_TURNS,
            "guidance": load_prompt_template("model_planning_loop_guidance").strip(),
            "tool_counts": dict(sorted(tool_counts.items())),
            "repeated_tools": repeated_tools,
            "action_history": [self._action_history_item(result) for result in results if result.tool_name != "write_note"][-12:],
            "observations": [self._result_for_response(result) for result in results if result.tool_name != "write_note"][-12:],
        }
        return context

    def _action_history_item(self, result: ToolResult) -> dict[str, object]:
        return {
            "tool_name": result.tool_name,
            "status": result.status.value,
            "summary": redact_secrets(result.summary),
            "source": result.output.get("source", ""),
            "error": redact_secrets(result.error or "") if result.error else "",
        }

    def _dedupe_model_steps(self, steps: list[PlannedStep], seen_step_keys: set[str]) -> list[PlannedStep]:
        unique: list[PlannedStep] = []
        for step in steps:
            key = json.dumps({"tool_name": step.tool_name, "tool_input": step.tool_input}, sort_keys=True, default=str)
            if key in seen_step_keys:
                continue
            seen_step_keys.add(key)
            unique.append(step)
        return unique

    def _model_loop_should_stop(self, steps: list[PlannedStep], results: list[ToolResult]) -> bool:
        if any(result.status == ActionStatus.NEEDS_APPROVAL for result in results):
            return True
        if any(step.tool_name == "conversation_response_prepare" for step in steps):
            return True
        return False

    def _planning_context(self, request: str = "") -> dict[str, object]:
        workspace_skills = self._workspace_skill_context()
        return {
            "workspace": str(self.config.workspace),
            "data_dir": str(self.config.data_dir),
            "system": self._system_context(),
            "active_window": self._active_window_context(),
            "screen_captures": self._screen_capture_context(),
            "recent_memory": self._recent_memory_context(),
            "activity_policy": self._activity_policy_context(),
            "user_profile": compact_user_profile(build_user_profile(self.memory, limit=100), per_section=3),
            "cognition": self._cognitive_context(),
            "browser_sessions": self._browser_context(),
            "available_workspace_skills": workspace_skills,
            "active_workspace_skills": self._selected_workspace_skill_context(request, workspace_skills),
            "capability_plugins": self._plugin_capability_context(),
            "gateway_channels": self._channel_capability_context(),
            "safety": {
                "retrieved_context_is_untrusted": True,
                "high_risk_actions_need_approval": True,
            },
        }

    def _system_context(self) -> dict[str, object]:
        status = collect_system_status(self.config)
        return {
            "overall_status": status.get("overall_status"),
            "platform": status.get("platform"),
            "warnings": status.get("warnings", []),
            "now_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        }

    def _active_window_context(self) -> dict[str, object]:
        snapshot = active_window_snapshot()
        return {
            "title": snapshot.get("title", ""),
            "supported": snapshot.get("supported", False),
            "platform": snapshot.get("platform", {}),
            "error": snapshot.get("error"),
        }

    def _browser_context(self) -> list[dict[str, object]]:
        try:
            sessions = BrowserSessionStore(self.config.browser_sessions_db_path).list(limit=3)
        except Exception:
            return []
        return [
            {
                "session_id": session["session_id"],
                "current_url": session["current_url"],
                "title": session["title"],
                "link_count": len(session.get("links", [])),
                "form_count": len(session.get("forms", [])),
                "updated_at": session["updated_at"],
            }
            for session in sessions
        ]

    def _workspace_skill_context(self) -> list[dict[str, object]]:
        try:
            skills = discover_workspace_skills(self.config)[:200]
        except Exception:
            return []
        return [
            {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description[:240],
                "relative_path": skill.relative_path,
                "domain": _skill_domain(skill.relative_path),
            }
            for skill in skills
        ]

    def _selected_workspace_skill_context(self, request: str, skills: list[dict[str, object]]) -> list[dict[str, object]]:
        if not request.strip() or not skills:
            return []
        selected_ids = self._select_relevant_workspace_skill_ids(request, skills)
        if not selected_ids:
            return []
        try:
            workspace_skills = discover_workspace_skills(self.config)
        except Exception:
            return []
        by_id = {skill.skill_id: skill for skill in workspace_skills}
        root_ids = self._hierarchical_root_skill_ids(selected_ids, by_id)
        skill_ids = self._expand_workspace_skill_ids(root_ids, by_id)
        skill_ids = self._ensure_selected_workspace_skills(skill_ids, selected_ids, by_id)
        active: list[dict[str, object]] = []
        remaining_chars = 60_000
        for skill_id, depth, parent_skill_id in skill_ids:
            skill = by_id.get(skill_id)
            if skill is None:
                continue
            try:
                content = skill.path.read_text(encoding="utf-8")
            except Exception:
                continue
            tool_map = _skill_reference_entries(content)
            child_refs = _skill_child_reference_payload(tool_map, by_id)
            content_mode = "full" if depth == 0 or skill_id in selected_ids else "summary"
            bounded = ""
            if content_mode == "full":
                bounded = content[: min(len(content), remaining_chars, 14_000)]
            summary = _skill_instruction_summary(content, skill.description)
            if not bounded and not summary:
                continue
            payload: dict[str, object] = {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description[:300],
                "relative_path": skill.relative_path,
                "domain": _skill_domain(skill.relative_path),
                "depth": depth,
                "parent_skill_id": parent_skill_id,
                "selected_directly": skill_id in selected_ids,
                "content_mode": content_mode,
                "summary": summary,
                "tool_map": tool_map[:40],
                "child_skill_refs": child_refs[:20],
            }
            if bounded:
                payload["content"] = bounded
                remaining_chars -= len(bounded)
            active.append(payload)
            if remaining_chars <= 0:
                break
        return active

    def _select_relevant_workspace_skill_ids(self, request: str, skills: list[dict[str, object]]) -> list[str]:
        skill_ids = [str(skill.get("skill_id") or "") for skill in skills if str(skill.get("skill_id") or "")]
        if not skill_ids:
            return []
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["skill_ids", "reason"],
            "properties": {
                "skill_ids": {
                    "type": "array",
                    "maxItems": min(5, len(skill_ids)),
                    "items": {"type": "string", "enum": skill_ids},
                },
                "reason": {"type": "string"},
            },
        }
        try:
            raw = self._build_model_client().complete_json(
                render_prompt_template(
                    "select_relevant_workspace_skills",
                    skill_catalog=json.dumps(skills, sort_keys=True, default=str, separators=(",", ":")),
                    user_request=request,
                ),
                schema,
            )
            payload = load_json_object(raw, label="Relevant workspace skill selector")
        except (ModelClientError, ValueError, json.JSONDecodeError):
            return []
        selected = payload.get("skill_ids")
        if not isinstance(selected, list):
            return []
        allowed = set(skill_ids)
        return [str(skill_id) for skill_id in selected if str(skill_id) in allowed]

    def _hierarchical_root_skill_ids(self, selected_ids: list[str], by_id: dict[str, object]) -> list[str]:
        roots: list[str] = []
        for skill_id in selected_ids:
            ancestors = _workspace_skill_ancestor_ids(skill_id, by_id)
            if ancestors:
                for ancestor_id in ancestors:
                    if ancestor_id not in roots:
                        roots.append(ancestor_id)
                continue
            if skill_id not in roots:
                roots.append(skill_id)
        return roots

    def _ensure_selected_workspace_skills(
        self,
        expanded: list[tuple[str, int, str]],
        selected_ids: list[str],
        by_id: dict[str, object],
    ) -> list[tuple[str, int, str]]:
        present = {skill_id for skill_id, _, _ in expanded}
        output = list(expanded)
        for skill_id in selected_ids:
            if skill_id in present or skill_id not in by_id:
                continue
            ancestors = _workspace_skill_ancestor_ids(skill_id, by_id)
            parent_skill_id = ancestors[-1] if ancestors else ""
            output.append((skill_id, len(ancestors), parent_skill_id))
            present.add(skill_id)
        return output

    def _expand_workspace_skill_ids(self, root_skill_ids: list[str], by_id: dict[str, object]) -> list[tuple[str, int, str]]:
        by_name: dict[str, str] = {}
        for skill_id, skill in by_id.items():
            name = str(getattr(skill, "name", "") or "").strip().lower()
            if name:
                by_name[name] = skill_id
        expanded: list[tuple[str, int, str]] = []
        queued: list[tuple[str, int, str]] = [(skill_id, 0, "") for skill_id in root_skill_ids]
        seen: set[str] = set()
        max_depth = 3
        max_skills = 12
        while queued and len(expanded) < max_skills:
            skill_id, depth, parent_skill_id = queued.pop(0)
            if skill_id in seen or skill_id not in by_id:
                continue
            seen.add(skill_id)
            expanded.append((skill_id, depth, parent_skill_id))
            if depth >= max_depth:
                continue
            skill = by_id[skill_id]
            try:
                content = getattr(skill, "path").read_text(encoding="utf-8")
            except Exception:
                continue
            for entry in _skill_reference_entries(content):
                child_id = entry if entry in by_id else by_name.get(entry.strip().lower())
                if child_id and child_id not in seen:
                    queued.append((child_id, depth + 1, skill_id))
        return expanded

    def _plugin_capability_context(self) -> list[dict[str, object]]:
        try:
            plugins = load_plugin_catalog()[:24]
        except Exception:
            return []
        return [
            {
                "plugin_id": plugin.get("plugin_id", ""),
                "kind": plugin.get("kind", ""),
                "status": plugin.get("status", ""),
                "channels": plugin.get("channels", [])[:8] if isinstance(plugin.get("channels"), list) else [],
                "tools": plugin.get("tools", [])[:8] if isinstance(plugin.get("tools"), list) else [],
                "skills": plugin.get("skills", [])[:8] if isinstance(plugin.get("skills"), list) else [],
            }
            for plugin in plugins
        ]

    def _channel_capability_context(self) -> list[dict[str, object]]:
        try:
            channels = load_channel_catalog()[:24]
        except Exception:
            return []
        return [
            {
                "channel_id": channel.get("channel_id", ""),
                "display_name": channel.get("display_name", channel.get("name", "")),
                "setup_kind": channel.get("setup_kind", ""),
                "direct_send": bool(
                    isinstance(channel.get("delivery", {}), dict)
                    and isinstance(channel.get("delivery", {}).get("official_send", {}), dict)
                    and channel.get("delivery", {}).get("official_send", {}).get("implemented", False)
                ),
                "ambient": bool(isinstance(channel.get("policies", {}), dict) and channel.get("policies", {}).get("ambient_room_events_supported", False)),
                "bot_loop": bool(isinstance(channel.get("policies", {}), dict) and channel.get("policies", {}).get("bot_loop_protection_supported", False)),
            }
            for channel in channels
        ]

    def _recent_memory_context(self) -> list[dict[str, object]]:
        policy = ActivityPolicyStore(activity_policy_path(self.config)).load()
        visible: list[dict[str, object]] = []
        for event in self.memory.tail(limit=15):
            if event.get("event_type") == "activity_event" and not _activity_event_visible(event, policy):
                continue
            visible.append(event)
            if len(visible) >= 5:
                break
        return visible

    def _activity_policy_context(self) -> dict[str, object]:
        policy = ActivityPolicyStore(activity_policy_path(self.config)).load()
        return {
            "retention_days": policy["retention_days"],
            "disabled_sources": policy["disabled_sources"],
            "excluded_apps_count": len(policy["excluded_apps"]),
            "excluded_window_terms_count": len(policy["excluded_window_terms"]),
            "excluded_url_domains_count": len(policy["excluded_url_domains"]),
            "excluded_text_terms_count": len(policy["excluded_text_terms"]),
        }

    def _screen_capture_context(self) -> dict[str, object]:
        captures = list_screenshot_captures(self.config, limit=3)
        return {
            "count": len(captures),
            "latest": [
                {
                    "filename": capture.get("filename"),
                    "created_at": capture.get("created_at"),
                    "width": capture.get("width"),
                    "height": capture.get("height"),
                    "reason": capture.get("reason", ""),
                    "image_bytes_served": False,
                }
                for capture in captures
            ],
        }

    def _cognitive_context(self) -> dict[str, object]:
        snapshot = CognitiveRecorder(self.config).snapshot()
        return {
            "active_goals": [asdict(goal) for goal in snapshot.active_goals[:5]],
            "active_tasks": [asdict(task) for task in snapshot.active_tasks[:8]],
            "focus": asdict(snapshot.focus),
            "persona": asdict(snapshot.persona),
            "knowledge": [asdict(record) for record in snapshot.knowledge[:5]],
            "learning": [asdict(record) for record in snapshot.learning[:5]],
            "consolidations": [asdict(record) for record in snapshot.consolidations[:5]],
            "wakeups": [asdict(record) for record in snapshot.wakeups[:5]],
            "recoveries": [asdict(record) for record in snapshot.recoveries[:5]],
            "briefings": [asdict(record) for record in snapshot.briefings[:5]],
            "curations": [asdict(record) for record in snapshot.curations[:5]],
            "skill_evolutions": [asdict(record) for record in snapshot.skill_evolutions[:5]],
            "persona_evolutions": [asdict(record) for record in snapshot.persona_evolutions[:5]],
            "self_reviews": [asdict(record) for record in snapshot.self_reviews[:5]],
            "interaction_reviews": [asdict(record) for record in snapshot.interaction_reviews[:5]],
            "commitments": [asdict(record) for record in snapshot.commitments[:5]],
            "commitment_reviews": [asdict(record) for record in snapshot.commitment_reviews[:5]],
            "environment": [asdict(record) for record in snapshot.environment[:5]],
            "environment_reviews": [asdict(record) for record in snapshot.environment_reviews[:5]],
            "priority_reviews": [asdict(record) for record in snapshot.priority_reviews[:5]],
            "skills": [asdict(skill) for skill in snapshot.skills[:5]],
            "specialists": [asdict(specialist) for specialist in snapshot.specialists[:5]],
        }

    def _compose_response(self, request: str, results: list[ToolResult]) -> str:
        direct_response = self._direct_result_response(results)
        if direct_response:
            return direct_response
        payload = {
            "request": request,
            "results": [self._result_for_response(result) for result in results if result.tool_name != "write_note"],
        }
        if self.config.planner_provider == "model":
            try:
                return self._compose_response_with_model(payload)
            except (ModelClientError, OSError, ValueError, json.JSONDecodeError, KeyError):
                pass
        return self._compose_generic_response(payload)

    def _compose_response_with_model(self, payload: dict[str, object]) -> str:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["response"],
            "properties": {
                "response": {"type": "string", "minLength": 1},
            },
        }
        prompt = render_prompt_template(
            "final_response",
            resource=RESPONSE_PROMPT_RESOURCE,
            run_data=json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        raw = self._build_model_client().complete_json(prompt, schema)
        document = json.loads(raw)
        response = str(document["response"]).strip()
        if not response:
            raise ValueError("Model response synthesis returned an empty response.")
        return redact_secrets(response)

    def _compose_generic_response(self, payload: dict[str, object]) -> str:
        request = str(payload.get("request", ""))
        results = payload.get("results", [])
        lines = [f"Request: {request}", ""]
        if not isinstance(results, list) or not results:
            lines.append("No tool actions were completed.")
            return "\n".join(lines).strip()
        for item in results:
            if not isinstance(item, dict):
                continue
            lines.append(f"{item.get('tool_name')}: {item.get('status')} - {item.get('summary')}")
            highlights = item.get("highlights", [])
            if isinstance(highlights, list):
                for highlight in highlights[:8]:
                    lines.append(f"- {highlight}")
        approvals = [
            item for item in results
            if isinstance(item, dict) and item.get("status") == ActionStatus.NEEDS_APPROVAL.value
        ]
        if approvals:
            lines.append("")
            lines.append("Approval needed:")
            for item in approvals:
                approval = item.get("approval", {})
                if isinstance(approval, dict):
                    lines.append(f"- {item.get('tool_name')} ({item.get('risk_level')}): {approval.get('reason', item.get('summary'))}")
                    lines.append(f"  token: {approval.get('approval_token', 'missing')}")
        return "\n".join(lines).strip()

    def _direct_result_response(self, results: list[ToolResult]) -> str:
        operational_results = [
            result for result in results
            if result.tool_name not in {"conversation_response_prepare", "write_note"}
        ]
        for result in reversed(results):
            if result.tool_name != "conversation_response_prepare" or result.status != ActionStatus.SUCCEEDED:
                continue
            text = str(result.output.get("text") or "").strip()
            if text:
                return redact_secrets(text)
        productivity_response = self._direct_productivity_response(operational_results)
        if productivity_response:
            return productivity_response
        for result in reversed(results):
            if result.tool_name != "conversation_response_prepare" or result.status != ActionStatus.SUCCEEDED:
                continue
            if operational_results:
                continue
            text = str(result.output.get("text") or "").strip()
            if text:
                return redact_secrets(text)
        for result in reversed(results):
            if result.tool_name != "voice_response_prepare" or result.status != ActionStatus.SUCCEEDED:
                continue
            text = str(result.output.get("text") or "").strip()
            path = str(result.output.get("path") or "").strip()
            audio = result.output.get("audio")
            audio_path = str(audio.get("audio_path") or "").strip() if isinstance(audio, dict) else ""
            lines = ["Prepared spoken reply."]
            if text:
                lines.append(f'Text: "{redact_secrets(text)}"')
            if path:
                lines.append(f"Artifact: {redact_secrets(path)}")
            if audio_path:
                lines.append(f"Audio: {redact_secrets(audio_path)}")
            return "\n".join(lines)
        return ""

    def _direct_productivity_response(self, results: list[ToolResult]) -> str:
        for result in reversed(results):
            if result.tool_name not in {"email_draft_prepare", "gmail_draft_prepare"} or result.status != ActionStatus.SUCCEEDED:
                continue
            draft = result.output.get("draft", {})
            if not isinstance(draft, dict):
                draft = {}
            lines = [
                "Prepared Gmail draft." if result.tool_name == "gmail_draft_prepare" else "Prepared email draft.",
                "Status: not sent; sending still requires explicit approval.",
            ]
            recipients = ", ".join(str(item) for item in draft.get("to", []) if item)
            if recipients:
                lines.append(f"To: {redact_secrets(recipients)}")
            subject = str(draft.get("subject") or "").strip()
            if subject:
                lines.append(f"Subject: {redact_secrets(subject)}")
            path = str(result.output.get("path") or "").strip()
            body_path = str(result.output.get("body_path") or "").strip()
            if path:
                lines.append(f"Draft artifact: {redact_secrets(path)}")
            if body_path:
                lines.append(f"Body file: {redact_secrets(body_path)}")
            return "\n".join(lines)
        created = next((result for result in results if result.tool_name == "xlsx_workbook_create" and result.status == ActionStatus.SUCCEEDED), None)
        inspected = next((result for result in results if result.tool_name == "xlsx_workbook_inspect" and result.status == ActionStatus.SUCCEEDED), None)
        if created is None:
            return ""
        path = str(created.output.get("path") or "").strip()
        lines = ["Created XLSX workbook."]
        if path:
            lines.append(f"Workbook: {redact_secrets(path)}")
        sheets = created.output.get("sheets", [])
        if isinstance(sheets, list) and sheets:
            lines.append(
                "Sheets: "
                + ", ".join(
                    f"{item.get('name')} ({item.get('rows')} rows, {item.get('columns')} columns)"
                    for item in sheets
                    if isinstance(item, dict)
                )
            )
        if inspected is not None:
            inspected_sheets = inspected.output.get("sheets", [])
            formula_count = 0
            if isinstance(inspected_sheets, list):
                formula_count = sum(len(item.get("formulas", [])) for item in inspected_sheets if isinstance(item, dict))
            lines.append(f"Inspection: succeeded; formulas found: {formula_count}.")
        return "\n".join(lines)

    def _result_for_response(self, result: ToolResult) -> dict[str, object]:
        payload: dict[str, object] = {
            "tool_name": result.tool_name,
            "status": result.status.value,
            "risk_level": result.risk_level.value,
            "summary": redact_secrets(result.summary),
            "error": redact_secrets(result.error or "") if result.error else "",
            "highlights": self._response_highlights(result),
        }
        approval = result.output.get("approval")
        if isinstance(approval, dict):
            payload["approval"] = {
                "tool_name": approval.get("tool_name"),
                "risk_level": result.risk_level.value,
                "reason": approval.get("reason"),
                "approval_token": approval.get("approval_token"),
            }
        return payload

    def _response_highlights(self, result: ToolResult) -> list[str]:
        highlights: list[str] = []
        output = result.output
        if output.get("path"):
            highlights.append(f"path: {output.get('path')}")
        if output.get("current_url"):
            highlights.append(f"url: {output.get('current_url')}")
        if output.get("live_session_id"):
            highlights.append(f"live_session_id: {output.get('live_session_id')}")
        if output.get("title"):
            highlights.append(f"title: {output.get('title')}")
        if output.get("overall_status"):
            highlights.append(f"status: {output.get('overall_status')}")
        stdout = str(output.get("stdout", "")).strip()
        if stdout:
            highlights.append(f"stdout: {redact_secrets(stdout[:1200])}")
        stderr = str(output.get("stderr", "")).strip()
        if stderr:
            highlights.append(f"stderr: {redact_secrets(stderr[:1200])}")
        text = str(output.get("text", "")).strip()
        if text:
            highlights.append(f"text: {redact_secrets(summarize_text(text, max_sentences=3)[:1200])}")
            if result.tool_name in {"fetch_web_page", "browser_observe", "browser_extract", "browser_live_observe"}:
                highlights.append(f"text_excerpt: {redact_secrets(text[:4000])}")
        for collection_key in (
            "files",
            "matches",
            "summaries",
            "limitations",
            "captures",
            "sessions",
            "responses",
            "results",
            "integrations",
            "runs",
            "tool_groups",
            "surfaces",
            "repeated_steps",
            "forms",
        ):
            value = output.get(collection_key)
            if isinstance(value, list):
                if result.tool_name == "summarize_pdfs" and collection_key == "summaries":
                    highlights.append(f"PDF summaries: {len(value)} files")
                else:
                    highlights.append(f"{collection_key}: {len(value)}")
                for item in value[:8]:
                    highlights.append(redact_secrets(self._compact_output_item(item)))
        return highlights[:16]

    def _compact_output_item(self, item: object) -> str:
        if isinstance(item, str):
            return item[:500]
        if not isinstance(item, dict):
            return str(item)[:500]
        parts = []
        for key in ("path", "line", "text", "summary", "url", "title", "name", "tool_name", "status", "event_type", "created_at", "response_id", "run_id", "reason"):
            if key in item and item.get(key) not in {None, ""}:
                parts.append(f"{key}={str(item.get(key))[:220]}")
        tool_input = item.get("tool_input")
        if isinstance(tool_input, dict):
            parts.append(f"tool_input={json.dumps(tool_input, ensure_ascii=False, sort_keys=True)[:300]}")
        snippets = item.get("snippets")
        if isinstance(snippets, list) and snippets:
            snippet_texts = []
            for snippet in snippets[:3]:
                if isinstance(snippet, dict) and snippet.get("text"):
                    snippet_texts.append(str(snippet["text"])[:300])
            if snippet_texts:
                parts.append(f"snippets={' | '.join(snippet_texts)}")
        return "; ".join(parts)[:700] or json.dumps(item, ensure_ascii=False, sort_keys=True)[:700]

    def _collect_approvals(self, results: list[ToolResult]) -> list[ApprovalRequest]:
        approvals: list[ApprovalRequest] = []
        for result in results:
            payload = result.output.get("approval")
            if not payload:
                continue
            approvals.append(
                ApprovalRequest(
                    tool_name=payload["tool_name"],
                    tool_input=payload["tool_input"],
                    risk_level=result.risk_level,
                    reason=payload["reason"],
                    approval_token=payload["approval_token"],
                )
            )
        return approvals

    def _persist_approval_if_needed(self, run_id: str, request: str, result: ToolResult) -> None:
        payload = result.output.get("approval")
        if not payload:
            return
        self.approvals.create_pending(
            run_id,
            request,
            ApprovalRequest(
                tool_name=payload["tool_name"],
                tool_input=payload["tool_input"],
                risk_level=result.risk_level,
                reason=payload["reason"],
                approval_token=payload["approval_token"],
            ),
        )

    def _run_status(self, results: list[ToolResult]) -> ActionStatus:
        if any(result.status == ActionStatus.NEEDS_APPROVAL for result in results):
            return ActionStatus.NEEDS_APPROVAL
        if any(result.status in {ActionStatus.FAILED, ActionStatus.BLOCKED} for result in results):
            return ActionStatus.FAILED
        return ActionStatus.SUCCEEDED

    def _write_summary_note(
        self,
        run_id: str,
        request: str,
        final_response: str,
        results: list[ToolResult],
    ) -> str | None:
        title = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{run_id[:8]}"
        content = f"# Agent Run {run_id}\n\n## Request\n\n{request}\n\n## Response\n\n{final_response}\n"
        step = PlannedStep(
            "write_note",
            {"title": title, "content": content},
            "Persist run summary for memory and review.",
        )
        result = self.executor.execute(step, self.config)
        results.append(result)
        self.audit.log_action(run_id, step.tool_input, result)
        if result.status == ActionStatus.SUCCEEDED:
            return str(result.output.get("path"))
        return None


def _skill_reference_entries(content: str) -> list[str]:
    entries: list[str] = []
    in_section = False
    wanted = {"tool map", "sub-skills", "subskills", "skill map"}
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lstrip("#").strip().lower() in wanted
            continue
        if in_section and stripped.startswith("#"):
            break
        if not in_section or not stripped.startswith("-"):
            continue
        entry = _first_backtick_value(stripped)
        if entry:
            entries.append(entry)
    return entries


def _skill_child_reference_payload(entries: list[str], by_id: dict[str, object]) -> list[dict[str, str]]:
    by_name: dict[str, object] = {}
    for skill in by_id.values():
        name = str(getattr(skill, "name", "") or "").strip().lower()
        if name:
            by_name[name] = skill
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in entries:
        skill = by_id.get(entry) or by_name.get(entry.strip().lower())
        if skill is None:
            continue
        skill_id = str(getattr(skill, "skill_id", "") or "")
        if not skill_id or skill_id in seen:
            continue
        seen.add(skill_id)
        refs.append(
            {
                "entry": entry,
                "skill_id": skill_id,
                "name": str(getattr(skill, "name", "") or ""),
                "relative_path": str(getattr(skill, "relative_path", "") or ""),
                "description": str(getattr(skill, "description", "") or "")[:240],
            }
        )
    return refs


def _skill_instruction_summary(content: str, fallback: str) -> str:
    parts = []
    purpose = _markdown_section_excerpt(content, {"purpose"}, limit=700)
    when_to_use = _markdown_section_excerpt(content, {"when to use", "when to use this skill"}, limit=700)
    if purpose:
        parts.append(f"Purpose: {purpose}")
    if when_to_use:
        parts.append(f"When to use: {when_to_use}")
    if not parts:
        body = _strip_frontmatter(content)
        parts.append((fallback or body).strip()[:900])
    return "\n".join(part for part in parts if part).strip()[:1_600]


def _markdown_section_excerpt(content: str, headings: set[str], *, limit: int) -> str:
    capture = False
    lines: list[str] = []
    for line in _strip_frontmatter(content).splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped.lstrip("#").strip().lower()
            if capture:
                break
            capture = heading in headings
            continue
        if capture:
            if stripped.startswith("#"):
                break
            if stripped:
                lines.append(stripped)
    return " ".join(lines)[:limit].strip()


def _strip_frontmatter(content: str) -> str:
    text = content.lstrip("\ufeff")
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end < 0:
        return text
    after = text.find("\n", end + 4)
    return text[after + 1 :] if after >= 0 else ""


def _skill_domain(relative_path: str) -> str:
    parts = Path(str(relative_path)).parts
    if len(parts) >= 3 and parts[0] == "skills":
        return parts[1]
    if len(parts) >= 4 and parts[0] == ".umang" and parts[1] == "skills":
        return parts[2]
    return ""


def _compact_active_workspace_skills(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    compact: list[dict[str, object]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "skill_id": str(item.get("skill_id") or ""),
                "name": str(item.get("name") or ""),
                "relative_path": str(item.get("relative_path") or ""),
                "domain": str(item.get("domain") or ""),
                "selected_directly": bool(item.get("selected_directly", False)),
                "content_mode": str(item.get("content_mode") or ""),
            }
        )
    return compact


def _workspace_skill_ancestor_ids(skill_id: str, by_id: dict[str, object]) -> list[str]:
    skill = by_id.get(skill_id)
    if skill is None:
        return []
    relative_path = str(getattr(skill, "relative_path", "") or "")
    if not relative_path:
        return []
    by_relative = {str(getattr(candidate, "relative_path", "") or ""): candidate_id for candidate_id, candidate in by_id.items()}
    path = Path(relative_path)
    ancestors: list[str] = []
    parents = list(path.parents)
    for parent in reversed(parents):
        if str(parent) in {"", "."}:
            continue
        candidate_relative = (parent / "SKILL.md").as_posix()
        candidate_id = by_relative.get(candidate_relative)
        if candidate_id and candidate_id != skill_id:
            ancestors.append(candidate_id)
    return ancestors


def _first_backtick_value(text: str) -> str:
    start = text.find("`")
    if start < 0:
        return ""
    end = text.find("`", start + 1)
    if end < 0:
        return ""
    return text[start + 1 : end].strip()
