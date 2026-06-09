from __future__ import annotations

from abc import ABC, abstractmethod
import json
import re
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from humungousaur.planning.model_clients import ModelClient, ModelClientError
from humungousaur.planning.prompt_templates import render_prompt_template
from humungousaur.planning.structured import PlanValidationError, StructuredPlanParser, step_tool_name
from humungousaur.schemas import PlannedStep, PlanResult


_FOUNDATIONAL_PLANNING_TOOLS = (
    "system_status",
    "tool_search",
    "tool_describe",
    "capability_surface",
    "conversation_response_prepare",
)


class PlanProvider(ABC):
    name: str

    @abstractmethod
    def plan(self, request: str, context: dict[str, Any] | None = None) -> PlanResult:
        raise NotImplementedError


class ExplicitFallbackPlanProvider(PlanProvider):
    """Narrow offline fallback for explicit tool-shaped commands only.

    This intentionally does not infer broad natural-language intent. It accepts
    either a full structured JSON plan or an exact tool command such as:

    - {"steps":[{"tool_name":"system_status","tool_input":{},"reason":"check"}]}
    - system_status {}
    - tool:voice_response_prepare {"text":"hello","reason":"test"}
    """

    name = "explicit"

    def __init__(self, allowed_tools: set[str] | None = None) -> None:
        self.allowed_tools = allowed_tools or set()

    def plan(self, request: str, context: dict[str, Any] | None = None) -> PlanResult:
        start = perf_counter()
        del context
        steps: list[PlannedStep] = []
        error: str | None = None
        try:
            steps = self._parse_explicit_plan(request)
        except PlanValidationError as exc:
            error = str(exc)
        return PlanResult(
            requested_provider=self.name,
            used_provider=self.name,
            steps=steps,
            error=error,
            duration_ms=round((perf_counter() - start) * 1000, 3),
        )

    def _parse_explicit_plan(self, request: str) -> list[PlannedStep]:
        text = request.strip()
        if not text:
            raise PlanValidationError("No request text was provided.")
        if text.startswith("{"):
            parser = StructuredPlanParser(self.allowed_tools) if self.allowed_tools else _PermissivePlanParser()
            steps = parser.parse(text)
            for step in steps:
                step.source = self.name
            return steps
        match = re.match(r"^(?:tool:)?(?P<tool>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<input>\{.*\})?\s*$", text, re.DOTALL)
        if match is None:
            raise PlanValidationError("Explicit fallback accepts only JSON plans or exact tool commands.")
        tool_name = match.group("tool")
        if self.allowed_tools and tool_name not in self.allowed_tools:
            raise PlanValidationError(f"Unknown or disallowed explicit fallback tool: {tool_name}")
        raw_input = match.group("input")
        if raw_input:
            try:
                tool_input = _load_explicit_tool_input(raw_input)
            except json.JSONDecodeError as exc:
                raise PlanValidationError(f"Explicit tool input must be valid JSON: {exc}") from exc
            if not isinstance(tool_input, dict):
                raise PlanValidationError("Explicit tool input must be a JSON object.")
        else:
            tool_input = {}
        return [PlannedStep(tool_name, tool_input, "Explicit user-selected tool command.", self.name)]


def _load_explicit_tool_input(raw_input: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        if "Invalid \\escape" not in str(exc) or "\\" not in raw_input:
            raise
        payload = json.loads(raw_input.replace("\\", "\\\\"))
    if not isinstance(payload, dict):
        raise PlanValidationError("Explicit tool input must be a JSON object.")
    return payload


class _PermissivePlanParser(StructuredPlanParser):
    def __init__(self) -> None:
        super().__init__(set())

    def _validate_step(self, index: int, tool_name: Any, tool_input: Any, reason: Any) -> None:
        if not isinstance(tool_name, str) or not tool_name:
            raise PlanValidationError(f"Step {index} has invalid tool_name.")
        if not isinstance(tool_input, dict):
            raise PlanValidationError(f"Step {index} tool_input must be an object.")
        if not isinstance(reason, str) or not reason.strip():
            raise PlanValidationError(f"Step {index} reason must be a non-empty string.")


class ModelPlanProvider(PlanProvider):
    name = "model"

    def __init__(
        self,
        model_client: ModelClient,
        allowed_tools: set[str],
        tool_catalog: dict[str, dict[str, Any]] | None = None,
        fallback: PlanProvider | None = None,
        max_prompt_tools: int = 64,
        max_candidate_groups: int = 4,
    ) -> None:
        self.model_client = model_client
        self.allowed_tools = allowed_tools
        self.parser = StructuredPlanParser(self.allowed_tools)
        self.tool_catalog = tool_catalog or {}
        self.fallback = fallback or ExplicitFallbackPlanProvider(allowed_tools)
        self.max_prompt_tools = max(4, int(max_prompt_tools))
        self.max_candidate_groups = max(1, int(max_candidate_groups))

    def plan(self, request: str, context: dict[str, Any] | None = None) -> PlanResult:
        start = perf_counter()
        planning_context = context or {}
        try:
            candidate_tools = self._candidate_tools_for_request(request, planning_context)
            active_parser = StructuredPlanParser(candidate_tools)
            prompt = self._build_prompt(request, planning_context, candidate_tools)
            plan_schema = self._plan_schema_for_tools(candidate_tools, active_parser.max_steps)
            raw_plan = self.model_client.complete_json(prompt, plan_schema)
            try:
                steps = self._parse_and_validate_plan(active_parser, raw_plan)
                source = f"model:{self.model_client.name}"
            except PlanValidationError as exc:
                try:
                    raw_plan = self._repair_plan(request, planning_context, active_parser, plan_schema=plan_schema, raw_plan=raw_plan, error=str(exc))
                    steps = self._parse_and_validate_plan(active_parser, raw_plan)
                except PlanValidationError as repair_exc:
                    raw_plan = self._repair_tool_input_plan(request, active_parser, raw_plan=raw_plan, error=str(repair_exc))
                    steps = self._parse_and_validate_plan(active_parser, raw_plan)
                source = f"model:{self.model_client.name}:repair"
            for step in steps:
                step.source = source
            return PlanResult(
                requested_provider=self.name,
                used_provider=source,
                steps=steps,
                duration_ms=round((perf_counter() - start) * 1000, 3),
            )
        except (ModelClientError, PlanValidationError, ValueError) as exc:
            fallback_result = self.fallback.plan(request, context)
            fallback_error = fallback_result.error
            fallback_result.requested_provider = self.name
            fallback_result.fallback_used = True
            fallback_result.error = f"{exc}; fallback: {fallback_error}" if fallback_error else str(exc)
            fallback_result.duration_ms = round((perf_counter() - start) * 1000, 3)
            return fallback_result

    def react_step(self, request: str, context: dict[str, Any] | None = None) -> PlanResult:
        start = perf_counter()
        planning_context = context or {}
        try:
            candidate_tools = self._candidate_tools_for_request(request, planning_context)
            active_parser = StructuredPlanParser(candidate_tools, max_steps=1)
            prompt = self._build_react_prompt(request, planning_context, candidate_tools)
            schema = self._react_schema_for_tools(candidate_tools)
            raw_step = self.model_client.complete_json(prompt, schema)
            try:
                steps = self._parse_react_step(active_parser, raw_step, request=request, context=planning_context)
            except PlanValidationError as exc:
                raw_step = self._repair_react_step(
                    request,
                    planning_context,
                    active_parser,
                    schema=schema,
                    raw_step=raw_step,
                    error=str(exc),
                )
                steps = self._parse_react_step(active_parser, raw_step, request=request, context=planning_context)
            source = f"react:{self.model_client.name}"
            for step in steps:
                step.source = source
            return PlanResult(
                requested_provider=self.name,
                used_provider=source,
                steps=steps,
                duration_ms=round((perf_counter() - start) * 1000, 3),
            )
        except (ModelClientError, PlanValidationError, ValueError, json.JSONDecodeError) as exc:
            fallback_result = self.fallback.plan(request, context)
            fallback_error = fallback_result.error
            fallback_result.requested_provider = self.name
            fallback_result.fallback_used = True
            fallback_result.error = f"{exc}; fallback: {fallback_error}" if fallback_error else str(exc)
            fallback_result.duration_ms = round((perf_counter() - start) * 1000, 3)
            return fallback_result

    def _parse_and_validate_plan(self, parser: StructuredPlanParser, raw_plan: str) -> list[PlannedStep]:
        steps = parser.parse(raw_plan)
        for index, step in enumerate(steps, start=1):
            schema = self.tool_catalog.get(step.tool_name, {}).get("input_schema")
            if not isinstance(schema, dict):
                continue
            try:
                _validate_planned_tool_input(step.tool_input, schema)
            except ValueError as exc:
                raise PlanValidationError(f"Step {index} input for {step.tool_name} is invalid: {exc}") from exc
        return steps

    def _plan_schema_for_tools(self, tool_names: set[str], max_steps: int) -> dict[str, Any]:
        step_variants: list[dict[str, Any]] = []
        for tool_name in sorted(tool_names):
            input_schema = self.tool_catalog.get(tool_name, {}).get("input_schema")
            if not isinstance(input_schema, dict):
                input_schema = {"type": "object", "additionalProperties": True}
            step_variants.append(
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tool_name", "tool_input", "reason"],
                    "properties": {
                        "tool_name": {"type": "string", "enum": [tool_name]},
                        "tool_input": input_schema,
                        "reason": {"type": "string", "minLength": 1},
                    },
                }
            )
        item_schema: dict[str, Any]
        if step_variants:
            item_schema = {"anyOf": step_variants}
        else:
            item_schema = {
                "type": "object",
                "additionalProperties": False,
                "required": ["tool_name", "tool_input", "reason"],
                "properties": {
                    "tool_name": {"type": "string", "enum": sorted(tool_names)},
                    "tool_input": {"type": "object", "additionalProperties": True},
                    "reason": {"type": "string", "minLength": 1},
                },
            }
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["steps"],
            "properties": {
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": max_steps,
                    "items": item_schema,
                }
            },
        }

    def _react_schema_for_tools(self, tool_names: set[str]) -> dict[str, Any]:
        variants: list[dict[str, Any]] = []
        for tool_name in sorted(tool_names):
            input_schema = self.tool_catalog.get(tool_name, {}).get("input_schema")
            if not isinstance(input_schema, dict):
                input_schema = {"type": "object", "additionalProperties": True}
            variants.append(
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["decision", "tool_name", "tool_input", "reason"],
                    "properties": {
                        "decision": {"type": "string", "enum": ["act"]},
                        "tool_name": {"type": "string", "enum": [tool_name]},
                        "tool_input": input_schema,
                        "reason": {"type": "string", "minLength": 1},
                        "scratchpad_summary": {"type": "string"},
                    },
                }
            )
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["decision", "final_response", "reason"],
                "properties": {
                    "decision": {"type": "string", "enum": ["final"]},
                    "final_response": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                    "scratchpad_summary": {"type": "string"},
                },
            }
        )
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["turn"],
            "properties": {"turn": {"anyOf": variants}},
        }

    def _parse_react_step(
        self,
        parser: StructuredPlanParser,
        raw_step: str,
        *,
        request: str,
        context: dict[str, Any] | None = None,
    ) -> list[PlannedStep]:
        document = json.loads(raw_step)
        if not isinstance(document, dict):
            raise PlanValidationError("ReAct turn must be a JSON object.")
        turn = document.get("turn")
        if not isinstance(turn, dict):
            raise PlanValidationError("ReAct turn must include a `turn` object.")
        decision = str(turn.get("decision", "")).strip().lower()
        if decision == "final":
            final_response = str(turn.get("final_response", "")).strip()
            reason = str(turn.get("reason", "")).strip() or "Final ReAct answer."
            if not final_response:
                raise PlanValidationError("Final ReAct response is empty.")
            self._review_react_final(request=request, context=context or {}, parser=parser, final_response=final_response, reason=reason)
            if "conversation_response_prepare" not in parser.allowed_tools:
                return []
            step = PlannedStep(
                "conversation_response_prepare",
                {"text": final_response, "reason": reason},
                reason,
            )
            _validate_planned_tool_input(step.tool_input, self.tool_catalog.get(step.tool_name, {}).get("input_schema", {}))
            return [step]
        if decision != "act":
            raise PlanValidationError("ReAct turn decision must be `act` or `final`.")
        tool_name = str(turn.get("tool_name") or "")
        self._review_react_action_if_repeated(request=request, context=context or {}, parser=parser, turn=turn)
        self._review_live_session_continuity(request=request, context=context or {}, parser=parser, turn=turn)
        self._review_live_navigation_churn(request=request, context=context or {}, parser=parser, turn=turn)
        self._review_static_browser_form_action(request=request, context=context or {}, parser=parser, turn=turn)
        self._review_live_browser_js_action(request=request, context=context or {}, parser=parser, turn=turn)
        plan_payload = json.dumps(
            {
                "steps": [
                    {
                        "tool_name": tool_name,
                        "tool_input": turn.get("tool_input", {}),
                        "reason": turn.get("reason", "ReAct tool action."),
                    }
                ]
            },
            ensure_ascii=False,
        )
        return self._parse_and_validate_plan(parser, plan_payload)

    def _review_react_action_if_repeated(
        self,
        *,
        request: str,
        context: dict[str, Any],
        parser: StructuredPlanParser,
        turn: dict[str, Any],
    ) -> None:
        tool_name = str(turn.get("tool_name") or "")
        current_run = context.get("current_run")
        tool_counts = current_run.get("tool_counts", {}) if isinstance(current_run, dict) else {}
        try:
            prior_count = int(tool_counts.get(tool_name, 0)) if isinstance(tool_counts, dict) else 0
        except (TypeError, ValueError):
            prior_count = 0
        if prior_count < 2:
            return
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["accept", "reason", "suggested_next_action"],
            "properties": {
                "accept": {"type": "boolean"},
                "reason": {"type": "string", "minLength": 1},
                "suggested_next_action": {"type": "string"},
            },
        }
        prompt = self._render_tool_review_prompt(
            "review_repeated_action",
            parser=parser,
            context=context,
            request=request,
            proposed_action=json.dumps(turn, ensure_ascii=False, sort_keys=True, separators=(",", ":"))[:4000],
        )
        raw = self.model_client.complete_json(prompt, schema)
        try:
            review = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Repeated-action review must return valid JSON: {exc}") from exc
        if not isinstance(review, dict):
            raise PlanValidationError("Repeated-action review must return a JSON object.")
        if not bool(review.get("accept")):
            review_reason = str(review.get("reason") or "The proposed repeated action does not change method.").strip()
            next_action = str(review.get("suggested_next_action") or "").strip()
            suffix = f" Suggested next action: {next_action}" if next_action else ""
            raise PlanValidationError(f"Repeated ReAct action rejected by model-led review: {review_reason}{suffix}")

    def _review_live_session_continuity(
        self,
        *,
        request: str,
        context: dict[str, Any],
        parser: StructuredPlanParser,
        turn: dict[str, Any],
    ) -> None:
        tool_name = str(turn.get("tool_name") or "")
        if tool_name != "browser_live_open":
            return
        if not _context_has_live_browser_session(context):
            return
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["accept", "reason", "suggested_next_action"],
            "properties": {
                "accept": {"type": "boolean"},
                "reason": {"type": "string", "minLength": 1},
                "suggested_next_action": {"type": "string"},
            },
        }
        prompt = self._render_tool_review_prompt(
            "review_live_session_continuity",
            parser=parser,
            context=context,
            request=request,
            proposed_action=json.dumps(turn, ensure_ascii=False, sort_keys=True, separators=(",", ":"))[:4000],
        )
        raw = self.model_client.complete_json(prompt, schema)
        try:
            review = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Live-browser continuity review must return valid JSON: {exc}") from exc
        if not isinstance(review, dict):
            raise PlanValidationError("Live-browser continuity review must return a JSON object.")
        if not bool(review.get("accept")):
            review_reason = str(review.get("reason") or "The existing live browser session should be reused.").strip()
            next_action = str(review.get("suggested_next_action") or "").strip()
            suffix = f" Suggested next action: {next_action}" if next_action else ""
            raise PlanValidationError(f"Live-browser continuity review rejected action: {review_reason}{suffix}")

    def _review_live_navigation_churn(
        self,
        *,
        request: str,
        context: dict[str, Any],
        parser: StructuredPlanParser,
        turn: dict[str, Any],
    ) -> None:
        tool_name = str(turn.get("tool_name") or "")
        navigational_tools = {
            "browser_live_search",
            "browser_live_new_tab",
            "browser_live_open",
            "web_search",
            "research_web_pages",
            "research_webpages",
        }
        if tool_name not in navigational_tools:
            return
        if not _context_has_live_browser_session(context) and not _context_has_tool_observation(
            context,
            {"web_search", "research_web_pages", "research_webpages"},
        ):
            return
        observed_urls = _context_observed_urls(context)
        tool_input = turn.get("tool_input")
        tool_input = tool_input if isinstance(tool_input, dict) else {}
        proposed_url = str(tool_input.get("url") or "").strip()
        if observed_urls and tool_name in {"browser_live_search", "web_search"}:
            raise PlanValidationError(
                "Live navigation action rejected by grounded-source review: prior observations already contain concrete source URLs; inspect one of those URLs before searching again."
            )
        if observed_urls and proposed_url and not _url_is_from_observations(proposed_url, observed_urls):
            raise PlanValidationError(
                "Live navigation action rejected by grounded-source review: the proposed URL was not found in prior search/research observations. Suggested next action: open or inspect one of the concrete URLs already present in runtime context."
            )
        if observed_urls and proposed_url and _url_is_from_observations(proposed_url, observed_urls):
            return
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["accept", "reason", "suggested_next_action"],
            "properties": {
                "accept": {"type": "boolean"},
                "reason": {"type": "string", "minLength": 1},
                "suggested_next_action": {"type": "string"},
            },
        }
        prompt = self._render_tool_review_prompt(
            "review_live_navigation_churn",
            parser=parser,
            context=context,
            request=request,
            proposed_action=json.dumps(turn, ensure_ascii=False, sort_keys=True, separators=(",", ":"))[:5000],
        )
        raw = self.model_client.complete_json(prompt, schema)
        try:
            review = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Live navigation review must return valid JSON: {exc}") from exc
        if not isinstance(review, dict):
            raise PlanValidationError("Live navigation review must return a JSON object.")
        if not bool(review.get("accept")):
            review_reason = str(review.get("reason") or "The proposed navigation action abandons usable page state.").strip()
            next_action = str(review.get("suggested_next_action") or "").strip()
            suffix = f" Suggested next action: {next_action}" if next_action else ""
            raise PlanValidationError(f"Live navigation action rejected by model-led review: {review_reason}{suffix}")

    def _review_static_browser_form_action(
        self,
        *,
        request: str,
        context: dict[str, Any],
        parser: StructuredPlanParser,
        turn: dict[str, Any],
    ) -> None:
        tool_name = str(turn.get("tool_name") or "")
        if tool_name != "browser_fill_form":
            return
        if not _context_has_tool_observation(
            context,
            {"browser_open", "browser_observe", "browser_extract", "browser_fill_form"},
        ):
            return
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["accept", "reason", "suggested_next_action"],
            "properties": {
                "accept": {"type": "boolean"},
                "reason": {"type": "string", "minLength": 1},
                "suggested_next_action": {"type": "string"},
            },
        }
        prompt = self._render_tool_review_prompt(
            "review_static_browser_form_action",
            parser=parser,
            context=context,
            request=request,
            proposed_action=json.dumps(turn, ensure_ascii=False, sort_keys=True, separators=(",", ":"))[:5000],
        )
        raw = self.model_client.complete_json(prompt, schema)
        try:
            review = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Static browser form review must return valid JSON: {exc}") from exc
        if not isinstance(review, dict):
            raise PlanValidationError("Static browser form review must return a JSON object.")
        if not bool(review.get("accept")):
            review_reason = str(review.get("reason") or "The proposed static form action is not supported by observed page forms.").strip()
            next_action = str(review.get("suggested_next_action") or "").strip()
            suffix = f" Suggested next action: {next_action}" if next_action else ""
            raise PlanValidationError(f"Static browser form action rejected by model-led review: {review_reason}{suffix}")

    def _review_live_browser_js_action(
        self,
        *,
        request: str,
        context: dict[str, Any],
        parser: StructuredPlanParser,
        turn: dict[str, Any],
    ) -> None:
        tool_name = str(turn.get("tool_name") or "")
        if tool_name != "browser_live_evaluate_js":
            return
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["accept", "reason", "suggested_next_action"],
            "properties": {
                "accept": {"type": "boolean"},
                "reason": {"type": "string", "minLength": 1},
                "suggested_next_action": {"type": "string"},
            },
        }
        prompt = self._render_tool_review_prompt(
            "review_live_browser_js_action",
            parser=parser,
            context=context,
            request=request,
            proposed_action=json.dumps(turn, ensure_ascii=False, sort_keys=True, separators=(",", ":"))[:6000],
        )
        raw = self.model_client.complete_json(prompt, schema)
        try:
            review = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Live-browser JavaScript review must return valid JSON: {exc}") from exc
        if not isinstance(review, dict):
            raise PlanValidationError("Live-browser JavaScript review must return a JSON object.")
        if not bool(review.get("accept")):
            review_reason = str(review.get("reason") or "The JavaScript action is not adequately verified.").strip()
            next_action = str(review.get("suggested_next_action") or "").strip()
            suffix = f" Suggested next action: {next_action}" if next_action else ""
            raise PlanValidationError(f"Live-browser JavaScript action rejected by model-led review: {review_reason}{suffix}")

    def _review_react_final(
        self,
        *,
        request: str,
        context: dict[str, Any],
        parser: StructuredPlanParser,
        final_response: str,
        reason: str,
    ) -> None:
        evidence_tools = parser.allowed_tools - {"conversation_response_prepare"}
        if not evidence_tools:
            return
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["accept", "reason", "suggested_next_action"],
            "properties": {
                "accept": {"type": "boolean"},
                "reason": {"type": "string", "minLength": 1},
                "suggested_next_action": {"type": "string"},
            },
        }
        prompt = self._render_tool_review_prompt(
            "review_react_final",
            parser=parser,
            context=context,
            request=request,
            reason=reason,
            final_response=final_response[:4000],
        )
        raw = self.model_client.complete_json(prompt, schema)
        try:
            review = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Final ReAct review must return valid JSON: {exc}") from exc
        if not isinstance(review, dict):
            raise PlanValidationError("Final ReAct review must return a JSON object.")
        if not bool(review.get("accept")):
            review_reason = str(review.get("reason") or "The proposed final answer needs another tool observation.").strip()
            next_action = str(review.get("suggested_next_action") or "").strip()
            suffix = f" Suggested next action: {next_action}" if next_action else ""
            raise PlanValidationError(f"Final ReAct response rejected by model-led review: {review_reason}{suffix}")

    def _repair_react_step(
        self,
        request: str,
        context: dict[str, Any],
        parser: StructuredPlanParser,
        *,
        schema: dict[str, Any],
        raw_step: str,
        error: str,
    ) -> str:
        prompt = self._render_tool_review_prompt(
            "repair_react_turn",
            parser=parser,
            context=context,
            request=request,
            error=error,
            raw_turn=raw_step[:4000],
        )
        return self.model_client.complete_json(prompt, schema)

    def _candidate_tools_for_request(self, request: str, context: dict[str, Any]) -> set[str]:
        if len(self.allowed_tools) <= self.max_prompt_tools:
            return set(self.allowed_tools)
        groups = self._select_capability_groups(request, context)
        candidates = {
            tool_name
            for tool_name in self.allowed_tools
            if str(self.tool_catalog.get(tool_name, {}).get("capability_group", "core")) in groups
        }
        candidates.update(name for name in _FOUNDATIONAL_PLANNING_TOOLS if name in self.allowed_tools)
        if not candidates:
            raise PlanValidationError("The model did not select any capability groups with executable tools.")
        if len(candidates) > self.max_prompt_tools:
            candidates = self._select_exact_tools(request, context, candidates)
        return candidates

    def _select_capability_groups(self, request: str, context: dict[str, Any]) -> set[str]:
        group_catalog = self._group_catalog_for_prompt()
        group_names = sorted(group_catalog)
        if not group_names:
            raise PlanValidationError("No capability groups are available for model planning.")
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["groups", "reason"],
            "properties": {
                "groups": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": self.max_candidate_groups,
                    "items": {"type": "string", "enum": group_names},
                },
                "reason": {"type": "string", "minLength": 1},
            },
        }
        prompt = render_prompt_template(
            "select_capability_groups",
            group_catalog=json.dumps(group_catalog, sort_keys=True, separators=(",", ":")),
            runtime_summary=json.dumps(_selector_context_for_prompt(context), sort_keys=True, default=str, separators=(",", ":")),
            user_request=request,
        )
        raw = self.model_client.complete_json(prompt, schema)
        try:
            return _parse_selection(raw, field_name="groups", allowed=set(group_catalog), label="Capability group selector")
        except PlanValidationError as exc:
            repaired = self._repair_selection(
                raw_selection=raw,
                error=str(exc),
                schema=schema,
                field_name="groups",
                allowed_values=group_names,
                label="capability groups",
            )
            return _parse_selection(repaired, field_name="groups", allowed=set(group_catalog), label="Capability group selector")

    def _select_exact_tools(self, request: str, context: dict[str, Any], candidates: set[str]) -> set[str]:
        candidate_names = sorted(name for name in candidates if name in self.allowed_tools)
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["tools", "reason"],
            "properties": {
                "tools": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": self.max_prompt_tools,
                    "items": {"type": "string", "enum": candidate_names},
                },
                "reason": {"type": "string", "minLength": 1},
            },
        }
        prompt = render_prompt_template(
            "select_exact_tools",
            candidate_tool_catalog=json.dumps(self._catalog_for_prompt(set(candidate_names)), sort_keys=True, separators=(",", ":")),
            runtime_summary=json.dumps(_selector_context_for_prompt(context), sort_keys=True, default=str, separators=(",", ":")),
            user_request=request,
        )
        raw = self.model_client.complete_json(prompt, schema)
        try:
            tools = _parse_selection(raw, field_name="tools", allowed=candidates, label="Tool selector")
        except PlanValidationError as exc:
            repaired = self._repair_selection(
                raw_selection=raw,
                error=str(exc),
                schema=schema,
                field_name="tools",
                allowed_values=candidate_names,
                label="tools",
            )
            tools = _parse_selection(repaired, field_name="tools", allowed=candidates, label="Tool selector")
        tools.update(name for name in _FOUNDATIONAL_PLANNING_TOOLS if name in self.allowed_tools)
        if not tools:
            raise PlanValidationError("Tool selector returned no known tools.")
        return tools

    def _repair_selection(
        self,
        *,
        raw_selection: str,
        error: str,
        schema: dict[str, Any],
        field_name: str,
        allowed_values: list[str],
        label: str,
    ) -> str:
        prompt = render_prompt_template(
            "repair_selection",
            label=label,
            field_name=field_name,
            allowed_values=json.dumps(allowed_values, separators=(",", ":")),
            error=error,
            raw_selection=raw_selection[:4000],
        )
        return self.model_client.complete_json(prompt, schema)

    def _repair_plan(self, request: str, context: dict[str, Any], parser: StructuredPlanParser, *, plan_schema: dict[str, Any], raw_plan: str, error: str) -> str:
        del context
        prompt = render_prompt_template(
            "repair_tool_plan",
            allowed_tool_names=json.dumps(sorted(parser.allowed_tools), separators=(",", ":")),
            allowed_tool_contracts=json.dumps(self._catalog_for_prompt(set(parser.allowed_tools)), sort_keys=True, separators=(",", ":")),
            user_request=request,
            error=error,
            raw_plan=raw_plan[:4000],
        )
        return self.model_client.complete_json(prompt, plan_schema)

    def _repair_tool_input_plan(self, request: str, parser: StructuredPlanParser, *, raw_plan: str, error: str) -> str:
        try:
            document = json.loads(raw_plan)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Could not repair tool input because the plan was not JSON: {exc}") from exc
        steps = document.get("steps") if isinstance(document, dict) else None
        if not isinstance(steps, list) or not steps or not isinstance(steps[0], dict):
            raise PlanValidationError("Could not repair tool input because the plan did not include an object step.")
        tool_name = str(step_tool_name(steps[0]) or "")
        if tool_name not in parser.allowed_tools:
            raise PlanValidationError(f"Could not repair tool input for unknown tool: {tool_name}")
        input_schema = self.tool_catalog.get(tool_name, {}).get("input_schema")
        if not isinstance(input_schema, dict):
            raise PlanValidationError(f"Could not repair tool input because {tool_name} has no input schema.")
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["tool_input", "reason"],
            "properties": {
                "tool_input": input_schema,
                "reason": {"type": "string", "minLength": 1},
            },
        }
        tool_details = self.tool_catalog.get(tool_name, {})
        prompt = render_prompt_template(
            "repair_tool_input",
            tool_name=tool_name,
            tool_description=tool_details.get("description", ""),
            tool_input_schema=json.dumps(input_schema, sort_keys=True, separators=(",", ":")),
            user_request=request,
            error=error,
            raw_plan=raw_plan[:4000],
        )
        raw_repair = self.model_client.complete_json(prompt, schema)
        try:
            repaired = json.loads(raw_repair)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Tool input repair must return valid JSON: {exc}") from exc
        if not isinstance(repaired, dict):
            raise PlanValidationError("Tool input repair must return a JSON object.")
        tool_input = repaired.get("tool_input")
        reason = str(repaired.get("reason") or steps[0].get("reason") or "Model-repaired tool input.").strip()
        if not isinstance(tool_input, dict):
            raise PlanValidationError("Tool input repair returned invalid tool_input.")
        return json.dumps(
            {
                "steps": [
                    {
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "reason": reason or "Model-repaired tool input.",
                    }
                ]
            },
            ensure_ascii=False,
        )

    def _render_tool_review_prompt(
        self,
        template_name: str,
        *,
        parser: StructuredPlanParser,
        context: dict[str, Any],
        request: str,
        **values: object,
    ) -> str:
        return render_prompt_template(
            template_name,
            allowed_tool_names=json.dumps(sorted(parser.allowed_tools), separators=(",", ":")),
            allowed_tool_contracts=json.dumps(self._catalog_for_prompt(set(parser.allowed_tools)), sort_keys=True, separators=(",", ":")),
            runtime_context=json.dumps(_context_for_prompt(context), sort_keys=True, default=str, separators=(",", ":")),
            user_request=request,
            **values,
        )

    def _build_prompt(self, request: str, context: dict[str, Any], candidate_tools: set[str] | None = None) -> str:
        candidate_tools = candidate_tools or set(self.allowed_tools)
        catalog = self._catalog_for_prompt(candidate_tools)
        runtime_context = _context_for_prompt(context)
        return render_prompt_template(
            "structured_plan",
            selected_count=len(catalog),
            total_count=len(self.allowed_tools),
            allowed_tool_catalog=json.dumps(catalog, sort_keys=True, separators=(",", ":")),
            runtime_context=json.dumps(runtime_context, sort_keys=True, default=str, separators=(",", ":")),
            user_request=request,
        )

    def _build_react_prompt(self, request: str, context: dict[str, Any], candidate_tools: set[str]) -> str:
        catalog = self._catalog_for_prompt(candidate_tools)
        runtime_context = _context_for_prompt(context)
        return render_prompt_template(
            "react_turn",
            selected_count=len(catalog),
            total_count=len(self.allowed_tools),
            allowed_tool_catalog=json.dumps(catalog, sort_keys=True, separators=(",", ":")),
            runtime_context=json.dumps(runtime_context, sort_keys=True, default=str, separators=(",", ":")),
            user_request=request,
        )

    def _catalog_for_prompt(self, tool_names: set[str] | None = None) -> dict[str, dict[str, Any]]:
        catalog: dict[str, dict[str, Any]] = {}
        selected_names = tool_names if tool_names is not None else self.allowed_tools
        for tool_name in sorted(selected_names):
            details = self.tool_catalog.get(tool_name, {})
            signature = _schema_signature(details.get("input_schema", {"type": "object", "properties": {}}))
            catalog[tool_name] = {
                "d": str(details.get("description", ""))[:48],
                "g": details.get("capability_group", "core"),
                "r": details.get("risk_level", "unknown"),
                "approval": bool(details.get("requires_approval", False)),
                "req": signature["required"],
                "fields": signature["fields"],
            }
        return catalog

    def _group_catalog_for_prompt(self) -> dict[str, dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for tool_name in sorted(self.allowed_tools):
            details = self.tool_catalog.get(tool_name, {})
            group_name = str(details.get("capability_group", "core"))
            group = groups.setdefault(
                group_name,
                {
                    "tool_count": 0,
                    "approval_required": 0,
                    "risk_levels": {},
                    "sample_tools": [],
                    "sample_descriptions": [],
                },
            )
            group["tool_count"] += 1
            if details.get("requires_approval"):
                group["approval_required"] += 1
            risk = str(details.get("risk_level", "unknown"))
            group["risk_levels"][risk] = group["risk_levels"].get(risk, 0) + 1
            if len(group["sample_tools"]) < 12:
                group["sample_tools"].append(tool_name)
            description = str(details.get("description", "")).strip()
            if description and len(group["sample_descriptions"]) < 4:
                group["sample_descriptions"].append(description[:120])
        return groups


def _schema_signature(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    fields: dict[str, str] = {}
    required = list(schema.get("required", []))[:8] if isinstance(schema.get("required"), list) else []
    if isinstance(properties, dict):
        selected_names = required or list(properties.keys())[:3]
        for name in selected_names[:8]:
            details = properties.get(name)
            if isinstance(details, dict):
                fields[name] = _property_signature(details)
        omitted = max(0, len(properties) - len(fields))
        if omitted:
            fields["optional_omitted"] = str(omitted)
    return {
        "required": required,
        "fields": fields,
    }


def _property_signature(details: dict[str, Any]) -> str:
    value_type = str(details.get("type", "any"))
    if isinstance(details.get("enum"), list) and details["enum"]:
        enum_values = "|".join(str(item) for item in details["enum"][:5])
        return f"{value_type} enum:{enum_values}"
    if value_type == "array" and isinstance(details.get("items"), dict):
        return f"array[{details['items'].get('type', 'any')}]"
    return value_type


def _parse_selection(raw: str, *, field_name: str, allowed: set[str], label: str) -> set[str]:
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanValidationError(f"{label} must return valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise PlanValidationError(f"{label} must return a JSON object.")
    selected = document.get(field_name)
    if not isinstance(selected, list):
        raise PlanValidationError(f"{label} must include `{field_name}` as an array.")
    values = {str(item) for item in selected if str(item) in allowed}
    if not values:
        raise PlanValidationError(f"{label} returned no known {field_name}.")
    return values


def _context_has_live_browser_session(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("live_session_id"):
            return True
        return any(_context_has_live_browser_session(item) for item in value.values())
    if isinstance(value, list):
        return any(_context_has_live_browser_session(item) for item in value)
    if isinstance(value, str):
        return "live_session_id:" in value
    return False


def _context_has_tool_observation(value: Any, tool_names: set[str]) -> bool:
    if isinstance(value, dict):
        tool_name = value.get("tool_name")
        if isinstance(tool_name, str) and tool_name in tool_names:
            return True
        return any(_context_has_tool_observation(item, tool_names) for item in value.values())
    if isinstance(value, list):
        return any(_context_has_tool_observation(item, tool_names) for item in value)
    return False


def _context_observed_urls(value: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"url", "current_url", "resolved_url", "href"} and isinstance(item, str):
                normalized = _normalize_observed_url(item)
                if normalized:
                    urls.add(normalized)
            else:
                urls.update(_context_observed_urls(item))
    elif isinstance(value, list):
        for item in value:
            urls.update(_context_observed_urls(item))
    elif isinstance(value, str):
        for raw_url in re.findall(r"https?://[^\s\"'<>),]+", value):
            normalized = _normalize_observed_url(raw_url)
            if normalized:
                urls.add(normalized)
    return urls


def _url_is_from_observations(proposed_url: str, observed_urls: set[str]) -> bool:
    normalized = _normalize_observed_url(proposed_url)
    if not normalized:
        return False
    if normalized in observed_urls:
        return True
    proposed = urlparse(normalized)
    for observed_url in observed_urls:
        observed = urlparse(observed_url)
        if proposed.netloc != observed.netloc:
            continue
        proposed_path = proposed.path.rstrip("/")
        observed_path = observed.path.rstrip("/")
        if proposed_path and observed_path and (proposed_path.startswith(observed_path) or observed_path.startswith(proposed_path)):
            return True
    return False


def _normalize_observed_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(fragment="", path=path).geturl()


def _validate_planned_tool_input(value: Any, schema: dict[str, Any], path: str = "tool_input") -> None:
    expected_type = schema.get("type")
    if expected_type == "object" or isinstance(value, dict):
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object.")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required", [])
        if not isinstance(required, list):
            required = []
        for key in required:
            if key not in value:
                raise ValueError(f"{path}.{key} is required.")
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                _validate_planned_tool_input(item, properties[key], f"{path}.{key}")
            elif additional is False:
                allowed = ", ".join(sorted(properties)) or "none"
                raise ValueError(f"{path}.{key} is not allowed. Allowed fields: {allowed}.")
        return
    if expected_type == "array" or isinstance(value, list):
        if not isinstance(value, list):
            raise ValueError(f"{path} must be an array.")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_planned_tool_input(item, item_schema, f"{path}[{index}]")
        return
    if expected_type == "string" and not isinstance(value, str):
        raise ValueError(f"{path} must be a string.")
    if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ValueError(f"{path} must be an integer.")
    if expected_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        raise ValueError(f"{path} must be a number.")
    if expected_type in {"integer", "number"} and isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            raise ValueError(f"{path} must be at least {minimum}.")
        if isinstance(maximum, (int, float)) and value > maximum:
            raise ValueError(f"{path} must be at most {maximum}.")
    if expected_type == "boolean" and not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean.")
    allowed_values = schema.get("enum")
    if isinstance(allowed_values, list) and value not in allowed_values:
        allowed = ", ".join(str(item) for item in allowed_values)
        raise ValueError(f"{path} must be one of: {allowed}.")


def _context_for_prompt(context: dict[str, Any]) -> dict[str, Any]:
    compact = dict(context)
    if isinstance(compact.get("recent_memory"), list):
        compact["recent_memory"] = [_compact_context_item(item) for item in compact["recent_memory"][:3]]
    if isinstance(compact.get("browser_sessions"), list):
        compact["browser_sessions"] = compact["browser_sessions"][:3]
    if isinstance(compact.get("available_workspace_skills"), list):
        compact["available_workspace_skills"] = [
            _compact_context_item(item) for item in compact["available_workspace_skills"][:8]
        ]
    if isinstance(compact.get("capability_plugins"), list):
        compact["capability_plugins"] = [
            _compact_context_item(item) for item in compact["capability_plugins"][:12]
        ]
    if isinstance(compact.get("gateway_channels"), list):
        compact["gateway_channels"] = [
            _compact_context_item(item) for item in compact["gateway_channels"][:12]
        ]
    if isinstance(compact.get("screen_captures"), dict):
        captures = dict(compact["screen_captures"])
        if isinstance(captures.get("latest"), list):
            captures["latest"] = captures["latest"][:2]
        compact["screen_captures"] = captures
    if isinstance(compact.get("cognition"), dict):
        compact["cognition"] = _compact_cognition(compact["cognition"])
    return compact


def _selector_context_for_prompt(context: dict[str, Any]) -> dict[str, Any]:
    compact = _context_for_prompt(context)
    return {
        "workspace": compact.get("workspace"),
        "system": compact.get("system"),
        "active_window": compact.get("active_window"),
        "browser_sessions": compact.get("browser_sessions", []),
        "screen_captures": compact.get("screen_captures", {}),
        "activity_policy": compact.get("activity_policy", {}),
        "cognition": {
            key: value
            for key, value in (compact.get("cognition", {}) if isinstance(compact.get("cognition"), dict) else {}).items()
            if key in {"active_goals", "active_tasks", "focus", "skills", "specialists"}
        },
    }


def _compact_cognition(cognition: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in cognition.items():
        if isinstance(value, list):
            compact[key] = {
                "count": len(value),
                "items": [_compact_context_item(item) for item in value[:3]],
            }
        else:
            compact[key] = _compact_context_item(value)
    return compact


def _compact_context_item(item: Any) -> Any:
    if isinstance(item, dict):
        compact: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, (dict, list)):
                continue
            text = str(value)
            compact[key] = text[:240] if len(text) > 240 else value
            if len(compact) >= 10:
                break
        return compact
    if isinstance(item, str):
        return item[:240]
    return item
