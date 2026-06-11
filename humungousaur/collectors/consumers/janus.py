from __future__ import annotations

from typing import Any

from humungousaur.active_agent import ActiveEventRouter
from humungousaur.config import AgentConfig

from ..event_log import CollectorEventLog


active_agent_consumer_name = "active_agent"


class ActiveAgentConsumer:
    """Consumes collector events into active-agent routes, context, and reflex decisions."""

    def __init__(self, event_log: CollectorEventLog) -> None:
        self.event_log = event_log

    def consume(self, config: AgentConfig, *, limit: int = 200, run_agent: bool = True) -> dict[str, Any]:
        events = self.event_log.read_batch(active_agent_consumer_name, limit=limit)
        router = ActiveEventRouter(config, run_agent=run_agent)
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
                self.event_log.retry_later(active_agent_consumer_name, sequence, str(exc))
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
            self.event_log.ack(active_agent_consumer_name, last_sequence)
        return {
            "consumer": active_agent_consumer_name,
            "processed": processed,
            "last_sequence": last_sequence,
            "decisions": decisions,
            "submissions": submissions,
            "routes": routes[-20:],
        }
