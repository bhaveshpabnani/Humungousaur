from __future__ import annotations

from dataclasses import asdict
from contextlib import closing
from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.cognition.focus import FocusStore
from humungousaur.cognition.models import FocusMode
from humungousaur.interaction import InteractionHarness, harness_result_to_dict
from humungousaur.memory.event_store import EventStore

from .deep_dive import execute_approved_deep_dive
from .models import ActivationResponse, ActiveEpisode, Confidence, DeepDiveRequest, MutedScope, MutedScopeMode, TaskContext, new_id
from .memory_promotion import promote_memory_candidate, retract_promoted_memory_candidate
from .store import ActiveAgentStore


CORRECTION_TYPES = {
    "wrong_task",
    "not_relevant",
    "helpful",
    "private",
    "not_now",
    "do_not_track",
    "no_assistance",
}


def active_agent_status(config: AgentConfig, *, limit: int = 20) -> dict[str, Any]:
    normalized = config.normalized()
    status = ActiveAgentStore(normalized.active_agent_db_path).status(limit=limit)
    active_provider = normalized.active_model_provider or "same-as-main"
    active_model_name = normalized.active_model_name or normalized.model_name
    status["reflex_model"] = {
        "planner_provider": normalized.planner_provider,
        "main_model_provider": normalized.model_provider,
        "main_model_name": normalized.model_name,
        "active_model_provider": active_provider,
        "active_model_name": active_model_name,
        "effective_model_provider": normalized.model_provider if active_provider == "same-as-main" else active_provider,
        "effective_model_name": active_model_name,
        "local_provider_supported": (normalized.model_provider if active_provider == "same-as-main" else active_provider)
        in {"auto", "ollama", "local-openai"},
        "note": "Active-agent reflex interpretation uses active_model_* when configured; otherwise it uses the main agent model.",
    }
    return status


def declare_task_context(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    store = ActiveAgentStore(normalized.active_agent_db_path)
    context = TaskContext(
        task_context_id=str(payload.get("task_context_id") or new_id("ctx")),
        status=str(payload.get("status") or "active"),
        source=str(payload.get("source") or "user_declared"),
        user_declared_goal=_clean(payload.get("user_declared_goal") or payload.get("goal"), limit=1_000),
        episode_id=_clean(payload.get("episode_id"), limit=160),
        primary_entities=_list_of_dicts(payload.get("primary_entities")),
        supporting_entities=_list_of_dicts(payload.get("supporting_entities")),
        assistant_mode=_clean(payload.get("assistant_mode") or "supportive", limit=120),
        allowed_help=[_clean(item, limit=120) for item in _list(payload.get("allowed_help")) if _clean(item, limit=120)],
        privacy_mode=_clean(payload.get("privacy_mode") or "metadata_first", limit=120),
        summary=_clean(payload.get("summary") or payload.get("user_declared_goal") or payload.get("goal"), limit=1_000),
        evidence_refs=[_clean(item, limit=200) for item in _list(payload.get("evidence_refs")) if _clean(item, limit=200)],
    )
    if not context.user_declared_goal and not context.summary:
        raise ValueError("user_declared_goal or summary is required")
    stored = store.upsert_task_context(context)
    focus = _project_task_context_to_focus(normalized, stored)
    return {"task_context": asdict(stored), "focus": focus, "status": store.status(limit=10)}


def create_muted_scope(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    mode = MutedScopeMode(str(payload.get("mode") or MutedScopeMode.NO_ASSISTANCE.value))
    scope = MutedScope(
        scope_id=str(payload.get("scope_id") or new_id("mute")),
        mode=mode,
        scope_type=_clean(payload.get("scope_type") or "manual", limit=120),
        entity_refs=[_clean(item, limit=240) for item in _list(payload.get("entity_refs")) if _clean(item, limit=240)],
        collector=_clean(payload.get("collector"), limit=120),
        source=_clean(payload.get("source"), limit=120),
        stimulus_type=_clean(payload.get("stimulus_type"), limit=120),
        expires_at=_clean(payload.get("expires_at"), limit=160),
        do_not_interrupt=bool(payload.get("do_not_interrupt", True)),
        do_not_deep_dive=bool(payload.get("do_not_deep_dive", True)),
        do_not_send_to_llm=bool(payload.get("do_not_send_to_llm", True)),
        do_not_store=bool(payload.get("do_not_store", mode == MutedScopeMode.DO_NOT_TRACK)),
        reason=_clean(payload.get("reason") or "User muted active-agent assistance for this scope.", limit=1_000),
    )
    if not (scope.entity_refs or scope.collector or scope.source or scope.stimulus_type):
        raise ValueError("muted scope requires entity_refs, collector, source, or stimulus_type")
    store = ActiveAgentStore(normalized.active_agent_db_path)
    stored = store.create_muted_scope(scope)
    return {"muted_scope": asdict(stored), "status": store.status(limit=10)}


def cancel_muted_scope(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    scope_id = _clean(payload.get("scope_id") or payload.get("id"), limit=160)
    if not scope_id:
        raise ValueError("scope_id is required")
    store = ActiveAgentStore(normalized.active_agent_db_path)
    updated = store.cancel_muted_scope(scope_id, reason=_clean(payload.get("reason"), limit=500))
    if updated is None:
        raise ValueError(f"muted scope not found: {scope_id}")
    return {"muted_scope": updated, "status": store.status(limit=10)}


def record_user_correction(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    correction_type = _clean(payload.get("correction_type") or payload.get("type"), limit=80)
    if correction_type not in CORRECTION_TYPES:
        raise ValueError(f"unsupported correction_type: {correction_type or '<empty>'}")
    target_type = _clean(payload.get("target_type") or "active_agent", limit=120)
    target_id = _clean(payload.get("target_id") or payload.get("id"), limit=200)
    if not target_id:
        raise ValueError("target_id is required")
    note = _clean(payload.get("note") or payload.get("reason"), limit=1_000)
    evidence_refs = [_clean(item, limit=240) for item in _list(payload.get("evidence_refs")) if _clean(item, limit=240)]
    evidence_refs.append(f"{target_type}:{target_id}")
    store = ActiveAgentStore(normalized.active_agent_db_path)
    task_context_id = ""
    muted_scope_id = ""
    memory_candidate: dict[str, Any] | None = None
    promoted_memory: dict[str, Any] | None = None
    retracted_memories: list[dict[str, Any]] = []
    cascaded_memory_candidates: list[dict[str, Any]] = []
    cascaded_activations: list[dict[str, Any]] = []
    task_payload = payload.get("task_context") if isinstance(payload.get("task_context"), dict) else {}
    goal = _clean(
        task_payload.get("goal") or task_payload.get("user_declared_goal") or payload.get("goal") or payload.get("user_declared_goal"),
        limit=1_000,
    )
    summary = _clean(task_payload.get("summary") or payload.get("summary") or goal, limit=1_000)
    if correction_type == "wrong_task" and (goal or summary):
        context = TaskContext(
            task_context_id=_clean(task_payload.get("task_context_id") or payload.get("task_context_id") or new_id("ctx"), limit=160),
            status="active",
            source="user_correction",
            user_declared_goal=goal,
            episode_id=_clean(task_payload.get("episode_id") or payload.get("episode_id"), limit=160),
            assistant_mode=_clean(task_payload.get("assistant_mode") or payload.get("assistant_mode") or "supportive", limit=120),
            allowed_help=[_clean(item, limit=120) for item in _list(task_payload.get("allowed_help") or payload.get("allowed_help")) if _clean(item, limit=120)],
            privacy_mode=_clean(task_payload.get("privacy_mode") or payload.get("privacy_mode") or "metadata_first", limit=120),
            summary=summary,
            evidence_refs=evidence_refs,
        )
        stored_context = store.upsert_task_context(context)
        _project_task_context_to_focus(normalized, stored_context)
        task_context_id = stored_context.task_context_id
    if correction_type in {"private", "not_now", "do_not_track", "no_assistance"}:
        mode = {
            "private": MutedScopeMode.PRIVATE,
            "not_now": MutedScopeMode.NOT_NOW,
            "do_not_track": MutedScopeMode.DO_NOT_TRACK,
            "no_assistance": MutedScopeMode.NO_ASSISTANCE,
        }[correction_type]
        scope = MutedScope(
            scope_id=_clean(payload.get("scope_id") or new_id("mute"), limit=160),
            mode=mode,
            scope_type=_clean(payload.get("scope_type") or "user_correction", limit=120),
            entity_refs=[_clean(item, limit=240) for item in _list(payload.get("entity_refs")) if _clean(item, limit=240)],
            collector=_clean(payload.get("collector"), limit=120),
            source=_clean(payload.get("source"), limit=120),
            stimulus_type=_clean(payload.get("stimulus_type"), limit=120),
            expires_at=_clean(payload.get("expires_at"), limit=160),
            do_not_store=bool(payload.get("do_not_store", mode in {MutedScopeMode.DO_NOT_TRACK, MutedScopeMode.PRIVATE})),
            reason=note or f"User correction marked target as {correction_type}.",
        )
        if scope.entity_refs or scope.collector or scope.source or scope.stimulus_type:
            stored_scope = store.create_muted_scope(scope)
            muted_scope_id = stored_scope.scope_id
    if target_type in {"memory_candidate", "active_memory_candidate"}:
        next_status = {
            "helpful": "accepted",
            "not_relevant": "rejected",
            "wrong_task": "rejected",
            "private": "private",
            "do_not_track": "private",
            "no_assistance": "archived",
            "not_now": "archived",
        }.get(correction_type)
        if next_status:
            memory_candidate = store.update_memory_candidate_status(target_id, status=next_status, reason=note or correction_type)
            if memory_candidate is not None:
                if next_status == "accepted":
                    promoted_memory = promote_memory_candidate(normalized, store, target_id, reason=note or correction_type)
                    if promoted_memory is not None:
                        memory_candidate = promoted_memory.get("candidate") or memory_candidate
                elif next_status in {"private", "rejected", "archived"}:
                    retracted = retract_promoted_memory_candidate(normalized, store, target_id, reason=note or correction_type)
                    if retracted is not None:
                        retracted_memories.append(retracted)
                EventStore(normalized.memory_db_path).append(
                    "active_agent_memory_candidate_status",
                    {
                        "candidate_id": memory_candidate["candidate_id"],
                        "status": memory_candidate["status"],
                        "correction_type": correction_type,
                        "target_id": target_id,
                        "promoted_knowledge_id": memory_candidate.get("promoted_knowledge_id", ""),
                        "summary": memory_candidate.get("summary", ""),
                        "evidence_refs": memory_candidate.get("evidence_refs", []),
                        "privacy_note": "Memory candidate status update only; raw collector payloads are not included.",
                    },
                )
    cascade_decision_id = _cascade_decision_id(store, target_type=target_type, target_id=target_id)
    if cascade_decision_id and correction_type == "helpful" and target_type not in {"memory_candidate", "active_memory_candidate"}:
        for candidate in store.memory_candidates_for_decision(cascade_decision_id):
            if candidate.get("status") in {"private", "rejected", "archived"}:
                continue
            updated_candidate = candidate
            if candidate.get("status") != "accepted":
                updated_candidate = store.update_memory_candidate_status(
                    str(candidate.get("candidate_id") or ""),
                    status="accepted",
                    reason=note or correction_type,
                ) or candidate
            promoted = promote_memory_candidate(
                normalized,
                store,
                str(updated_candidate.get("candidate_id") or ""),
                reason=note or correction_type,
            )
            if promoted is not None:
                updated_candidate = promoted.get("candidate") or updated_candidate
                if promoted_memory is None:
                    promoted_memory = promoted
            cascaded_memory_candidates.append(updated_candidate)
            EventStore(normalized.memory_db_path).append(
                "active_agent_memory_candidate_status",
                {
                    "candidate_id": updated_candidate.get("candidate_id", ""),
                    "status": updated_candidate.get("status", ""),
                    "correction_type": correction_type,
                    "target_id": target_id,
                    "promoted_knowledge_id": updated_candidate.get("promoted_knowledge_id", ""),
                    "summary": updated_candidate.get("summary", ""),
                    "evidence_refs": updated_candidate.get("evidence_refs", []),
                    "privacy_note": "Helpful feedback accepted related memory candidates; raw collector payloads are not included.",
                },
            )
    if cascade_decision_id and correction_type in {"private", "do_not_track", "no_assistance", "not_now", "not_relevant", "wrong_task"}:
        memory_status = "private" if correction_type in {"private", "do_not_track"} else "archived"
        if correction_type in {"not_relevant", "wrong_task"}:
            memory_status = "rejected"
        for candidate in store.memory_candidates_for_decision(cascade_decision_id):
            if candidate.get("status") == memory_status:
                continue
            updated_candidate = store.update_memory_candidate_status(
                str(candidate.get("candidate_id") or ""),
                status=memory_status,
                reason=note or correction_type,
            )
            if updated_candidate is not None:
                retracted = retract_promoted_memory_candidate(
                    normalized,
                    store,
                    str(updated_candidate.get("candidate_id") or ""),
                    reason=note or correction_type,
                )
                if retracted is not None:
                    retracted_memories.append(retracted)
                cascaded_memory_candidates.append(updated_candidate)
        if correction_type in {"private", "do_not_track", "no_assistance", "not_now", "not_relevant", "wrong_task"}:
            for activation in store.activations_for_decision(cascade_decision_id):
                if activation.get("status") not in {"prepared", "pending"}:
                    continue
                updated_activation = store.update_activation_status(
                    str(activation.get("activation_id") or ""),
                    status="skipped",
                    reason=f"Skipped after user correction: {note or correction_type}",
                )
                if updated_activation is not None:
                    cascaded_activations.append(updated_activation)
        if cascaded_memory_candidates or cascaded_activations:
            EventStore(normalized.memory_db_path).append(
                "active_agent_correction_cascade",
                {
                    "target_type": target_type,
                    "target_id": target_id,
                    "decision_id": cascade_decision_id,
                    "correction_type": correction_type,
                    "memory_candidate_ids": [item.get("candidate_id", "") for item in cascaded_memory_candidates],
                    "activation_ids": [item.get("activation_id", "") for item in cascaded_activations],
                    "privacy_note": "Correction cascade contains ids and statuses only; raw collector payloads are not included.",
                },
            )
    correction = store.record_correction(
        correction_id=_clean(payload.get("correction_id") or new_id("corr"), limit=160),
        correction_type=correction_type,
        target_type=target_type,
        target_id=target_id,
        note=note,
        task_context_id=task_context_id,
        muted_scope_id=muted_scope_id,
        evidence_refs=evidence_refs,
    )
    return {
        "correction": correction,
        "memory_candidate": memory_candidate,
        "promoted_memory": promoted_memory,
        "retracted_memories": retracted_memories,
        "cascaded_memory_candidates": cascaded_memory_candidates,
        "cascaded_activations": cascaded_activations,
        "status": store.status(limit=10),
    }


def create_deep_dive_request(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    request = DeepDiveRequest(
        request_id=str(payload.get("request_id") or new_id("deep")),
        episode_id=_clean(payload.get("episode_id"), limit=160),
        requested_by=_clean(payload.get("requested_by") or "user", limit=120),
        purpose=_clean(payload.get("purpose"), limit=1_000),
        source=_clean(payload.get("source"), limit=120),
        requested_access=_clean(payload.get("requested_access"), limit=240),
        privacy_tier=_clean(payload.get("privacy_tier") or "rich_capture", limit=120),
        requires_user_approval=bool(payload.get("requires_user_approval", True)),
        status=_clean(payload.get("status") or "needs_approval", limit=120),
        evidence_refs=[_clean(item, limit=200) for item in _list(payload.get("evidence_refs")) if _clean(item, limit=200)],
    )
    if not request.purpose or not request.source or not request.requested_access:
        raise ValueError("purpose, source, and requested_access are required")
    store = ActiveAgentStore(normalized.active_agent_db_path)
    stored = store.record_deep_dive_request(request)
    return {"deep_dive_request": asdict(stored), "status": store.status(limit=10)}


def approve_deep_dive_request(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    return update_deep_dive_request(config, payload, status="approved")


def reject_deep_dive_request(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    return update_deep_dive_request(config, payload, status="rejected")


def update_deep_dive_request(config: AgentConfig, payload: dict[str, Any], *, status: str | None = None) -> dict[str, Any]:
    normalized = config.normalized()
    request_id = _clean(payload.get("request_id") or payload.get("id"), limit=160)
    next_status = _clean(status or payload.get("status"), limit=80)
    if not request_id:
        raise ValueError("request_id is required")
    if not next_status:
        raise ValueError("status is required")
    store = ActiveAgentStore(normalized.active_agent_db_path)
    updated = store.update_deep_dive_status(
        request_id,
        status=next_status,
        reason=_clean(payload.get("reason"), limit=500),
    )
    if updated is None:
        raise ValueError(f"deep-dive request not found: {request_id}")
    return {"deep_dive_request": updated, "status": store.status(limit=10)}


def execute_deep_dive_request(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    request_id = _clean(payload.get("request_id") or payload.get("id"), limit=160)
    if not request_id:
        raise ValueError("request_id is required")
    return execute_approved_deep_dive(
        config,
        request_id,
        limit=max(1, min(int(payload.get("limit") or 40), 100)),
    )


def apply_episode_operation(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    store = ActiveAgentStore(normalized.active_agent_db_path)
    operation = _clean(payload.get("operation") or payload.get("action"), limit=80)
    episode_id = _clean(payload.get("episode_id"), limit=160)
    reason = _clean(payload.get("reason"), limit=1_000)
    evidence_refs = [_clean(item, limit=240) for item in _list(payload.get("evidence_refs")) if _clean(item, limit=240)]
    if operation not in {"pause", "resume", "complete", "abandon", "merge", "split"}:
        raise ValueError(f"unsupported episode operation: {operation or '<empty>'}")
    if not episode_id:
        raise ValueError("episode_id is required")
    current = store.episode(episode_id)
    if current is None:
        raise ValueError(f"episode not found: {episode_id}")
    result: dict[str, Any] = {"operation": operation}
    if operation in {"pause", "resume", "complete", "abandon"}:
        status = {"pause": "paused", "resume": "active", "complete": "completed", "abandon": "abandoned"}[operation]
        updated = store.update_episode_status(episode_id, status=status, reason=reason, evidence_refs=evidence_refs)
        result["episode"] = updated
    elif operation == "merge":
        target_episode_id = _clean(payload.get("target_episode_id"), limit=160)
        if not target_episode_id:
            raise ValueError("target_episode_id is required for merge")
        if store.episode(target_episode_id) is None:
            raise ValueError(f"target episode not found: {target_episode_id}")
        link = store.record_episode_link(
            source_episode_id=episode_id,
            target_episode_id=target_episode_id,
            relation="merged_into",
            reason=reason or "User/model merged related active-agent episodes.",
            evidence_refs=[*evidence_refs, f"episode:{episode_id}", f"episode:{target_episode_id}"],
        )
        updated = store.update_episode_status(
            episode_id,
            status="merged",
            reason=reason or f"Merged into {target_episode_id}.",
            evidence_refs=[*evidence_refs, f"episode_link:{link['link_id']}"],
        )
        result.update({"episode": updated, "episode_link": link})
    elif operation == "split":
        new_episode_id = _clean(payload.get("new_episode_id") or new_id("episode"), limit=160)
        summary = _clean(payload.get("summary") or current.get("summary") or "Split active-agent episode.", limit=1_000)
        hypothesis = _clean(payload.get("hypothesis") or summary, limit=1_000)
        refs = [*evidence_refs, f"episode:{episode_id}"]
        new_episode = store.upsert_episode(
            ActiveEpisode(
                episode_id=new_episode_id,
                status="active",
                source="episode_operation",
                hypothesis=hypothesis,
                summary=summary,
                confidence=Confidence.MEDIUM,
                primary_entities=_list_of_dicts(payload.get("primary_entities")) or current.get("primary_entities", []),
                supporting_entities=_list_of_dicts(payload.get("supporting_entities")),
                task_context_id=_clean(payload.get("task_context_id"), limit=160),
                evidence_refs=refs,
            )
        )
        link = store.record_episode_link(
            source_episode_id=episode_id,
            target_episode_id=new_episode_id,
            relation="split_into",
            reason=reason or "Split a separate activity episode from an existing episode.",
            evidence_refs=refs,
        )
        store.update_episode_status(episode_id, status="split", reason=reason or f"Split into {new_episode_id}.", evidence_refs=[f"episode_link:{link['link_id']}"])
        result.update({"episode": store.episode(episode_id), "new_episode": asdict(new_episode), "episode_link": link})
    result["status"] = store.status(limit=10)
    return result


def respond_to_activation(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    store = ActiveAgentStore(normalized.active_agent_db_path)
    activation_id = _clean(payload.get("activation_id") or payload.get("id"), limit=160)
    response_type = _clean(payload.get("response_type") or payload.get("type"), limit=80)
    text = _clean(payload.get("text") or payload.get("message") or payload.get("note"), limit=2_000)
    if response_type not in {"accept", "decline", "not_now", "private", "clarify", "wake_agent"}:
        raise ValueError(f"unsupported response_type: {response_type or '<empty>'}")
    activation = store.activation(activation_id)
    if activation is None:
        raise ValueError(f"activation not found: {activation_id}")
    evidence_refs = [f"activation:{activation_id}"]
    action_taken = "recorded"
    task_context_id = ""
    muted_scope_id = ""
    harness_result: dict[str, Any] = {}
    if response_type in {"decline", "not_now", "private"}:
        correction_type = "no_assistance" if response_type == "decline" else response_type
        correction_payload = record_user_correction(
            normalized,
            {
                "correction_type": correction_type,
                "target_type": "activation",
                "target_id": activation_id,
                "note": text or correction_type,
                "collector": payload.get("collector", ""),
                "source": payload.get("source", ""),
                "stimulus_type": payload.get("stimulus_type", ""),
                "entity_refs": payload.get("entity_refs", []),
            },
        )
        muted_scope_id = str((correction_payload.get("correction") or {}).get("muted_scope_id") or "")
        store.update_activation_status(activation_id, status="skipped", reason=text or correction_type)
        action_taken = correction_type
    if response_type in {"accept", "clarify", "wake_agent"}:
        goal = _clean(payload.get("goal") or text, limit=1_000)
        if goal:
            task = declare_task_context(
                normalized,
                {
                    "goal": goal,
                    "summary": _clean(payload.get("summary") or goal, limit=1_000),
                    "episode_id": payload.get("episode_id") or _episode_id_from_activation(activation),
                    "source": "activation_response",
                    "allowed_help": payload.get("allowed_help", ["resume_capsule", "prepare_draft", "answer_question"]),
                    "privacy_mode": payload.get("privacy_mode", "metadata_first"),
                    "evidence_refs": evidence_refs,
                },
            )
            task_context_id = str((task.get("task_context") or {}).get("task_context_id") or "")
        if response_type == "wake_agent" or bool(payload.get("run_agent", False)):
            stimulus = {
                "text": text or activation.get("agent_stimulus") or activation.get("user_visible_text") or "User accepted active-agent help.",
                "source": "active_agent_activation_response",
                "metadata": {
                    "activation_id": activation_id,
                    "task_context_id": task_context_id,
                    "evidence_refs": evidence_refs,
                },
            }
            harness = InteractionHarness(normalized).handle(
                stimulus,
                response_mode=str(payload.get("response_mode") or activation.get("response_mode") or "text"),
                approve_high_risk=bool(payload.get("approve_high_risk", False)),
            )
            harness_result = harness_result_to_dict(harness)
            store.update_activation_status(activation_id, status="submitted", harness_result=harness_result, reason=text or "User accepted active-agent help.")
            action_taken = "woke_agent"
        else:
            store.update_activation_status(activation_id, status="prepared", reason=text or "User accepted active-agent help.")
            action_taken = "accepted"
    response = store.record_activation_response(
        ActivationResponse(
            response_id=_clean(payload.get("response_id") or new_id("response"), limit=160),
            activation_id=activation_id,
            response_type=response_type,
            text=text,
            action_taken=action_taken,
            task_context_id=task_context_id,
            muted_scope_id=muted_scope_id,
            harness_result=harness_result,
            evidence_refs=evidence_refs,
        )
    )
    return {"activation_response": asdict(response), "status": store.status(limit=10)}


def active_agent_privacy_export(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    store = ActiveAgentStore(normalized.active_agent_db_path)
    limit = max(1, min(int(payload.get("limit") or 100), 500))
    scope = _privacy_scope(payload)
    status = store.status(limit=limit)
    export = {key: _filter_records(value, scope) if isinstance(value, list) else value for key, value in status.items()}
    export["privacy_export"] = {
        "scope": scope,
        "raw_collector_payloads_included": False,
        "note": "Export contains active-agent summaries, state records, ids, and evidence refs from active_agent.sqlite3 only.",
    }
    action = store.record_privacy_action(
        action_id=new_id("privacy"),
        action_type="export",
        scope=scope,
        affected_counts={key: len(value) for key, value in export.items() if isinstance(value, list)},
        status="completed",
        reason=_clean(payload.get("reason") or "User requested active-agent export.", limit=500),
    )
    export["privacy_action"] = action
    return export


def active_agent_privacy_delete(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    store = ActiveAgentStore(normalized.active_agent_db_path)
    scope = _privacy_scope(payload)
    counts = _delete_privacy_scope(store, scope)
    action = store.record_privacy_action(
        action_id=new_id("privacy"),
        action_type="delete",
        scope=scope,
        affected_counts=counts,
        status="completed",
        reason=_clean(payload.get("reason") or "User requested active-agent scoped deletion.", limit=500),
    )
    return {"privacy_action": action, "status": store.status(limit=10)}


def run_active_agent_eval(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = config.normalized()
    store = ActiveAgentStore(normalized.active_agent_db_path)
    scenario = _clean(payload.get("scenario") or "status_replay", limit=160)
    status = store.status(limit=max(20, min(int(payload.get("limit") or 100), 500)))
    failures: list[dict[str, Any]] = []
    metrics = {
        "episodes": len(status.get("episodes", [])),
        "decisions": len(status.get("decisions", [])),
        "activations": len(status.get("activations", [])),
        "deep_dive_requests": len(status.get("deep_dive_requests", [])),
        "memory_candidates": len(status.get("memory_candidates", [])),
    }
    for decision in status.get("decisions", []):
        posture = str(decision.get("posture") or "")
        if posture in {"ask_user", "wake_main_agent", "request_deep_dive"} and not decision.get("safety_notes"):
            failures.append({"kind": "missing_safety_notes", "decision_id": decision.get("decision_id", ""), "posture": posture})
    for request in status.get("deep_dive_requests", []):
        if not bool(request.get("requires_user_approval", True)):
            failures.append({"kind": "deep_dive_without_approval", "request_id": request.get("request_id", "")})
    for episode in status.get("episodes", []):
        if str(episode.get("status") or "") == "active" and not episode.get("summary"):
            failures.append({"kind": "episode_missing_summary", "episode_id": episode.get("episode_id", "")})
    eval_run = store.record_eval_run(
        eval_id=_clean(payload.get("eval_id") or new_id("eval"), limit=160),
        scenario=scenario,
        status="failed" if failures else "passed",
        summary=f"Active-agent replay eval {scenario} checked {metrics['decisions']} decision(s), {metrics['episodes']} episode(s), and {metrics['deep_dive_requests']} deep-dive request(s).",
        metrics=metrics,
        failures=failures,
    )
    return {"eval_run": eval_run, "status": store.status(limit=10)}


def _project_task_context_to_focus(config: AgentConfig, context: TaskContext) -> dict[str, Any]:
    store = FocusStore(config.cognition_db_path)
    current = store.load()
    summary = context.summary or context.user_declared_goal
    pinned_context = [
        item
        for item in [
            f"Active task: {summary}" if summary else "",
            f"Task source: {context.source}" if context.source else "",
            f"Privacy mode: {context.privacy_mode}" if context.privacy_mode else "",
            f"Allowed help: {', '.join(context.allowed_help)}" if context.allowed_help else "",
        ]
        if item
    ][:8]
    metadata = {
        **current.metadata,
        "active_agent_task_context_id": context.task_context_id,
        "active_agent_episode_id": context.episode_id,
        "active_agent_source": context.source,
        "active_agent_assistant_mode": context.assistant_mode,
        "active_agent_privacy_mode": context.privacy_mode,
        "active_agent_allowed_help": context.allowed_help,
        "active_agent_evidence_refs": context.evidence_refs,
        "active_agent_primary_entities": context.primary_entities[:10],
        "active_agent_supporting_entities": context.supporting_entities[:10],
    }
    focus = store.update(
        mode=FocusMode.MONITORING,
        active_task_id=context.task_context_id,
        summary=summary,
        pinned_context=pinned_context,
        metadata=metadata,
    )
    return asdict(focus)


def _episode_id_from_activation(activation: dict[str, Any]) -> str:
    for ref in activation.get("evidence_refs", []):
        text = str(ref or "")
        if text.startswith("episode:"):
            return text.split(":", 1)[1]
    return ""


def _privacy_scope(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "target_type": _clean(payload.get("target_type"), limit=120),
        "target_id": _clean(payload.get("target_id") or payload.get("id"), limit=200),
        "episode_id": _clean(payload.get("episode_id"), limit=160),
        "collector": _clean(payload.get("collector"), limit=120),
        "source": _clean(payload.get("source"), limit=120),
        "entity_ref": _clean(payload.get("entity_ref"), limit=240),
    }


def _filter_records(records: list[Any], scope: dict[str, str]) -> list[Any]:
    if not any(scope.values()):
        return records
    return [record for record in records if isinstance(record, dict) and _record_matches_scope(record, scope)]


def _record_matches_scope(record: dict[str, Any], scope: dict[str, str]) -> bool:
    target_type = scope.get("target_type", "")
    target_id = scope.get("target_id", "")
    if target_id and target_id not in {
        str(record.get("id") or ""),
        str(record.get("activation_id") or ""),
        str(record.get("candidate_id") or ""),
        str(record.get("decision_id") or ""),
        str(record.get("episode_id") or ""),
        str(record.get("request_id") or ""),
        str(record.get("route_id") or ""),
        str(record.get("scope_id") or ""),
        str(record.get("task_context_id") or ""),
    }:
        return False
    if target_type and target_id and not _target_type_matches(record, target_type):
        return False
    for key in ("episode_id", "collector", "source"):
        if scope.get(key) and str(record.get(key) or "") != scope[key]:
            return False
    entity_ref = scope.get("entity_ref", "")
    if entity_ref:
        refs = record.get("entity_refs") or record.get("primary_entities") or record.get("supporting_entities") or []
        if entity_ref not in str(refs):
            return False
    return True


def _target_type_matches(record: dict[str, Any], target_type: str) -> bool:
    markers = {
        "activation": "activation_id",
        "decision": "decision_id",
        "episode": "episode_id",
        "memory_candidate": "candidate_id",
        "deep_dive_request": "request_id",
        "route": "route_id",
        "task_context": "task_context_id",
        "muted_scope": "scope_id",
    }
    marker = markers.get(target_type)
    return not marker or bool(record.get(marker))


def _delete_privacy_scope(store: ActiveAgentStore, scope: dict[str, str]) -> dict[str, int]:
    if not any(scope.values()):
        raise ValueError("privacy delete requires at least one scope field")
    counts: dict[str, int] = {}
    tables = {
        "active_agent_activations": ["activation_id", "decision_id", "route_id"],
        "active_reflex_decisions": ["decision_id", "route_id"],
        "active_memory_candidates": ["candidate_id", "decision_id", "route_id"],
        "active_task_contexts": ["task_context_id", "episode_id"],
        "active_episodes": ["episode_id"],
        "active_episode_events": ["episode_id", "event_id", "route_id", "decision_id"],
        "active_deep_dive_requests": ["request_id", "episode_id", "source"],
        "active_deep_dive_results": ["request_id", "episode_id"],
        "active_activation_responses": ["activation_id"],
        "active_corrections": ["target_id", "task_context_id", "muted_scope_id"],
        "active_muted_scopes": ["scope_id", "collector", "source", "stimulus_type"],
        "active_event_routes": ["route_id", "collector", "source", "stimulus_type"],
    }
    target_id = scope.get("target_id", "")
    target_type = scope.get("target_type", "")
    with closing(store._connect()) as connection:  # Internal scoped deletion helper; keep SQL constrained and explicit.
        for table, columns in tables.items():
            clauses: list[str] = []
            values: list[str] = []
            if target_id:
                clauses.append("(" + " OR ".join(f"{column} = ?" for column in columns) + ")")
                values.extend([target_id] * len(columns))
            for key in ("episode_id", "collector", "source"):
                if scope.get(key) and key in columns:
                    clauses.append(f"{key} = ?")
                    values.append(scope[key])
            if target_type and target_id and not clauses:
                continue
            if not clauses:
                continue
            cursor = connection.execute(f"DELETE FROM {table} WHERE {' AND '.join(clauses)}", tuple(values))
            counts[table] = int(cursor.rowcount or 0)
        connection.commit()
    return counts


def _cascade_decision_id(store: ActiveAgentStore, *, target_type: str, target_id: str) -> str:
    if target_type == "decision":
        return target_id
    if target_type == "activation":
        activation = store.activation(target_id)
        return str((activation or {}).get("decision_id") or "")
    if target_type in {"memory_candidate", "active_memory_candidate"}:
        candidate = store.memory_candidate(target_id)
        return str((candidate or {}).get("decision_id") or "")
    return ""


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)][:50]
