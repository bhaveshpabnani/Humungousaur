from __future__ import annotations

from typing import Any

from ..event_log import CollectorEventLog


autonomous_consumer_name = "autonomous_trigger"


class AutonomousTriggerConsumer:
    """Tracks collector events seen by autonomy without deciding actions itself."""

    def __init__(self, event_log: CollectorEventLog) -> None:
        self.event_log = event_log

    def consume(self, *, limit: int = 200) -> dict[str, Any]:
        events = self.event_log.read_batch(autonomous_consumer_name, limit=limit)
        last_sequence = int(events[-1]["sequence"]) if events else 0
        if last_sequence:
            self.event_log.ack(autonomous_consumer_name, last_sequence)
        return {"consumer": autonomous_consumer_name, "observed": len(events), "last_sequence": last_sequence}
