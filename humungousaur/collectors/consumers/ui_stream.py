from __future__ import annotations

from typing import Any

from ..event_log import CollectorEventLog


ui_stream_consumer_name = "ui_stream"


class UIStreamConsumer:
    """Read-only consumer for dashboards and APIs that need recent event envelopes."""

    def __init__(self, event_log: CollectorEventLog) -> None:
        self.event_log = event_log

    def consume(self, *, limit: int = 200, retain: int = 100) -> dict[str, Any]:
        events = self.event_log.read_batch(ui_stream_consumer_name, limit=limit)
        state = self.event_log.consumer_state(ui_stream_consumer_name)
        recent = state.get("recent_events", [])
        if not isinstance(recent, list):
            recent = []
        last_sequence = 0
        for event in events:
            last_sequence = int(event["sequence"])
            recent.append(event)
        state["recent_events"] = recent[-max(1, min(int(retain or 100), 500)) :]
        if last_sequence:
            self.event_log.ack(ui_stream_consumer_name, last_sequence)
        self.event_log.save_consumer_state(ui_stream_consumer_name, state)
        return {"consumer": ui_stream_consumer_name, "streamed": len(events), "last_sequence": last_sequence}

    def recent(self, *, limit: int = 50) -> dict[str, Any]:
        state = self.event_log.consumer_state(ui_stream_consumer_name)
        recent = state.get("recent_events", [])
        if isinstance(recent, list) and recent:
            return {"consumer": ui_stream_consumer_name, "events": list(reversed(recent[-max(1, min(limit, 500)) :]))}
        return {"consumer": ui_stream_consumer_name, "events": self.event_log.tail(limit=limit)}
