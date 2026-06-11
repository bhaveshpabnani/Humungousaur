from __future__ import annotations

from typing import Any

from humungousaur.janus import JanusEventRouter
from humungousaur.config import AgentConfig

from ..event_log import CollectorEventLog


janus_consumer_name = "janus"


class JanusConsumer:
    """Consumes collector events into janus routes, context, and reflex decisions."""

    def __init__(self, event_log: CollectorEventLog) -> None:
        self.event_log = event_log

    def consume(self, config: AgentConfig, *, limit: int = 200, run_agent: bool = True) -> dict[str, Any]:
        events = self.event_log.read_batch(janus_consumer_name, limit=limit)
        router = JanusEventRouter(config, run_agent=run_agent)
        processed = 0
        last_sequence = 0
        decisions = 0
        submissions = 0
        routes: list[dict[str, Any]] = []
        for event in events:
            sequence = int(event["sequence"])
            try:
                result = router.handle_event(event)
            except Exception as exc:
                self.event_log.retry_later(janus_consumer_name, sequence, str(exc))
                break
            last_sequence = sequence
            processed += 1
            route = result.get("route")
            if isinstance(route, dict):
                routes.append(route)
            if isinstance(result.get("decision"), dict):
                decisions += 1
            if isinstance(result.get("submission"), dict):
                submissions += 1
        if last_sequence:
            self.event_log.ack(janus_consumer_name, last_sequence)
        return {
            "consumer": janus_consumer_name,
            "processed": processed,
            "last_sequence": last_sequence,
            "decisions": decisions,
            "submissions": submissions,
            "routes": routes[-20:],
        }
