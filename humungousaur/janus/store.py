from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .entities import extract_entity_refs
from .models import (
    JanusActivation,
    JanusDecision,
    JanusEpisode,
    JanusMemoryCandidate,
    JanusRoute,
    ActivationResponse,
    DeepDiveRequest,
    DeepDiveResult,
    MutedScope,
    TaskContext,
    utc_now,
)


class JanusStore:
    """Durable local state for collector-to-agent reflex interpretation."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_event_routes (
                    route_id TEXT PRIMARY KEY,
                    event_sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    collector TEXT NOT NULL,
                    source TEXT NOT NULL,
                    stimulus_type TEXT NOT NULL,
                    privacy_tier TEXT NOT NULL,
                    route_class TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_event_routes_sequence ON active_event_routes(event_sequence)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_event_routes_class ON active_event_routes(route_class, created_at)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_reflex_decisions (
                    decision_id TEXT PRIMARY KEY,
                    route_id TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    posture TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    should_interrupt_user INTEGER NOT NULL,
                    user_visible_text TEXT NOT NULL,
                    agent_stimulus TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    task_context_updates_json TEXT NOT NULL,
                    memory_updates_json TEXT NOT NULL,
                    safety_notes_json TEXT NOT NULL,
                    deep_dive_request_json TEXT NOT NULL,
                    model_status TEXT NOT NULL,
                    raw_output_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_reflex_decisions_sequence ON active_reflex_decisions(event_sequence)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS janus_activations (
                    activation_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    posture TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_mode TEXT NOT NULL,
                    stimulus_id TEXT NOT NULL,
                    user_visible_text TEXT NOT NULL,
                    agent_stimulus TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    should_interrupt_user INTEGER NOT NULL,
                    allowed_actions_json TEXT NOT NULL DEFAULT '[]',
                    forbidden_actions_json TEXT NOT NULL DEFAULT '[]',
                    harness_result_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_janus_activations_sequence ON janus_activations(event_sequence)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_janus_activations_status ON janus_activations(status, updated_at)"
            )
            _ensure_column(connection, "janus_activations", "allowed_actions_json", "TEXT NOT NULL DEFAULT '[]'")
            _ensure_column(connection, "janus_activations", "forbidden_actions_json", "TEXT NOT NULL DEFAULT '[]'")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_memory_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    importance TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_memory_candidates_sequence ON active_memory_candidates(event_sequence)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_memory_candidates_status ON active_memory_candidates(status, created_at)"
            )
            _ensure_column(connection, "active_memory_candidates", "promoted_knowledge_id", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(connection, "active_memory_candidates", "promoted_at", "TEXT NOT NULL DEFAULT ''")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_task_contexts (
                    task_context_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    user_declared_goal TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    primary_entities_json TEXT NOT NULL,
                    supporting_entities_json TEXT NOT NULL,
                    assistant_mode TEXT NOT NULL,
                    allowed_help_json TEXT NOT NULL,
                    privacy_mode TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_task_contexts_status ON active_task_contexts(status, updated_at)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_episodes (
                    episode_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    hypothesis TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    primary_entities_json TEXT NOT NULL,
                    supporting_entities_json TEXT NOT NULL,
                    task_context_id TEXT NOT NULL,
                    correction_refs_json TEXT NOT NULL,
                    deep_dive_refs_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    last_event_sequence INTEGER NOT NULL DEFAULT 0,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_episodes_status ON active_episodes(status, updated_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_episodes_sequence ON active_episodes(last_event_sequence)")
            _ensure_column(connection, "active_episodes", "last_event_sequence", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(connection, "active_episodes", "event_count", "INTEGER NOT NULL DEFAULT 0")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_episode_events (
                    episode_event_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_episode_events_episode ON active_episode_events(episode_id, event_sequence)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_episode_links (
                    link_id TEXT PRIMARY KEY,
                    source_episode_id TEXT NOT NULL,
                    target_episode_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_episode_links_source ON active_episode_links(source_episode_id, updated_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_muted_scopes (
                    scope_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    entity_refs_json TEXT NOT NULL,
                    collector TEXT NOT NULL,
                    source TEXT NOT NULL,
                    stimulus_type TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    do_not_interrupt INTEGER NOT NULL,
                    do_not_deep_dive INTEGER NOT NULL,
                    do_not_send_to_llm INTEGER NOT NULL,
                    do_not_store INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_muted_scopes_mode ON active_muted_scopes(mode, updated_at)")
            _ensure_column(connection, "active_muted_scopes", "status", "TEXT NOT NULL DEFAULT 'active'")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_context_windows (
                    window_id TEXT PRIMARY KEY,
                    route_class TEXT NOT NULL,
                    last_sequence INTEGER NOT NULL,
                    event_count INTEGER NOT NULL,
                    summary_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_context_boundaries (
                    boundary_id TEXT PRIMARY KEY,
                    boundary_type TEXT NOT NULL,
                    window_id TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_context_boundaries_sequence ON active_context_boundaries(event_sequence)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_resume_capsules (
                    capsule_id TEXT PRIMARY KEY,
                    boundary_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_resume_capsules_updated ON active_resume_capsules(updated_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_explanations (
                    explanation_id TEXT PRIMARY KEY,
                    route_id TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    explanation_type TEXT NOT NULL,
                    posture TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_explanations_sequence ON active_explanations(event_sequence)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_corrections (
                    correction_id TEXT PRIMARY KEY,
                    correction_type TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    note TEXT NOT NULL,
                    task_context_id TEXT NOT NULL,
                    muted_scope_id TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_corrections_created ON active_corrections(created_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_deep_dive_requests (
                    request_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    source TEXT NOT NULL,
                    requested_access TEXT NOT NULL,
                    privacy_tier TEXT NOT NULL,
                    requires_user_approval INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_deep_dive_results (
                    result_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    executor TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    safety_notes_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_deep_dive_results_request ON active_deep_dive_results(request_id, created_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_activation_responses (
                    response_id TEXT PRIMARY KEY,
                    activation_id TEXT NOT NULL,
                    response_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    task_context_id TEXT NOT NULL,
                    muted_scope_id TEXT NOT NULL,
                    harness_result_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_activation_responses_activation ON active_activation_responses(activation_id, created_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_privacy_actions (
                    action_id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    scope_json TEXT NOT NULL,
                    affected_counts_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_privacy_actions_created ON active_privacy_actions(created_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_eval_runs (
                    eval_id TEXT PRIMARY KEY,
                    scenario TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    failures_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_active_eval_runs_created ON active_eval_runs(created_at)")
            connection.commit()

    def record_route(self, route: JanusRoute) -> JanusRoute:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_event_routes
                (route_id, event_sequence, event_id, collector, source, stimulus_type, privacy_tier, route_class, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    route.route_id,
                    route.event_sequence,
                    route.event_id,
                    route.collector,
                    route.source,
                    route.stimulus_type,
                    route.privacy_tier,
                    route.route_class.value,
                    route.reason,
                    route.created_at,
                ),
            )
            connection.commit()
        return route

    def record_decision(self, decision: JanusDecision) -> JanusDecision:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_reflex_decisions
                (decision_id, route_id, event_sequence, posture, confidence, should_interrupt_user,
                 user_visible_text, agent_stimulus, reason, task_context_updates_json, memory_updates_json,
                 safety_notes_json, deep_dive_request_json, model_status, raw_output_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.route_id,
                    decision.event_sequence,
                    decision.posture.value,
                    decision.confidence.value,
                    int(decision.should_interrupt_user),
                    decision.user_visible_text,
                    decision.agent_stimulus,
                    decision.reason,
                    _json_dumps(decision.task_context_updates),
                    _json_dumps(decision.memory_updates),
                    _json_dumps(decision.safety_notes),
                    _json_dumps(decision.deep_dive_request or {}),
                    decision.model_status,
                    _json_dumps(decision.raw_output),
                    decision.created_at,
                ),
            )
            connection.commit()
        return decision

    def record_activation(self, activation: JanusActivation) -> JanusActivation:
        now = utc_now()
        if not activation.created_at:
            activation.created_at = now
        activation.updated_at = now
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO janus_activations
                (activation_id, decision_id, route_id, event_sequence, posture, status, response_mode,
                 stimulus_id, user_visible_text, agent_stimulus, reason, should_interrupt_user,
                 allowed_actions_json, forbidden_actions_json, harness_result_json, evidence_refs_json,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(activation_id) DO UPDATE SET
                    status = excluded.status,
                    response_mode = excluded.response_mode,
                    user_visible_text = excluded.user_visible_text,
                    agent_stimulus = excluded.agent_stimulus,
                    reason = excluded.reason,
                    should_interrupt_user = excluded.should_interrupt_user,
                    allowed_actions_json = excluded.allowed_actions_json,
                    forbidden_actions_json = excluded.forbidden_actions_json,
                    harness_result_json = excluded.harness_result_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    updated_at = excluded.updated_at
                """,
                (
                    activation.activation_id,
                    activation.decision_id,
                    activation.route_id,
                    activation.event_sequence,
                    activation.posture.value,
                    activation.status,
                    activation.response_mode,
                    activation.stimulus_id,
                    activation.user_visible_text,
                    activation.agent_stimulus,
                    activation.reason,
                    int(activation.should_interrupt_user),
                    _json_dumps(activation.allowed_actions),
                    _json_dumps(activation.forbidden_actions),
                    _json_dumps(activation.harness_result),
                    _json_dumps(activation.evidence_refs),
                    activation.created_at,
                    activation.updated_at,
                ),
            )
            connection.commit()
        return activation

    def record_memory_candidate(self, candidate: JanusMemoryCandidate) -> JanusMemoryCandidate:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_memory_candidates
                (candidate_id, decision_id, route_id, event_sequence, kind, summary, importance, status,
                 payload_json, evidence_refs_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    candidate.decision_id,
                    candidate.route_id,
                    candidate.event_sequence,
                    candidate.kind,
                    candidate.summary,
                    candidate.importance,
                    candidate.status,
                    _json_dumps(candidate.payload),
                    _json_dumps(candidate.evidence_refs),
                    candidate.created_at,
                ),
            )
            connection.commit()
        return candidate

    def update_memory_candidate_status(
        self,
        candidate_id: str,
        *,
        status: str,
        reason: str = "",
    ) -> dict[str, Any] | None:
        cleaned_id = str(candidate_id or "").strip()
        cleaned_status = str(status or "").strip()
        if cleaned_status not in {"candidate", "accepted", "rejected", "private", "archived"}:
            raise ValueError(f"unsupported memory candidate status: {cleaned_status or '<empty>'}")
        current = self._one("SELECT * FROM active_memory_candidates WHERE candidate_id = ?", cleaned_id)
        if current is None:
            return None
        evidence_refs = _json_loads_list(str(current.get("evidence_refs_json") or "[]"))
        transition_reason = " ".join(str(reason or "").split())[:160]
        if transition_reason:
            evidence_refs.append(f"transition_note:{transition_reason}")
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE active_memory_candidates
                SET status = ?, evidence_refs_json = ?
                WHERE candidate_id = ?
                """,
                (cleaned_status, _json_dumps(evidence_refs[-50:]), cleaned_id),
            )
            connection.commit()
        return self._memory_candidate(cleaned_id)

    def mark_memory_candidate_promoted(
        self,
        candidate_id: str,
        *,
        knowledge_id: str,
    ) -> dict[str, Any] | None:
        cleaned_id = str(candidate_id or "").strip()
        cleaned_knowledge_id = str(knowledge_id or "").strip()
        if not cleaned_id or not cleaned_knowledge_id:
            return None
        current = self._one("SELECT * FROM active_memory_candidates WHERE candidate_id = ?", cleaned_id)
        if current is None:
            return None
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE active_memory_candidates
                SET promoted_knowledge_id = ?, promoted_at = ?
                WHERE candidate_id = ?
                """,
                (cleaned_knowledge_id, utc_now(), cleaned_id),
            )
            connection.commit()
        return self._memory_candidate(cleaned_id)

    def update_activation_status(
        self,
        activation_id: str,
        *,
        status: str,
        harness_result: dict[str, Any] | None = None,
        reason: str = "",
    ) -> dict[str, Any] | None:
        cleaned_id = str(activation_id or "").strip()
        cleaned_status = str(status or "").strip()
        if cleaned_status not in {"prepared", "pending", "submitted", "skipped", "failed"}:
            raise ValueError(f"unsupported activation status: {cleaned_status or '<empty>'}")
        current = self._one("SELECT * FROM janus_activations WHERE activation_id = ?", cleaned_id)
        if current is None:
            return None
        next_reason = str(reason or current.get("reason") or "")[:1_000]
        next_result = harness_result if harness_result is not None else _json_loads(str(current.get("harness_result_json") or "{}"))
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE janus_activations
                SET status = ?, reason = ?, harness_result_json = ?, updated_at = ?
                WHERE activation_id = ?
                """,
                (cleaned_status, next_reason, _json_dumps(next_result), now, cleaned_id),
            )
            connection.commit()
        return self._activation(cleaned_id)

    def upsert_task_context(self, context: TaskContext) -> TaskContext:
        now = utc_now()
        if not context.created_at:
            context.created_at = now
        context.updated_at = now
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO active_task_contexts
                (task_context_id, status, source, user_declared_goal, episode_id, primary_entities_json,
                 supporting_entities_json, assistant_mode, allowed_help_json, privacy_mode, summary,
                 evidence_refs_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_context_id) DO UPDATE SET
                    status = excluded.status,
                    source = excluded.source,
                    user_declared_goal = excluded.user_declared_goal,
                    episode_id = excluded.episode_id,
                    primary_entities_json = excluded.primary_entities_json,
                    supporting_entities_json = excluded.supporting_entities_json,
                    assistant_mode = excluded.assistant_mode,
                    allowed_help_json = excluded.allowed_help_json,
                    privacy_mode = excluded.privacy_mode,
                    summary = excluded.summary,
                    evidence_refs_json = excluded.evidence_refs_json,
                    updated_at = excluded.updated_at
                """,
                (
                    context.task_context_id,
                    context.status,
                    context.source,
                    context.user_declared_goal,
                    context.episode_id,
                    _json_dumps(context.primary_entities),
                    _json_dumps(context.supporting_entities),
                    context.assistant_mode,
                    _json_dumps(context.allowed_help),
                    context.privacy_mode,
                    context.summary,
                    _json_dumps(context.evidence_refs),
                    context.created_at,
                    context.updated_at,
                ),
            )
            connection.commit()
        return context

    def upsert_episode(self, episode: JanusEpisode) -> JanusEpisode:
        now = utc_now()
        current = self._one("SELECT created_at FROM active_episodes WHERE episode_id = ?", episode.episode_id)
        if current is not None:
            episode.created_at = str(current.get("created_at") or episode.created_at or now)
        elif not episode.created_at:
            episode.created_at = now
        episode.updated_at = now
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO active_episodes
                (episode_id, status, source, hypothesis, summary, confidence, primary_entities_json,
                 supporting_entities_json, task_context_id, correction_refs_json, deep_dive_refs_json,
                 evidence_refs_json, last_event_sequence, event_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id) DO UPDATE SET
                    status = excluded.status,
                    source = excluded.source,
                    hypothesis = excluded.hypothesis,
                    summary = excluded.summary,
                    confidence = excluded.confidence,
                    primary_entities_json = excluded.primary_entities_json,
                    supporting_entities_json = excluded.supporting_entities_json,
                    task_context_id = excluded.task_context_id,
                    correction_refs_json = excluded.correction_refs_json,
                    deep_dive_refs_json = excluded.deep_dive_refs_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    last_event_sequence = MAX(active_episodes.last_event_sequence, excluded.last_event_sequence),
                    event_count = MAX(active_episodes.event_count, excluded.event_count),
                    updated_at = excluded.updated_at
                """,
                (
                    episode.episode_id,
                    episode.status,
                    episode.source,
                    episode.hypothesis,
                    episode.summary,
                    episode.confidence.value if hasattr(episode.confidence, "value") else str(episode.confidence),
                    _json_dumps(episode.primary_entities),
                    _json_dumps(episode.supporting_entities),
                    episode.task_context_id,
                    _json_dumps(episode.correction_refs),
                    _json_dumps(episode.deep_dive_refs),
                    _json_dumps(episode.evidence_refs),
                    int(episode.last_event_sequence or 0),
                    int(episode.event_count or 0),
                    episode.created_at,
                    episode.updated_at,
                ),
            )
            connection.commit()
        return episode

    def record_episode_event(
        self,
        *,
        episode_id: str,
        event: dict[str, Any],
        relation: str,
        route_id: str,
        decision_id: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        event_sequence = int(event.get("sequence") or 0)
        event_id = str(event.get("event_id") or "")
        cleaned_relation = " ".join(str(relation or "observed").split())[:120]
        episode_event_id = _episode_event_id(episode_id, event_sequence, cleaned_relation, decision_id)
        created_at = utc_now()
        payload = {
            "episode_event_id": episode_event_id,
            "episode_id": episode_id,
            "event_sequence": event_sequence,
            "event_id": event_id,
            "relation": cleaned_relation,
            "route_id": route_id,
            "decision_id": decision_id,
            "evidence": evidence,
            "created_at": created_at,
        }
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO active_episode_events
                (episode_event_id, episode_id, event_sequence, event_id, relation, route_id,
                 decision_id, evidence_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_event_id,
                    episode_id,
                    event_sequence,
                    event_id,
                    cleaned_relation,
                    route_id,
                    decision_id,
                    _json_dumps(evidence),
                    created_at,
                ),
            )
            connection.execute(
                """
                UPDATE active_episodes
                SET last_event_sequence = MAX(last_event_sequence, ?),
                    event_count = (
                        SELECT COUNT(*)
                        FROM active_episode_events
                        WHERE active_episode_events.episode_id = active_episodes.episode_id
                    ),
                    updated_at = ?
                WHERE episode_id = ?
                """,
                (event_sequence, created_at, episode_id),
            )
            connection.commit()
        return payload

    def episode(self, episode_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM active_episodes WHERE episode_id = ?", str(episode_id or ""))
        if row is None:
            return None
        row["primary_entities"] = _json_loads_list(row.pop("primary_entities_json", "[]"))
        row["supporting_entities"] = _json_loads_list(row.pop("supporting_entities_json", "[]"))
        row["correction_refs"] = _json_loads_list(row.pop("correction_refs_json", "[]"))
        row["deep_dive_refs"] = _json_loads_list(row.pop("deep_dive_refs_json", "[]"))
        row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return row

    def update_episode_status(
        self,
        episode_id: str,
        *,
        status: str,
        reason: str = "",
        evidence_refs: list[str] | None = None,
    ) -> dict[str, Any] | None:
        cleaned_id = str(episode_id or "").strip()
        cleaned_status = str(status or "").strip()
        if cleaned_status not in {"active", "waiting", "paused", "completed", "abandoned", "merged", "split"}:
            raise ValueError(f"unsupported episode status: {cleaned_status or '<empty>'}")
        current = self.episode(cleaned_id)
        if current is None:
            return None
        refs = [str(item) for item in current.get("evidence_refs", []) if str(item)]
        refs.extend(str(item) for item in (evidence_refs or []) if str(item))
        if reason:
            refs.append(f"transition_note:{' '.join(str(reason).split())[:160]}")
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE active_episodes
                SET status = ?, evidence_refs_json = ?, updated_at = ?
                WHERE episode_id = ?
                """,
                (cleaned_status, _json_dumps(refs[-60:]), now, cleaned_id),
            )
            connection.commit()
        return self.episode(cleaned_id)

    def record_episode_link(
        self,
        *,
        source_episode_id: str,
        target_episode_id: str,
        relation: str,
        status: str = "active",
        reason: str = "",
        evidence_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        source = str(source_episode_id or "").strip()
        target = str(target_episode_id or "").strip()
        relation_text = " ".join(str(relation or "related").split())[:120]
        now = utc_now()
        digest = hashlib.sha256(f"{source}:{target}:{relation_text}".encode("utf-8")).hexdigest()[:20]
        link_id = f"episode_link_{digest}"
        payload = {
            "link_id": link_id,
            "source_episode_id": source,
            "target_episode_id": target,
            "relation": relation_text,
            "status": str(status or "active")[:80],
            "reason": " ".join(str(reason or "").split())[:1_000],
            "evidence_refs": [str(item) for item in (evidence_refs or []) if str(item)][:40],
            "created_at": now,
            "updated_at": now,
        }
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO active_episode_links
                (link_id, source_episode_id, target_episode_id, relation, status, reason,
                 evidence_refs_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(link_id) DO UPDATE SET
                    status = excluded.status,
                    reason = excluded.reason,
                    evidence_refs_json = excluded.evidence_refs_json,
                    updated_at = excluded.updated_at
                """,
                (
                    link_id,
                    source,
                    target,
                    payload["relation"],
                    payload["status"],
                    payload["reason"],
                    _json_dumps(payload["evidence_refs"]),
                    now,
                    now,
                ),
            )
            connection.commit()
        return payload

    def create_muted_scope(self, scope: MutedScope) -> MutedScope:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_muted_scopes
                (scope_id, mode, scope_type, status, entity_refs_json, collector, source, stimulus_type, expires_at,
                 do_not_interrupt, do_not_deep_dive, do_not_send_to_llm, do_not_store, reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    scope.mode.value,
                    scope.scope_type,
                    scope.status,
                    _json_dumps(scope.entity_refs),
                    scope.collector,
                    scope.source,
                    scope.stimulus_type,
                    scope.expires_at,
                    int(scope.do_not_interrupt),
                    int(scope.do_not_deep_dive),
                    int(scope.do_not_send_to_llm),
                    int(scope.do_not_store),
                    scope.reason,
                    scope.created_at,
                    scope.updated_at,
                ),
            )
            connection.commit()
        return scope

    def cancel_muted_scope(self, scope_id: str, *, reason: str = "") -> dict[str, Any] | None:
        now = utc_now()
        cleaned_id = str(scope_id or "").strip()
        if not cleaned_id:
            return None
        current = self._one("SELECT * FROM active_muted_scopes WHERE scope_id = ?", cleaned_id)
        if current is None:
            return None
        updated_reason = str(current.get("reason") or "")
        cancel_reason = " ".join(str(reason or "").split())[:500]
        if cancel_reason:
            updated_reason = f"{updated_reason} Cancelled: {cancel_reason}".strip()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE active_muted_scopes
                SET status = 'cancelled', expires_at = ?, reason = ?, updated_at = ?
                WHERE scope_id = ?
                """,
                (now, updated_reason, now, cleaned_id),
            )
            connection.commit()
        return self._muted_scope(cleaned_id)

    def record_context_event(self, event: dict[str, Any], *, retain: int = 80) -> dict[str, Any]:
        summary = _context_event_summary(event)
        windows = [
            self._append_context_window("rolling_context", "rolling", "all", summary, retain=retain),
            self._append_context_window(
                _window_id("collector", summary["collector"]),
                "collector",
                summary["collector"],
                summary,
                retain=retain,
            ),
            self._append_context_window(
                _window_id("source", summary["source"]),
                "source",
                summary["source"],
                summary,
                retain=retain,
            ),
        ]
        for entity_ref in summary.get("entity_refs", [])[:6]:
            windows.append(
                self._append_context_window(
                    _window_id("entity", entity_ref),
                    "entity",
                    entity_ref,
                    summary,
                    retain=retain,
                )
            )
        return {"rolling_context": windows[0], "windows": windows}

    def detect_context_boundary(
        self,
        context_result: dict[str, Any],
        *,
        stable_event_count: int = 3,
        stable_seconds: int = 120,
        return_gap_seconds: int = 1_800,
    ) -> dict[str, Any] | None:
        rolling = context_result.get("rolling_context", {})
        if isinstance(rolling, dict):
            gap_boundary = self._detect_return_gap_boundary(rolling, return_gap_seconds=return_gap_seconds)
            if gap_boundary is not None:
                return gap_boundary
        windows = context_result.get("windows", [])
        if not isinstance(windows, list):
            return None
        preferred = sorted(
            [window for window in windows if isinstance(window, dict) and window.get("window_kind") in {"entity", "source"}],
            key=lambda item: 0 if item.get("window_kind") == "entity" else 1,
        )
        for window in preferred:
            boundary = self._detect_stable_context_boundary(
                window,
                stable_event_count=stable_event_count,
                stable_seconds=stable_seconds,
            )
            if boundary is not None:
                return boundary
        return None

    def _append_context_window(
        self,
        window_id: str,
        window_kind: str,
        anchor: str,
        summary: dict[str, Any],
        *,
        retain: int,
    ) -> dict[str, Any]:
        current = self.context_window(window_id=window_id)
        events = current.get("events", [])
        if not isinstance(events, list):
            events = []
        events.append(summary)
        events = events[-max(1, min(int(retain or 80), 500)) :]
        payload = {
            "window_id": window_id,
            "window_kind": window_kind,
            "anchor": anchor,
            "events": events,
            "event_count": len(events),
            "latest_event": events[-1] if events else {},
            "collector_counts": _counts(item.get("collector") for item in events),
            "source_counts": _counts(item.get("source") for item in events),
            "stimulus_counts": _counts(item.get("stimulus_type") for item in events),
            "entity_refs": _unique_entity_refs(events),
            "raw_content_included": False,
        }
        last_sequence = int(summary["sequence"])
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO active_context_windows (window_id, route_class, last_sequence, event_count, summary_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(window_id) DO UPDATE SET
                    route_class = excluded.route_class,
                    last_sequence = excluded.last_sequence,
                    event_count = excluded.event_count,
                    summary_json = excluded.summary_json,
                    updated_at = excluded.updated_at
                """,
                (window_id, "context", last_sequence, len(events), _json_dumps(payload), utc_now()),
            )
            connection.commit()
        return payload

    def _detect_return_gap_boundary(self, window: dict[str, Any], *, return_gap_seconds: int) -> dict[str, Any] | None:
        events = window.get("events", [])
        if not isinstance(events, list) or len(events) < 2:
            return None
        current = events[-1]
        previous = events[-2]
        current_ts = _parse_timestamp(current.get("occurred_at"))
        previous_ts = _parse_timestamp(previous.get("occurred_at"))
        if current_ts is None or previous_ts is None:
            return None
        gap_seconds = int(current_ts - previous_ts)
        if gap_seconds < max(60, int(return_gap_seconds or 1_800)):
            return None
        latest_sequence = int(current.get("sequence") or 0)
        boundary_id = f"return_after_gap:{latest_sequence}"
        reason = f"Context resumed after approximately {gap_seconds} seconds away."
        return self._record_context_boundary(
            boundary_id=boundary_id,
            boundary_type="return_after_gap",
            window=window,
            event=current,
            reason=reason,
            evidence={"gap_seconds": gap_seconds, "previous_event": previous, "latest_event": current},
        )

    def _detect_stable_context_boundary(
        self,
        window: dict[str, Any],
        *,
        stable_event_count: int,
        stable_seconds: int,
    ) -> dict[str, Any] | None:
        events = window.get("events", [])
        if not isinstance(events, list):
            return None
        threshold = max(2, int(stable_event_count or 3))
        if len(events) != threshold:
            return None
        first_ts = _parse_timestamp(events[0].get("occurred_at"))
        latest = events[-1]
        latest_ts = _parse_timestamp(latest.get("occurred_at"))
        if first_ts is None or latest_ts is None:
            return None
        span_seconds = int(latest_ts - first_ts)
        if span_seconds < max(0, int(stable_seconds or 120)):
            return None
        window_id = str(window.get("window_id") or "")
        latest_sequence = int(latest.get("sequence") or 0)
        boundary_id = f"stable_context:{window_id}:{threshold}"
        reason = f"Context stayed on {window.get('window_kind', 'window')}:{window.get('anchor', 'unknown')} for {threshold} events over approximately {span_seconds} seconds."
        return self._record_context_boundary(
            boundary_id=boundary_id,
            boundary_type="stable_context",
            window=window,
            event=latest,
            reason=reason,
            evidence={"span_seconds": span_seconds, "threshold_event_count": threshold, "latest_event": latest},
        )

    def _record_context_boundary(
        self,
        *,
        boundary_id: str,
        boundary_type: str,
        window: dict[str, Any],
        event: dict[str, Any],
        reason: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any] | None:
        now = utc_now()
        window_id = str(window.get("window_id") or "")
        latest_sequence = int(event.get("sequence") or 0)
        payload = {
            "boundary_id": boundary_id,
            "boundary_type": boundary_type,
            "window_id": window_id,
            "window_kind": str(window.get("window_kind") or ""),
            "anchor": str(window.get("anchor") or ""),
            "event_sequence": latest_sequence,
            "reason": reason,
            "evidence": evidence,
            "created_at": now,
        }
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO active_context_boundaries
                (boundary_id, boundary_type, window_id, event_sequence, reason, evidence_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (boundary_id, boundary_type, window_id, latest_sequence, reason, _json_dumps(payload), now),
            )
            inserted = connection.total_changes > 0
            connection.commit()
        if not inserted:
            return None
        return payload

    def record_resume_capsule(self, boundary: dict[str, Any], decision: JanusDecision | None = None) -> dict[str, Any]:
        now = utc_now()
        boundary_id = str(boundary.get("boundary_id") or "")
        capsule_id = f"capsule:{boundary_id}"
        summary = _resume_capsule_summary(boundary, decision)
        evidence = {
            "boundary": boundary,
            "decision_id": decision.decision_id if decision is not None else "",
            "posture": decision.posture.value if decision is not None else "",
            "event_sequence": int(boundary.get("event_sequence") or 0),
        }
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO active_resume_capsules
                (capsule_id, boundary_id, status, summary, evidence_json, created_at, updated_at)
                VALUES (?, ?, 'active', ?, ?, ?, ?)
                ON CONFLICT(capsule_id) DO UPDATE SET
                    status = excluded.status,
                    summary = excluded.summary,
                    evidence_json = excluded.evidence_json,
                    updated_at = excluded.updated_at
                """,
                (capsule_id, boundary_id, summary, _json_dumps(evidence), now, now),
            )
            connection.commit()
        return {
            "capsule_id": capsule_id,
            "boundary_id": boundary_id,
            "status": "active",
            "summary": summary,
            "evidence": evidence,
            "created_at": now,
            "updated_at": now,
        }

    def record_explanation(
        self,
        *,
        route: JanusRoute,
        event: dict[str, Any],
        explanation_type: str,
        summary: str,
        decision: JanusDecision | None = None,
        boundary: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        posture = decision.posture.value if decision is not None else route.route_class.value
        evidence_refs = _explanation_evidence_refs(route, event, decision=decision, boundary=boundary)
        explanation_id = _explanation_id(route, explanation_type)
        payload_details = {
            "collector": route.collector,
            "source": route.source,
            "stimulus_type": route.stimulus_type,
            "route_class": route.route_class.value,
            "route_reason": route.reason,
            "decision_id": decision.decision_id if decision is not None else "",
            "decision_reason": decision.reason if decision is not None else "",
            "boundary": boundary or {},
            **(details or {}),
        }
        cleaned_summary = " ".join(str(summary or route.reason).split())[:1_000]
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_explanations
                (explanation_id, route_id, event_sequence, explanation_type, posture, summary,
                 evidence_refs_json, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    explanation_id,
                    route.route_id,
                    route.event_sequence,
                    str(explanation_type or "route"),
                    posture,
                    cleaned_summary,
                    _json_dumps(evidence_refs),
                    _json_dumps(payload_details),
                    now,
                ),
            )
            connection.commit()
        return {
            "explanation_id": explanation_id,
            "route_id": route.route_id,
            "event_sequence": route.event_sequence,
            "explanation_type": str(explanation_type or "route"),
            "posture": posture,
            "summary": cleaned_summary,
            "evidence_refs": evidence_refs,
            "details": payload_details,
            "created_at": now,
        }

    def record_correction(
        self,
        *,
        correction_id: str,
        correction_type: str,
        target_type: str,
        target_id: str,
        note: str = "",
        task_context_id: str = "",
        muted_scope_id: str = "",
        evidence_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        payload = {
            "correction_id": correction_id,
            "correction_type": correction_type,
            "target_type": target_type,
            "target_id": target_id,
            "note": note,
            "task_context_id": task_context_id,
            "muted_scope_id": muted_scope_id,
            "evidence_refs": list(evidence_refs or []),
            "created_at": now,
        }
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_corrections
                (correction_id, correction_type, target_type, target_id, note, task_context_id,
                 muted_scope_id, evidence_refs_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    correction_id,
                    correction_type,
                    target_type,
                    target_id,
                    note,
                    task_context_id,
                    muted_scope_id,
                    _json_dumps(payload["evidence_refs"]),
                    now,
                ),
            )
            connection.commit()
        return payload

    def record_deep_dive_request(self, request: DeepDiveRequest) -> DeepDiveRequest:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_deep_dive_requests
                (request_id, episode_id, requested_by, purpose, source, requested_access, privacy_tier,
                 requires_user_approval, status, evidence_refs_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id,
                    request.episode_id,
                    request.requested_by,
                    request.purpose,
                    request.source,
                    request.requested_access,
                    request.privacy_tier,
                    int(request.requires_user_approval),
                    request.status,
                    _json_dumps(request.evidence_refs),
                    request.created_at,
                    request.updated_at,
                ),
            )
            connection.commit()
        return request

    def record_deep_dive_result(self, result: DeepDiveResult) -> DeepDiveResult:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_deep_dive_results
                (result_id, request_id, episode_id, status, executor, summary, evidence_json,
                 safety_notes_json, evidence_refs_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.result_id,
                    result.request_id,
                    result.episode_id,
                    result.status,
                    result.executor,
                    result.summary,
                    _json_dumps(result.evidence),
                    _json_dumps(result.safety_notes),
                    _json_dumps(result.evidence_refs),
                    result.created_at,
                ),
            )
            connection.commit()
        return result

    def record_activation_response(self, response: ActivationResponse) -> ActivationResponse:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_activation_responses
                (response_id, activation_id, response_type, text, action_taken, task_context_id,
                 muted_scope_id, harness_result_json, evidence_refs_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.response_id,
                    response.activation_id,
                    response.response_type,
                    response.text,
                    response.action_taken,
                    response.task_context_id,
                    response.muted_scope_id,
                    _json_dumps(response.harness_result),
                    _json_dumps(response.evidence_refs),
                    response.created_at,
                ),
            )
            connection.commit()
        return response

    def record_privacy_action(
        self,
        *,
        action_id: str,
        action_type: str,
        scope: dict[str, Any],
        affected_counts: dict[str, int],
        status: str,
        reason: str = "",
    ) -> dict[str, Any]:
        now = utc_now()
        payload = {
            "action_id": action_id,
            "action_type": action_type,
            "scope": scope,
            "affected_counts": affected_counts,
            "status": status,
            "reason": reason,
            "created_at": now,
        }
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_privacy_actions
                (action_id, action_type, scope_json, affected_counts_json, status, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (action_id, action_type, _json_dumps(scope), _json_dumps(affected_counts), status, reason, now),
            )
            connection.commit()
        return payload

    def record_eval_run(
        self,
        *,
        eval_id: str,
        scenario: str,
        status: str,
        summary: str,
        metrics: dict[str, Any],
        failures: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = utc_now()
        payload = {
            "eval_id": eval_id,
            "scenario": scenario,
            "status": status,
            "summary": summary,
            "metrics": metrics,
            "failures": failures,
            "created_at": now,
        }
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_eval_runs
                (eval_id, scenario, status, summary, metrics_json, failures_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (eval_id, scenario, status, summary, _json_dumps(metrics), _json_dumps(failures), now),
            )
            connection.commit()
        return payload

    def update_deep_dive_status(self, request_id: str, *, status: str, reason: str = "") -> dict[str, Any] | None:
        cleaned_id = str(request_id or "").strip()
        cleaned_status = str(status or "").strip()
        if cleaned_status not in {"approved", "executing", "rejected", "denied", "completed", "expired", "blocked_by_policy", "needs_approval"}:
            raise ValueError(f"unsupported deep-dive status: {cleaned_status or '<empty>'}")
        current = self._one("SELECT * FROM active_deep_dive_requests WHERE request_id = ?", cleaned_id)
        if current is None:
            return None
        evidence_refs = _json_loads_list(str(current.get("evidence_refs_json") or "[]"))
        if reason:
            evidence_refs.append(f"transition_note:{' '.join(str(reason).split())[:160]}")
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE active_deep_dive_requests
                SET status = ?, evidence_refs_json = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (cleaned_status, _json_dumps(evidence_refs[-50:]), now, cleaned_id),
            )
            connection.commit()
        return self._deep_dive_request(cleaned_id)

    def active_muted_scope_for(self, event: dict[str, Any]) -> MutedScope | None:
        now = utc_now()
        collector = str(event.get("collector") or "")
        source = str(event.get("source") or "")
        stimulus_type = str(event.get("stimulus_type") or "")
        entity_refs = set(_entity_refs(event))
        for scope in self.muted_scopes(limit=200):
            if str(scope.get("status") or "active") != "active":
                continue
            expires_at = str(scope.get("expires_at") or "")
            if expires_at and expires_at < now:
                continue
            scope_entities = set(scope.get("entity_refs", []))
            if scope_entities and entity_refs and scope_entities.intersection(entity_refs):
                return _muted_scope_from_payload(scope)
            if scope.get("collector") and scope["collector"] != collector:
                continue
            if scope.get("source") and scope["source"] != source:
                continue
            if scope.get("stimulus_type") and scope["stimulus_type"] != stimulus_type:
                continue
            if scope.get("collector") or scope.get("source") or scope.get("stimulus_type"):
                return _muted_scope_from_payload(scope)
        return None

    def _muted_scope(self, scope_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM active_muted_scopes WHERE scope_id = ?", scope_id)
        if row is None:
            return None
        row["entity_refs"] = _json_loads_list(row.pop("entity_refs_json", "[]"))
        for key in ("do_not_interrupt", "do_not_deep_dive", "do_not_send_to_llm", "do_not_store"):
            row[key] = bool(row.get(key))
        return row

    def _deep_dive_request(self, request_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM active_deep_dive_requests WHERE request_id = ?", request_id)
        if row is None:
            return None
        row["requires_user_approval"] = bool(row.get("requires_user_approval"))
        row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return row

    def _activation(self, activation_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM janus_activations WHERE activation_id = ?", activation_id)
        if row is None:
            return None
        row["should_interrupt_user"] = bool(row.get("should_interrupt_user"))
        row["allowed_actions"] = _json_loads_list(row.pop("allowed_actions_json", "[]"))
        row["forbidden_actions"] = _json_loads_list(row.pop("forbidden_actions_json", "[]"))
        row["harness_result"] = _json_loads(row.pop("harness_result_json", "{}"))
        row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return row

    def activation(self, activation_id: str) -> dict[str, Any] | None:
        return self._activation(activation_id)

    def _memory_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM active_memory_candidates WHERE candidate_id = ?", candidate_id)
        if row is None:
            return None
        row["payload"] = _json_loads(row.pop("payload_json", "{}"))
        row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return row

    def memory_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        return self._memory_candidate(candidate_id)

    def _one(self, query: str, value: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(query, (value,)).fetchone()
        return dict(row) if row is not None else None

    def context_window(self, *, window_id: str = "rolling_context") -> dict[str, Any]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT summary_json FROM active_context_windows WHERE window_id = ?",
                (window_id,),
            ).fetchone()
        if row is None:
            return {"window_id": window_id, "events": []}
        return _json_loads(row["summary_json"])

    def context_windows(self, *, limit: int = 8) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_context_windows
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        windows: list[dict[str, Any]] = []
        for row in rows:
            payload = _json_loads(row.get("summary_json", "{}"))
            if not payload:
                continue
            payload.setdefault("window_id", row.get("window_id", ""))
            payload.setdefault("last_sequence", row.get("last_sequence", 0))
            payload.setdefault("event_count", row.get("event_count", 0))
            payload.setdefault("updated_at", row.get("updated_at", ""))
            windows.append(payload)
        return windows

    def context_bundle(self, *, limit: int = 8) -> dict[str, Any]:
        return {"rolling_context": self.context_window(), "context_windows": self.context_windows(limit=limit)}

    def context_boundaries(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_context_boundaries
            ORDER BY event_sequence DESC
            LIMIT ?
            """,
            limit=limit,
        )
        boundaries: list[dict[str, Any]] = []
        for row in rows:
            payload = _json_loads(row.get("evidence_json", "{}"))
            if not payload:
                payload = {
                    "boundary_id": row.get("boundary_id", ""),
                    "boundary_type": row.get("boundary_type", ""),
                    "window_id": row.get("window_id", ""),
                    "event_sequence": row.get("event_sequence", 0),
                    "reason": row.get("reason", ""),
                    "created_at": row.get("created_at", ""),
                }
            boundaries.append(payload)
        return boundaries

    def resume_capsules(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_resume_capsules
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        capsules: list[dict[str, Any]] = []
        for row in rows:
            row["evidence"] = _json_loads(row.pop("evidence_json", "{}"))
            capsules.append(row)
        return capsules

    def explanations(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_explanations
            ORDER BY event_sequence DESC, created_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
            row["details"] = _json_loads(row.pop("details_json", "{}"))
        return rows

    def corrections(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_corrections
            ORDER BY created_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def routes(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self._recent(
            """
            SELECT * FROM active_event_routes
            ORDER BY event_sequence DESC
            LIMIT ?
            """,
            limit=limit,
        )

    def decisions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_reflex_decisions
            ORDER BY event_sequence DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["should_interrupt_user"] = bool(row.get("should_interrupt_user"))
            row["task_context_updates"] = _json_loads_list(row.pop("task_context_updates_json", "[]"))
            row["memory_updates"] = _json_loads_list(row.pop("memory_updates_json", "[]"))
            row["safety_notes"] = _json_loads_list(row.pop("safety_notes_json", "[]"))
            row["deep_dive_request"] = _json_loads(row.pop("deep_dive_request_json", "{}"))
            row["raw_output"] = _json_loads(row.pop("raw_output_json", "{}"))
        return rows

    def activations(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM janus_activations
            ORDER BY event_sequence DESC, updated_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["should_interrupt_user"] = bool(row.get("should_interrupt_user"))
            row["allowed_actions"] = _json_loads_list(row.pop("allowed_actions_json", "[]"))
            row["forbidden_actions"] = _json_loads_list(row.pop("forbidden_actions_json", "[]"))
            row["harness_result"] = _json_loads(row.pop("harness_result_json", "{}"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def memory_candidates(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_memory_candidates
            ORDER BY event_sequence DESC, created_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["payload"] = _json_loads(row.pop("payload_json", "{}"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def memory_candidates_for_decision(self, decision_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_memory_candidates
            WHERE decision_id = ?
            ORDER BY event_sequence DESC, created_at DESC
            LIMIT ?
            """,
            limit=limit,
            params=(str(decision_id or ""),),
        )
        for row in rows:
            row["payload"] = _json_loads(row.pop("payload_json", "{}"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def activations_for_decision(self, decision_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM janus_activations
            WHERE decision_id = ?
            ORDER BY event_sequence DESC, updated_at DESC
            LIMIT ?
            """,
            limit=limit,
            params=(str(decision_id or ""),),
        )
        for row in rows:
            row["should_interrupt_user"] = bool(row.get("should_interrupt_user"))
            row["allowed_actions"] = _json_loads_list(row.pop("allowed_actions_json", "[]"))
            row["forbidden_actions"] = _json_loads_list(row.pop("forbidden_actions_json", "[]"))
            row["harness_result"] = _json_loads(row.pop("harness_result_json", "{}"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def task_contexts(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_task_contexts
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["primary_entities"] = _json_loads_list(row.pop("primary_entities_json", "[]"))
            row["supporting_entities"] = _json_loads_list(row.pop("supporting_entities_json", "[]"))
            row["allowed_help"] = _json_loads_list(row.pop("allowed_help_json", "[]"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def episodes(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_episodes
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["primary_entities"] = _json_loads_list(row.pop("primary_entities_json", "[]"))
            row["supporting_entities"] = _json_loads_list(row.pop("supporting_entities_json", "[]"))
            row["correction_refs"] = _json_loads_list(row.pop("correction_refs_json", "[]"))
            row["deep_dive_refs"] = _json_loads_list(row.pop("deep_dive_refs_json", "[]"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def episode_events(self, *, episode_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if episode_id:
            rows = self._recent(
                """
                SELECT * FROM active_episode_events
                WHERE episode_id = ?
                ORDER BY event_sequence DESC, created_at DESC
                LIMIT ?
                """,
                limit=limit,
                params=(str(episode_id),),
            )
        else:
            rows = self._recent(
                """
                SELECT * FROM active_episode_events
                ORDER BY event_sequence DESC, created_at DESC
                LIMIT ?
                """,
                limit=limit,
            )
        for row in rows:
            row["evidence"] = _json_loads(row.pop("evidence_json", "{}"))
        return rows

    def episode_links(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_episode_links
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def muted_scopes(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_muted_scopes
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["entity_refs"] = _json_loads_list(row.pop("entity_refs_json", "[]"))
            for key in ("do_not_interrupt", "do_not_deep_dive", "do_not_send_to_llm", "do_not_store"):
                row[key] = bool(row.get(key))
        return rows

    def deep_dive_requests(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_deep_dive_requests
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["requires_user_approval"] = bool(row.get("requires_user_approval"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def deep_dive_results(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_deep_dive_results
            ORDER BY created_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["evidence"] = _json_loads(row.pop("evidence_json", "{}"))
            row["safety_notes"] = _json_loads_list(row.pop("safety_notes_json", "[]"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def activation_responses(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_activation_responses
            ORDER BY created_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["harness_result"] = _json_loads(row.pop("harness_result_json", "{}"))
            row["evidence_refs"] = _json_loads_list(row.pop("evidence_refs_json", "[]"))
        return rows

    def privacy_actions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_privacy_actions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["scope"] = _json_loads(row.pop("scope_json", "{}"))
            row["affected_counts"] = _json_loads(row.pop("affected_counts_json", "{}"))
        return rows

    def eval_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._recent(
            """
            SELECT * FROM active_eval_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            limit=limit,
        )
        for row in rows:
            row["metrics"] = _json_loads(row.pop("metrics_json", "{}"))
            row["failures"] = _json_loads_list(row.pop("failures_json", "[]"))
        return rows

    def status(self, *, limit: int = 20) -> dict[str, Any]:
        return {
            "store_path": str(self.path),
            "routes": self.routes(limit=limit),
            "decisions": self.decisions(limit=limit),
            "activations": self.activations(limit=limit),
            "memory_candidates": self.memory_candidates(limit=limit),
            "episodes": self.episodes(limit=limit),
            "episode_events": self.episode_events(limit=limit),
            "episode_links": self.episode_links(limit=limit),
            "task_contexts": self.task_contexts(limit=limit),
            "muted_scopes": self.muted_scopes(limit=limit),
            "deep_dive_requests": self.deep_dive_requests(limit=limit),
            "deep_dive_results": self.deep_dive_results(limit=limit),
            "activation_responses": self.activation_responses(limit=limit),
            "context_window": self.context_window(),
            "context_windows": self.context_windows(limit=limit),
            "context_boundaries": self.context_boundaries(limit=limit),
            "resume_capsules": self.resume_capsules(limit=limit),
            "explanations": self.explanations(limit=limit),
            "corrections": self.corrections(limit=limit),
            "privacy_actions": self.privacy_actions(limit=limit),
            "eval_runs": self.eval_runs(limit=limit),
        }

    def _recent(self, query: str, *, limit: int, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, (*params, max(1, min(int(limit or 20), 500)))).fetchall()
        return [dict(row) for row in rows]


def _muted_scope_from_payload(payload: dict[str, Any]) -> MutedScope:
    from .models import MutedScopeMode

    return MutedScope(
        scope_id=str(payload.get("scope_id") or ""),
        mode=MutedScopeMode(str(payload.get("mode") or MutedScopeMode.NO_ASSISTANCE.value)),
        scope_type=str(payload.get("scope_type") or ""),
        status=str(payload.get("status") or "active"),
        entity_refs=[str(item) for item in payload.get("entity_refs", []) if str(item)],
        collector=str(payload.get("collector") or ""),
        source=str(payload.get("source") or ""),
        stimulus_type=str(payload.get("stimulus_type") or ""),
        expires_at=str(payload.get("expires_at") or ""),
        do_not_interrupt=bool(payload.get("do_not_interrupt", True)),
        do_not_deep_dive=bool(payload.get("do_not_deep_dive", True)),
        do_not_send_to_llm=bool(payload.get("do_not_send_to_llm", True)),
        do_not_store=bool(payload.get("do_not_store", False)),
        reason=str(payload.get("reason") or ""),
        created_at=str(payload.get("created_at") or utc_now()),
        updated_at=str(payload.get("updated_at") or utc_now()),
    )


def _entity_refs(event: dict[str, Any]) -> list[str]:
    return extract_entity_refs(event, limit=20)


def _episode_event_id(episode_id: str, event_sequence: int, relation: str, decision_id: str) -> str:
    raw = f"{episode_id}:{event_sequence}:{relation}:{decision_id}".encode("utf-8", errors="ignore")
    return f"episode_event_{hashlib.sha256(raw).hexdigest()[:24]}"


def _context_event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence": int(event.get("sequence") or 0),
        "event_id": str(event.get("event_id") or ""),
        "collector": str(event.get("collector") or ""),
        "source": str(event.get("source") or ""),
        "stimulus_type": str(event.get("stimulus_type") or ""),
        "privacy_tier": str(event.get("privacy_tier") or ""),
        "occurred_at": str(event.get("occurred_at") or ""),
        "text": str(event.get("text") or "")[:240],
        "entity_refs": _entity_refs(event),
    }


def _window_id(kind: str, value: str) -> str:
    cleaned = " ".join(str(value or "unknown").split())[:240] or "unknown"
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}"


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12])


def _unique_entity_refs(events: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for event in events:
        for ref in event.get("entity_refs", []):
            text = str(ref or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            refs.append(text)
            if len(refs) >= 20:
                return refs
    return refs


def _parse_timestamp(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _resume_capsule_summary(boundary: dict[str, Any], decision: JanusDecision | None) -> str:
    if decision is not None:
        for value in (decision.agent_stimulus, decision.user_visible_text, decision.reason):
            text = " ".join(str(value or "").split())
            if text:
                return text[:1_000]
    evidence = boundary.get("evidence", {})
    latest = evidence.get("latest_event", {}) if isinstance(evidence, dict) else {}
    if not isinstance(latest, dict):
        latest = {}
    collector = str(latest.get("collector") or "activity")
    stimulus_type = str(latest.get("stimulus_type") or boundary.get("boundary_type") or "context")
    return f"Resume capsule prepared from {collector}:{stimulus_type} boundary evidence."


def _explanation_id(route: JanusRoute, explanation_type: str) -> str:
    digest = hashlib.sha256(f"{route.route_id}:{explanation_type}:{route.event_sequence}".encode("utf-8")).hexdigest()[:16]
    return f"why_{digest}"


def _explanation_evidence_refs(
    route: JanusRoute,
    event: dict[str, Any],
    *,
    decision: JanusDecision | None,
    boundary: dict[str, Any] | None,
) -> list[str]:
    refs = [
        f"collector_event:{int(event.get('sequence') or route.event_sequence)}",
        f"route:{route.route_id}",
    ]
    if decision is not None:
        refs.append(f"reflex_decision:{decision.decision_id}")
    if boundary is not None and boundary.get("boundary_id"):
        refs.append(f"context_boundary:{boundary['boundary_id']}")
    return refs


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_loads_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    if any(str(row[1]) == column for row in rows):
        return
    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
