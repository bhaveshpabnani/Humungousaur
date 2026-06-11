from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.interaction import InteractionHarness, harness_result_to_dict
from humungousaur.memory.event_store import EventStore
from humungousaur.planning.model_clients import ModelClient
from humungousaur.planning.model_factory import build_model_client

from .activity_guides import select_activity_guides
from .models import (
    JanusActivation,
    JanusDecision,
    JanusEpisode,
    JanusMemoryCandidate,
    JanusRoute,
    Confidence,
    DeepDiveRequest,
    MutedScopeMode,
    ReflexPosture,
    RouteClass,
    TaskContext,
    new_id,
)
from .redaction import safe_compact_mapping
from .reflex_interpreter import ReflexInterpreter
from .store import JanusStore


REFLEX_STIMULI = {
    "system_started",
    "user_logged_in",
    "screen_unlocked",
    "wake_started",
    "external_display_connected",
    "workspace_switched",
    "focus_mode_enabled",
    "meeting_joined",
    "meeting_left",
    "wake_word_detected",
    "global_hotkey_pressed",
    "explicit_assistant_opened",
    "user_returned_after_gap",
    "new_work_session_started",
}

TRIAGE_COLLECTORS = {
    "mail_activity",
    "mail_composition_activity",
    "mail_organization_activity",
    "calendar_activity",
    "calendar_scheduling_activity",
    "channel_activity",
    "communication_activity",
    "chat_thread_activity",
    "meeting_artifact_activity",
    "github_activity",
    "code_hosting_activity",
    "issue_tracker_activity",
    "task_manager_activity",
    "incident_activity",
    "support_desk_activity",
}

TRIAGE_STIMULI = {
    "email_received",
    "calendar_invite_received",
    "file_shared",
    "cloud_file_shared",
    "issue_assigned",
    "issue_comment_received",
    "pull_request_review_requested",
    "review_requested",
    "ci_failed",
    "build_failed",
    "test_suite_failed",
    "incident_declared",
    "on_call_alert_received",
    "meeting_transcript_available",
    "meeting_action_items_detected",
    "ticket_escalated",
    "sla_breach_warning",
}

BLOCKED_STIMULI = {
    "otp_code_detected",
    "verification_code_prompt_shown",
    "backup_code_prompt_shown",
    "credential_selected",
    "credential_copied",
    "credential_filled",
    "password_manager_opened",
    "payment_prompt_shown",
    "secret_view_attempted",
}

RICH_PRIVACY_TIERS = {"rich_capture"}

BRIDGE_POSTURES = {
    ReflexPosture.SUMMARIZE,
    ReflexPosture.PREPARE,
    ReflexPosture.ASK_USER,
    ReflexPosture.WAKE_MAIN_AGENT,
    ReflexPosture.REQUEST_DEEP_DIVE,
}


class JanusEventRouter:
    """Routes accepted collector events into janus interpretation."""

    def __init__(
        self,
        config: AgentConfig,
        *,
        store: JanusStore | None = None,
        model_client: ModelClient | None = None,
        run_agent: bool = True,
    ) -> None:
        self.config = config.normalized()
        self.store = store or JanusStore(self.config.janus_db_path)
        self.interpreter = ReflexInterpreter(model_client or _build_reflex_model_client(self.config))
        self.run_agent = run_agent

    def handle_event(self, event: dict[str, Any]) -> dict[str, Any]:
        muted_scope = self.store.active_muted_scope_for(event)
        route = self._route_event(event, muted_scope=muted_scope)
        if _scope_blocks_storage(muted_scope):
            return {
                "route": {
                    "route_class": RouteClass.BLOCKED.value,
                    "reason": "Matched active do-not-track scope; event details were not persisted.",
                },
                "decision": None,
                "submission": None,
                "suppressed": True,
            }
        self.store.record_route(route)
        result: dict[str, Any] = {"route": asdict(route), "decision": None, "submission": None}

        if route.route_class == RouteClass.CONTEXT:
            context_result = self.store.record_context_event(event)
            result["context_window"] = context_result
            boundary = self.store.detect_context_boundary(context_result)
            if boundary is not None:
                boundary_route = self._boundary_route(route, event, boundary)
                self.store.record_route(boundary_route)
                result["boundary"] = boundary
                result["boundary_route"] = asdict(boundary_route)
                decision = self._interpret_and_record(boundary_route, event, boundary=boundary)
                result["decision"] = asdict(decision)
                result["resume_capsule"] = self.store.record_resume_capsule(boundary, decision)
                result["explanation"] = self.store.record_explanation(
                    route=boundary_route,
                    event=event,
                    explanation_type="context_boundary",
                    summary=_decision_explanation_summary(decision, boundary_route, boundary=boundary),
                    decision=decision,
                    boundary=boundary,
                )
                submission = self._maybe_wake_agent(decision, boundary_route, event)
                if submission:
                    result["submission"] = submission
            else:
                result["explanation"] = self.store.record_explanation(
                    route=route,
                    event=event,
                    explanation_type="context_observed",
                    summary="Observed as ongoing context and kept quiet until a meaningful boundary appears.",
                    details={"context_windows_updated": len(context_result.get("windows", [])) if isinstance(context_result, dict) else 0},
                )
            return result
        if route.route_class in {RouteClass.BLOCKED, RouteClass.MUTED}:
            result["explanation"] = self.store.record_explanation(
                route=route,
                event=event,
                explanation_type=route.route_class.value,
                summary=route.reason,
                details={"muted_or_blocked": True},
            )
            return result

        decision = self._interpret_and_record(route, event)
        result["decision"] = asdict(decision)
        result["explanation"] = self.store.record_explanation(
            route=route,
            event=event,
            explanation_type="reflex_decision",
            summary=_decision_explanation_summary(decision, route),
            decision=decision,
        )
        submission = self._maybe_wake_agent(decision, route, event)
        if submission:
            result["submission"] = submission
        return result

    def _interpret_and_record(
        self,
        route: JanusRoute,
        event: dict[str, Any],
        *,
        boundary: dict[str, Any] | None = None,
    ) -> JanusDecision:
        context_window = self.store.context_bundle(limit=8)
        task_contexts = self.store.task_contexts(limit=8)
        policy = _policy_for_event(event, route=route, boundary=boundary)
        decision = self.interpreter.interpret(
            route=route,
            event=event,
            context_window=context_window,
            task_contexts=task_contexts,
            muted_scopes=self.store.muted_scopes(limit=8),
            active_episodes=self.store.episodes(limit=8),
            active_episode_events=self.store.episode_events(limit=16),
            activity_guides=select_activity_guides(
                route=route,
                event=event,
                context_window=context_window,
                task_contexts=task_contexts,
            ),
            policy=policy,
            corrections=self.store.corrections(limit=8),
            deep_dive_requests=self.store.deep_dive_requests(limit=8),
        )
        decision = self._apply_policy(decision, event, policy=policy)
        self.store.record_decision(decision)
        self._apply_decision_updates(decision, event)
        return decision

    def _boundary_route(self, route: JanusRoute, event: dict[str, Any], boundary: dict[str, Any]) -> JanusRoute:
        return JanusRoute(
            route_id=new_id("route"),
            event_sequence=int(event.get("sequence") or route.event_sequence),
            event_id=str(event.get("event_id") or route.event_id),
            collector=route.collector,
            source="active_context",
            stimulus_type=str(boundary.get("boundary_type") or "context_boundary"),
            privacy_tier=route.privacy_tier,
            route_class=RouteClass.REFLEX,
            reason=f"Context boundary detected: {boundary.get('reason', '')}",
        )

    def _route_event(self, event: dict[str, Any], *, muted_scope: object | None) -> JanusRoute:
        stimulus_type = str(event.get("stimulus_type") or "")
        collector = str(event.get("collector") or "")
        privacy_tier = str(event.get("privacy_tier") or "")
        if muted_scope is not None:
            mode = getattr(muted_scope, "mode", MutedScopeMode.NO_ASSISTANCE)
            route_class = RouteClass.BLOCKED if mode == MutedScopeMode.DO_NOT_TRACK else RouteClass.MUTED
            reason = f"Matched active muted scope: {getattr(mode, 'value', str(mode))}"
        elif privacy_tier in RICH_PRIVACY_TIERS or stimulus_type in BLOCKED_STIMULI:
            route_class = RouteClass.BLOCKED
            reason = "Sensitive or rich-capture event cannot enter janus interpretation without explicit deep-dive approval."
        elif stimulus_type in REFLEX_STIMULI:
            route_class = RouteClass.REFLEX
            reason = "Reflex state-change event."
        elif collector in TRIAGE_COLLECTORS or stimulus_type in TRIAGE_STIMULI:
            route_class = RouteClass.TRIAGE
            reason = "Incoming or externally meaningful event requires model-led triage."
        else:
            route_class = RouteClass.CONTEXT
            reason = "Ongoing work context event; accumulated into rolling context window."
        return JanusRoute(
            route_id=new_id("route"),
            event_sequence=int(event.get("sequence") or 0),
            event_id=str(event.get("event_id") or ""),
            collector=collector,
            source=str(event.get("source") or ""),
            stimulus_type=stimulus_type,
            privacy_tier=privacy_tier,
            route_class=route_class,
            reason=reason,
        )

    def _apply_policy(self, decision: JanusDecision, event: dict[str, Any], *, policy: dict[str, Any]) -> JanusDecision:
        if str(event.get("privacy_tier") or "") in RICH_PRIVACY_TIERS:
            decision.posture = ReflexPosture.STAY_SILENT
            decision.should_interrupt_user = False
            decision.agent_stimulus = ""
            decision.user_visible_text = ""
            decision.safety_notes.append("Rich-capture event blocked by hard policy.")
            return decision
        if decision.deep_dive_request and not bool(decision.deep_dive_request.get("requires_user_approval", True)):
            decision.deep_dive_request["requires_user_approval"] = True
            decision.safety_notes.append("Deep-dive request forced to require approval.")
        if decision.posture == ReflexPosture.REQUEST_DEEP_DIVE and not _valid_deep_dive_request(decision.deep_dive_request):
            decision.posture = ReflexPosture.REMEMBER
            decision.should_interrupt_user = False
            decision.agent_stimulus = ""
            decision.user_visible_text = ""
            decision.safety_notes.append("Deep-dive posture downgraded because no valid approval request was supplied.")
        if decision.posture == ReflexPosture.ASK_USER and not bool(policy.get("can_interrupt_now", False)):
            decision.posture = ReflexPosture.PREPARE if decision.agent_stimulus or decision.user_visible_text else ReflexPosture.REMEMBER
            decision.should_interrupt_user = False
            decision.safety_notes.append("Ask-user posture downgraded because interruption is not allowed at this boundary.")
        if decision.posture == ReflexPosture.WAKE_MAIN_AGENT and not decision.agent_stimulus:
            if decision.user_visible_text and bool(policy.get("can_interrupt_now", False)):
                decision.posture = ReflexPosture.ASK_USER
                decision.should_interrupt_user = True
                decision.safety_notes.append("Agent wake downgraded to ask_user because no safe agent stimulus was supplied.")
            elif decision.user_visible_text:
                decision.posture = ReflexPosture.PREPARE
                decision.should_interrupt_user = False
                decision.agent_stimulus = decision.user_visible_text
                decision.safety_notes.append("Agent wake downgraded to prepare because no safe agent stimulus was supplied.")
            else:
                decision.posture = ReflexPosture.REMEMBER
                decision.should_interrupt_user = False
                decision.safety_notes.append("Agent wake downgraded because no safe stimulus text was supplied.")
        return decision

    def _apply_decision_updates(self, decision: JanusDecision, event: dict[str, Any]) -> None:
        episode_id = self._apply_episode_update(decision, event)
        for update in decision.task_context_updates[:8]:
            summary = str(update.get("summary") or update.get("goal") or "").strip()
            if not summary:
                continue
            update_episode_id = str(update.get("episode_id") or episode_id or "")
            self.store.upsert_task_context(
                TaskContext(
                    task_context_id=str(update.get("task_context_id") or new_id("ctx")),
                    status=str(update.get("status") or "active"),
                    source=str(update.get("source") or "model"),
                    user_declared_goal=str(update.get("user_declared_goal") or update.get("goal") or ""),
                    episode_id=update_episode_id,
                    primary_entities=_safe_dict_list(update.get("primary_entities")),
                    supporting_entities=_safe_dict_list(update.get("supporting_entities")),
                    assistant_mode=_clean_text(update.get("assistant_mode") or "supportive", limit=120),
                    allowed_help=_clean_text_list(update.get("allowed_help"), limit=120),
                    privacy_mode=_clean_text(update.get("privacy_mode") or "metadata_first", limit=120),
                    summary=summary[:1_000],
                    evidence_refs=[
                        f"collector_event:{int(event.get('sequence') or 0)}",
                        f"reflex_decision:{decision.decision_id}",
                        *_clean_text_list(update.get("evidence_refs"), limit=200),
                    ][:20],
                )
            )
        if decision.posture == ReflexPosture.REQUEST_DEEP_DIVE and decision.deep_dive_request:
            request = decision.deep_dive_request
            request_id = str(request.get("request_id") or new_id("deep"))
            self.store.record_deep_dive_request(
                DeepDiveRequest(
                    request_id=request_id,
                    episode_id=str(request.get("episode_id") or episode_id or ""),
                    requested_by="reflex_llm",
                    purpose=str(request.get("purpose") or decision.reason)[:1_000],
                    source=str(request.get("source") or event.get("source") or ""),
                    requested_access=str(request.get("requested_access") or ""),
                    privacy_tier=str(request.get("privacy_tier") or "rich_capture"),
                    requires_user_approval=True,
                    evidence_refs=[f"collector_event:{int(event.get('sequence') or 0)}", f"reflex_decision:{decision.decision_id}"],
                )
            )
            request["request_id"] = request_id
        self._record_memory_candidates(decision, event)

    def _apply_episode_update(self, decision: JanusDecision, event: dict[str, Any]) -> str:
        update = decision.episode_update if isinstance(decision.episode_update, dict) else {}
        action = _clean_text(update.get("action"), limit=120)
        if not update or action == "observe_only":
            return ""
        summary = _clean_text(update.get("summary"), limit=1_000)
        hypothesis = _clean_text(update.get("hypothesis") or summary, limit=1_000)
        if not summary and not hypothesis:
            return ""
        episode_id = _clean_text(update.get("episode_id") or new_id("episode"), limit=160)
        status = _episode_status(action, _clean_text(update.get("status"), limit=80))
        confidence = _confidence(update.get("confidence"))
        evidence_refs = [
            f"collector_event:{int(event.get('sequence') or 0)}",
            f"route:{decision.route_id}",
            f"reflex_decision:{decision.decision_id}",
            *_clean_text_list(update.get("evidence_refs"), limit=240),
        ][:30]
        episode = JanusEpisode(
            episode_id=episode_id,
            status=status,
            source="reflex_llm",
            hypothesis=hypothesis,
            summary=summary or hypothesis,
            confidence=confidence,
            primary_entities=_safe_dict_list(update.get("primary_entities")),
            supporting_entities=_safe_dict_list(update.get("supporting_entities")),
            task_context_id=_clean_text(update.get("task_context_id"), limit=160),
            correction_refs=_clean_text_list(update.get("correction_refs"), limit=240),
            deep_dive_refs=_clean_text_list(update.get("deep_dive_refs"), limit=240),
            evidence_refs=evidence_refs,
            last_event_sequence=int(event.get("sequence") or decision.event_sequence),
        )
        self.store.upsert_episode(episode)
        self.store.record_episode_event(
            episode_id=episode_id,
            event=event,
            relation=action,
            route_id=decision.route_id,
            decision_id=decision.decision_id,
            evidence={
                "action": action,
                "status": status,
                "confidence": confidence.value,
                "reason": _clean_text(update.get("reason") or decision.reason, limit=1_000),
                "evidence_refs": evidence_refs,
                "raw_content_included": False,
            },
        )
        return episode_id

    def _record_memory_candidates(self, decision: JanusDecision, event: dict[str, Any]) -> None:
        if not decision.memory_updates:
            return
        memory_store = EventStore(self.config.memory_db_path)
        for update in decision.memory_updates[:8]:
            candidate = _memory_candidate_for(decision, event, update)
            if candidate is None:
                continue
            self.store.record_memory_candidate(candidate)
            memory_store.append(
                "janus_memory_candidate",
                {
                    "candidate_id": candidate.candidate_id,
                    "decision_id": candidate.decision_id,
                    "route_id": candidate.route_id,
                    "event_sequence": candidate.event_sequence,
                    "kind": candidate.kind,
                    "summary": candidate.summary,
                    "importance": candidate.importance,
                    "status": candidate.status,
                    "payload": candidate.payload,
                    "evidence_refs": candidate.evidence_refs,
                    "privacy_note": "Generated from Reflex LLM safe context; raw collector payloads are not included.",
                },
            )

    def _maybe_wake_agent(self, decision: JanusDecision, route: JanusRoute, event: dict[str, Any]) -> dict[str, Any] | None:
        if decision.posture not in BRIDGE_POSTURES:
            return None
        activation = self._activation_for(decision, route, event)
        self.store.record_activation(activation)
        if decision.posture != ReflexPosture.WAKE_MAIN_AGENT:
            return {"activation": self.store.activations(limit=1)[0]}
        if not self.run_agent:
            updated = self.store.update_activation_status(
                activation.activation_id,
                status="skipped",
                reason="Agent bridge execution is disabled for this runtime.",
            )
            return {"activation": updated or asdict(activation), "skipped": True, "reason": "agent bridge disabled"}
        text = decision.agent_stimulus
        if not text:
            return None
        stimulus = {
            "text": text,
            "source": "activity",
            "stimulus_id": activation.stimulus_id,
            "occurred_at": route.created_at,
            "metadata": {
                "janus": True,
                "route_id": route.route_id,
                "decision_id": decision.decision_id,
                "activation_id": activation.activation_id,
                "posture": decision.posture.value,
                "collector_event_sequence": route.event_sequence,
                "should_run_agent": True,
                "requires_response": activation.response_mode != "silent",
                "response_mode": activation.response_mode,
                "evidence_refs": activation.evidence_refs,
                "allowed_actions": activation.allowed_actions,
                "forbidden_actions": activation.forbidden_actions,
                "evidence": {
                    "collector": route.collector,
                    "source": route.source,
                    "stimulus_type": route.stimulus_type,
                    "event_id": route.event_id,
                },
            },
        }
        try:
            harness = InteractionHarness(self.config).handle(stimulus, response_mode=activation.response_mode)
            harness_result = harness_result_to_dict(harness)
            updated = self.store.update_activation_status(
                activation.activation_id,
                status="submitted",
                harness_result=harness_result,
                reason=decision.reason,
            )
            return {"activation": updated or asdict(activation), "harness": harness_result}
        except Exception as exc:
            error_result = {"error": type(exc).__name__, "message": str(exc)[:500]}
            updated = self.store.update_activation_status(
                activation.activation_id,
                status="failed",
                harness_result=error_result,
                reason=f"Agent bridge submission failed: {type(exc).__name__}",
            )
            return {"activation": updated or asdict(activation), "error": error_result}

    def _activation_for(self, decision: JanusDecision, route: JanusRoute, event: dict[str, Any]) -> JanusActivation:
        response_mode = "text" if decision.posture == ReflexPosture.ASK_USER else "silent"
        status = "pending" if decision.posture == ReflexPosture.WAKE_MAIN_AGENT else "prepared"
        evidence_refs = [
            f"collector_event:{int(event.get('sequence') or route.event_sequence)}",
            f"route:{route.route_id}",
            f"reflex_decision:{decision.decision_id}",
        ]
        if decision.deep_dive_request:
            request_id = str(decision.deep_dive_request.get("request_id") or "")
            if request_id:
                evidence_refs.append(f"deep_dive_request:{request_id}")
        return JanusActivation(
            activation_id=new_id("act"),
            decision_id=decision.decision_id,
            route_id=route.route_id,
            event_sequence=route.event_sequence,
            posture=decision.posture,
            status=status,
            response_mode=response_mode,
            stimulus_id=f"janus-{decision.decision_id}",
            user_visible_text=decision.user_visible_text[:1_000],
            agent_stimulus=decision.agent_stimulus[:4_000],
            reason=decision.reason[:1_000],
            should_interrupt_user=bool(decision.should_interrupt_user and decision.posture == ReflexPosture.ASK_USER),
            allowed_actions=_allowed_actions_for(decision.posture),
            forbidden_actions=_forbidden_actions_for(decision.posture),
            evidence_refs=evidence_refs,
        )


def _policy_for_event(event: dict[str, Any], *, route: JanusRoute, boundary: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "route_class": route.route_class.value,
        "privacy_tier": route.privacy_tier,
        "rich_capture_allowed": False,
        "can_interrupt_now": route.route_class in {RouteClass.REFLEX, RouteClass.TRIAGE}
        and not (boundary and boundary.get("boundary_type") == "stable_context"),
        "allowed_outputs": [item.value for item in ReflexPosture],
        "blocked_if_private_or_secret": True,
        "boundary": boundary or {},
        "event": {
            "collector": str(event.get("collector") or ""),
            "source": str(event.get("source") or ""),
            "stimulus_type": str(event.get("stimulus_type") or ""),
        },
    }


def _build_reflex_model_client(config: AgentConfig) -> ModelClient | None:
    if config.planner_provider != "model":
        return None
    reflex_config = _reflex_model_config(config)
    try:
        return build_model_client(reflex_config)
    except Exception:
        return None


def _reflex_model_config(config: AgentConfig) -> AgentConfig:
    provider = str(config.janus_model_provider or "").strip()
    if not provider or provider == "same-as-main":
        return config
    return replace(
        config,
        model_provider=provider,
        model_name=str(config.janus_model_name or "").strip() or config.model_name,
        model_base_url=config.janus_model_base_url or config.model_base_url,
        model_api_key_env=config.janus_model_api_key_env or config.model_api_key_env,
    ).normalized()


def _decision_explanation_summary(
    decision: JanusDecision,
    route: JanusRoute,
    *,
    boundary: dict[str, Any] | None = None,
) -> str:
    prefix = f"{decision.posture.value} with {decision.confidence.value} confidence"
    if boundary is not None:
        return f"{prefix} after {boundary.get('boundary_type', 'context boundary')}: {decision.reason or route.reason}"
    return f"{prefix}: {decision.reason or route.reason}"


def _allowed_actions_for(posture: ReflexPosture) -> list[str]:
    if posture == ReflexPosture.ASK_USER:
        return ["ask_user_only", "show_janus_card"]
    if posture == ReflexPosture.WAKE_MAIN_AGENT:
        return ["prepare_draft", "prepare_checklist", "summarize_safe_context", "update_cognitive_focus", "queue_approval"]
    if posture == ReflexPosture.REQUEST_DEEP_DIVE:
        return ["queue_deep_dive_approval", "show_janus_card"]
    return ["prepare_silent_help", "summarize_safe_context", "show_janus_card"]


def _forbidden_actions_for(posture: ReflexPosture) -> list[str]:
    common = [
        "read_rich_content_without_approval",
        "send_message_without_approval",
        "modify_files_without_approval",
        "run_destructive_tool_without_approval",
        "bypass_muted_scope",
    ]
    if posture == ReflexPosture.ASK_USER:
        return [*common, "continue_without_user_answer"]
    if posture == ReflexPosture.REQUEST_DEEP_DIVE:
        return [*common, "perform_deep_dive_without_approval"]
    return common


def _valid_deep_dive_request(request: dict[str, Any] | None) -> bool:
    if not isinstance(request, dict):
        return False
    return bool(str(request.get("purpose") or "").strip() and str(request.get("source") or "").strip() and str(request.get("requested_access") or "").strip())


def _episode_status(action: str, requested_status: str) -> str:
    requested = requested_status if requested_status in {"active", "paused", "waiting", "completed", "abandoned"} else ""
    if requested:
        return requested
    if action in {"pause_episode"}:
        return "paused"
    if action in {"complete_episode"}:
        return "completed"
    if action in {"abandon_episode"}:
        return "abandoned"
    return "active"


def _confidence(value: object) -> Confidence:
    try:
        return Confidence(str(value or Confidence.LOW.value))
    except ValueError:
        return Confidence.LOW


def _scope_blocks_storage(scope: object | None) -> bool:
    if scope is None:
        return False
    mode = getattr(scope, "mode", "")
    mode_value = getattr(mode, "value", str(mode))
    return bool(getattr(scope, "do_not_store", False) or mode_value == MutedScopeMode.DO_NOT_TRACK.value)


def _memory_candidate_for(
    decision: JanusDecision,
    event: dict[str, Any],
    update: dict[str, Any],
) -> JanusMemoryCandidate | None:
    if not isinstance(update, dict):
        return None
    summary = _clean_text(update.get("summary") or update.get("text") or update.get("note"), limit=1_000)
    if not summary:
        return None
    event_sequence = int(event.get("sequence") or decision.event_sequence)
    return JanusMemoryCandidate(
        candidate_id=str(update.get("candidate_id") or new_id("mem")),
        decision_id=decision.decision_id,
        route_id=decision.route_id,
        event_sequence=event_sequence,
        kind=_clean_text(update.get("kind") or update.get("type") or "working_context", limit=120),
        summary=summary,
        importance=_clean_text(update.get("importance") or "normal", limit=80),
        status="candidate",
        payload=_safe_memory_payload(update),
        evidence_refs=[
            f"collector_event:{event_sequence}",
            f"route:{decision.route_id}",
            f"reflex_decision:{decision.decision_id}",
        ],
    )


def _safe_memory_payload(update: dict[str, Any]) -> dict[str, Any]:
    payload = safe_compact_mapping(update)
    payload.pop("status", None)
    payload.pop("candidate_id", None)
    payload["raw_content_included"] = False
    return payload


def _clean_text(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").split())[: max(1, int(limit))]


def _clean_text_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value[:20]:
        text = _clean_text(item, limit=limit)
        if text:
            cleaned.append(text)
    return cleaned


def _safe_dict_list(value: object, *, limit: int = 12) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_drop_redacted_fields(safe_compact_mapping(item)) for item in value[:limit] if isinstance(item, dict)]


def _drop_redacted_fields(value: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if item == "[redacted]":
            continue
        if isinstance(item, dict):
            nested = _drop_redacted_fields(item)
            if nested:
                cleaned[key] = nested
            continue
        if isinstance(item, list):
            nested_list = [_drop_redacted_fields(child) if isinstance(child, dict) else child for child in item]
            nested_list = [child for child in nested_list if child not in ("[redacted]", {}, [])]
            if nested_list:
                cleaned[key] = nested_list
            continue
        cleaned[key] = item
    return cleaned
