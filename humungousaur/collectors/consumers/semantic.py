from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.cognition.semantic_events import record_attention_batch_semantics
from humungousaur.memory.event_store import EventStore

from ..attention_compaction import compact_attention_event
from ..envelope import CollectorEventEnvelope
from ..event_log import CollectorEventLog

semantic_consumer_name = "semantic_events"


class SemanticEventConsumer:
    """Turns compact attention batches into semantic events and action candidates."""

    def __init__(self, event_log: CollectorEventLog | None = None) -> None:
        self.event_log = event_log

    def consume_attention_batch(self, config: AgentConfig, attention_batch: dict[str, Any]) -> dict[str, Any]:
        return record_attention_batch_semantics(config, attention_batch)

    def consume(self, config: AgentConfig, *, limit: int = 200) -> dict[str, Any]:
        if self.event_log is None:
            return {"consumer": semantic_consumer_name, "mirrored": 0, "last_sequence": 0, "reason": "no event log"}
        events = self.event_log.read_batch(semantic_consumer_name, limit=limit)
        store = EventStore(config.memory_db_path)
        mirrored = 0
        last_sequence = 0
        for event in events:
            last_sequence = int(event["sequence"])
            envelope = CollectorEventEnvelope.from_payload(event)
            store.append(
                "collector_semantic_event",
                {
                    "sequence": last_sequence,
                    "event_id": envelope.event_id,
                    "collector": envelope.collector,
                    "source": envelope.source,
                    "stimulus_type": envelope.stimulus_type,
                    "occurred_at": envelope.occurred_at,
                    "privacy_tier": envelope.privacy_tier,
                    "summary": compact_attention_event(envelope.to_collector_event()),
                },
            )
            mirrored += 1
        if last_sequence:
            self.event_log.ack(semantic_consumer_name, last_sequence)
        return {"consumer": semantic_consumer_name, "mirrored": mirrored, "last_sequence": last_sequence}
