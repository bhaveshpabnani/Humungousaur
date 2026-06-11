from __future__ import annotations

import hashlib
import time
from typing import Any

from humungousaur.active_agent.store import ActiveAgentStore
from humungousaur.config import AgentConfig
from humungousaur.interaction import InteractionHarness, harness_result_to_dict
from humungousaur.memory.event_store import EventStore

from ..attention_compaction import attention_batch_payload, compact_attention_event
from ..envelope import CollectorEventEnvelope
from ..event_log import CollectorEventLog
from ..models import CollectorProfile
from .semantic import SemanticEventConsumer


attention_consumer_name = "attention_batch"


class AttentionBatchConsumer:
    """Builds compact LLM-safe attention batches from durable collector events."""

    def __init__(self, event_log: CollectorEventLog) -> None:
        self.event_log = event_log
        self.semantic_consumer = SemanticEventConsumer()

    def consume(self, config: AgentConfig, profile: CollectorProfile, *, force: bool = False, limit: int = 500) -> dict[str, Any]:
        consumer_state = self.event_log.consumer_state(attention_consumer_name)
        pending = consumer_state.get("pending_attention_events", [])
        if not isinstance(pending, list):
            pending = []

        events = self.event_log.read_batch(attention_consumer_name, limit=limit)
        active_store = ActiveAgentStore(config.normalized().active_agent_db_path)
        last_sequence = 0
        accepted = 0
        for event in events:
            last_sequence = int(event["sequence"])
            envelope = CollectorEventEnvelope.from_payload(event)
            muted_scope = active_store.active_muted_scope_for(event)
            if muted_scope is not None and muted_scope.do_not_send_to_llm:
                continue
            collector_event = envelope.to_collector_event()
            if not _llm_eligible_event(collector_event.collector, collector_event.source, collector_event.stimulus_type):
                continue
            pending.append(compact_attention_event(collector_event))
            accepted += 1
        if last_sequence:
            self.event_log.ack(attention_consumer_name, last_sequence)

        consumer_state["pending_attention_events"] = pending[-500:]
        attention_batch = _maybe_build_attention_batch(consumer_state, profile, force=force)
        result: dict[str, Any] = {
            "consumer": attention_consumer_name,
            "read": len(events),
            "accepted": accepted,
            "last_sequence": last_sequence,
            "attention_batch": None,
            "semantic_result": {},
            "submission": None,
        }
        if attention_batch is None:
            self.event_log.save_consumer_state(attention_consumer_name, consumer_state)
            return result

        EventStore(config.memory_db_path).append("attention_batch", attention_batch)
        semantic_result = self.semantic_consumer.consume_attention_batch(config, attention_batch)
        harness = InteractionHarness(config).handle(_attention_stimulus(attention_batch), response_mode=profile.response_mode)
        submission = {
            "collector": "attention_batch",
            "stimulus_type": "attention_batch",
            "decision": harness_result_to_dict(harness).get("decision", {}),
            "run_id": harness.run.run_id if harness.run is not None else "",
            "batch_id": attention_batch["batch_id"],
        }
        self.event_log.save_consumer_state(attention_consumer_name, consumer_state)
        result.update({"attention_batch": attention_batch, "semantic_result": semantic_result, "submission": submission})
        return result


def _maybe_build_attention_batch(state: dict[str, Any], profile: CollectorProfile, *, force: bool) -> dict[str, Any] | None:
    pending = state.get("pending_attention_events", [])
    if not isinstance(pending, list) or not pending:
        return None
    now = time.time()
    first_at = _parse_time(pending[0].get("occurred_at")) or now
    last_attention_at = float(state.get("last_attention_batch_at", 0.0) or 0.0)
    if not force and now - first_at < profile.batch_seconds:
        return None
    if not force and last_attention_at > 0.0 and now - last_attention_at < profile.llm_attention_interval_seconds:
        return None
    batch = attention_batch_payload(pending, profile)
    state["pending_attention_events"] = []
    state["last_attention_batch_at"] = now
    return batch


def _attention_stimulus(batch: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": str(batch.get("text", "")),
        "source": "activity",
        "metadata": {
            "collector": "attention_batch",
            "stimulus_type": "attention_batch",
            "privacy_mode": str(batch.get("privacy_mode", "privacy_first")),
            "event_count": int(batch.get("event_count") or 0),
            "collector_counts": batch.get("collector_counts", {}),
            "events": batch.get("events", []),
            "payload": {key: value for key, value in batch.items() if key != "events"},
        },
        "stimulus_id": str(batch.get("batch_id", "")) or f"attention-{hashlib.sha256(str(batch).encode('utf-8')).hexdigest()[:12]}",
        "occurred_at": str(batch.get("occurred_at", "")),
    }


def _parse_time(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _llm_eligible_event(collector: str, source: str, stimulus_type: str) -> bool:
    if collector == "audio_activity":
        return False
    if source == "audio_transcript" and stimulus_type == "voice_activity_detected":
        return False
    return True
