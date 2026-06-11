from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig

from .models import DeepDiveResult, new_id
from .store import ActiveAgentStore


def execute_approved_deep_dive(config: AgentConfig, request_id: str, *, limit: int = 40) -> dict[str, Any]:
    """Execute an approval-gated metadata deep dive.

    This executor is intentionally metadata-first. It can gather recent collector
    event envelopes, active episode state, task context, corrections, and resume
    capsules. It does not fetch raw document bodies, message bodies, screenshots,
    transcripts, file contents, SQL results, or provider payloads.
    """

    normalized = config.normalized()
    store = ActiveAgentStore(normalized.active_agent_db_path)
    request = _find_request(store, request_id)
    if request is None:
        raise ValueError(f"deep-dive request not found: {request_id}")
    status = str(request.get("status") or "")
    if status != "approved":
        raise ValueError(f"deep-dive request must be approved before execution; current status is {status or '<empty>'}")
    store.update_deep_dive_status(request_id, status="executing", reason="Approved metadata deep dive started.")
    evidence = _collect_metadata_evidence(normalized, store, request, limit=limit)
    summary = _summarize_deep_dive(request, evidence)
    result = DeepDiveResult(
        result_id=new_id("deep_result"),
        request_id=request_id,
        episode_id=str(request.get("episode_id") or ""),
        status="completed",
        executor="local_metadata_deep_dive",
        summary=summary,
        evidence=evidence,
        safety_notes=[
            "Metadata-only deep dive executed after approval.",
            "Raw content, screenshots, transcripts, file bodies, message bodies, and provider payloads were not read.",
        ],
        evidence_refs=[f"deep_dive_request:{request_id}", *evidence.get("evidence_refs", [])][:40],
    )
    stored = store.record_deep_dive_result(result)
    updated_request = store.update_deep_dive_status(request_id, status="completed", reason=f"Deep dive result: {stored.result_id}")
    if result.episode_id:
        store.record_episode_link(
            source_episode_id=result.episode_id,
            target_episode_id=result.result_id,
            relation="deep_dive_result",
            reason=summary,
            evidence_refs=result.evidence_refs,
        )
    return {
        "deep_dive_request": updated_request,
        "deep_dive_result": {
            "result_id": stored.result_id,
            "request_id": stored.request_id,
            "episode_id": stored.episode_id,
            "status": stored.status,
            "executor": stored.executor,
            "summary": stored.summary,
            "evidence": stored.evidence,
            "safety_notes": stored.safety_notes,
            "evidence_refs": stored.evidence_refs,
            "created_at": stored.created_at,
        },
        "status": store.status(limit=10),
    }


def _find_request(store: ActiveAgentStore, request_id: str) -> dict[str, Any] | None:
    for request in store.deep_dive_requests(limit=200):
        if str(request.get("request_id") or "") == str(request_id or ""):
            return request
    return None


def _collect_metadata_evidence(
    config: AgentConfig,
    store: ActiveAgentStore,
    request: dict[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    from humungousaur.collectors.event_log import CollectorEventLog

    source = str(request.get("source") or "")
    episode_id = str(request.get("episode_id") or "")
    collector_events = CollectorEventLog(config.collector_events_db_path).query(
        limit=max(1, min(int(limit or 40), 100)) * (3 if source else 1),
    )
    raw_events = [
        event
        for event in collector_events
        if not source or str(event.get("source") or "") == source or str(event.get("collector") or "") == source
    ][: max(1, min(int(limit or 40), 100))]
    events = [_compact_collector_event(event) for event in raw_events]
    episode = store.episode(episode_id) if episode_id else None
    episode_events = store.episode_events(episode_id=episode_id, limit=20) if episode_id else []
    task_contexts = [
        item
        for item in store.task_contexts(limit=20)
        if not episode_id or str(item.get("episode_id") or "") == episode_id
    ][:8]
    evidence_refs = [f"collector_event:{event['sequence']}" for event in events if event.get("sequence")]
    if episode_id:
        evidence_refs.append(f"episode:{episode_id}")
    return {
        "request": {
            "request_id": request.get("request_id", ""),
            "episode_id": episode_id,
            "source": source,
            "requested_access": request.get("requested_access", ""),
            "privacy_tier": request.get("privacy_tier", ""),
        },
        "collector_events": events,
        "episode": episode or {},
        "episode_events": episode_events[:20],
        "task_contexts": task_contexts,
        "resume_capsules": store.resume_capsules(limit=6),
        "recent_corrections": store.corrections(limit=8),
        "evidence_refs": evidence_refs[:40],
        "raw_content_included": False,
    }


def _compact_collector_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence": int(event.get("sequence") or 0),
        "event_id": str(event.get("event_id") or ""),
        "collector": str(event.get("collector") or ""),
        "source": str(event.get("source") or ""),
        "stimulus_type": str(event.get("stimulus_type") or ""),
        "privacy_tier": str(event.get("privacy_tier") or ""),
        "occurred_at": str(event.get("occurred_at") or ""),
        "text": str(event.get("text") or "")[:240],
        "metadata_keys": sorted((event.get("metadata") or {}).keys())[:40] if isinstance(event.get("metadata"), dict) else [],
        "payload_keys": sorted((event.get("payload") or {}).keys())[:40] if isinstance(event.get("payload"), dict) else [],
        "redaction": event.get("redaction") if isinstance(event.get("redaction"), dict) else {},
    }


def _summarize_deep_dive(request: dict[str, Any], evidence: dict[str, Any]) -> str:
    event_count = len(evidence.get("collector_events", []))
    context_count = len(evidence.get("task_contexts", []))
    source = str(request.get("source") or "active-agent state")
    access = str(request.get("requested_access") or "metadata")
    return (
        f"Approved metadata deep dive for {source} gathered {event_count} recent collector event(s) "
        f"and {context_count} related task context record(s) for requested access '{access}'."
    )[:1_000]
