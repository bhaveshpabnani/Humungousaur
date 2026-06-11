from __future__ import annotations

from typing import Any

from humungousaur.config import AgentConfig
from humungousaur.memory.event_store import EventStore

from ..envelope import CollectorEventEnvelope
from ..event_log import CollectorEventLog


memory_consumer_name = "memory"


class MemoryMirrorConsumer:
    """Mirrors accepted collector events into the existing local memory surface."""

    def __init__(self, event_log: CollectorEventLog) -> None:
        self.event_log = event_log

    def consume(self, config: AgentConfig, *, limit: int = 200) -> dict[str, Any]:
        events = self.event_log.read_batch(memory_consumer_name, limit=limit)
        mirrored = 0
        last_sequence = 0
        store = EventStore(config.memory_db_path)
        for event in events:
            last_sequence = int(event["sequence"])
            envelope = CollectorEventEnvelope.from_payload(event)
            store.append("collector_stimulus", envelope.to_memory_payload())
            mirrored += 1
        if last_sequence:
            self.event_log.ack(memory_consumer_name, last_sequence)
        return {"consumer": memory_consumer_name, "mirrored": mirrored, "last_sequence": last_sequence}
