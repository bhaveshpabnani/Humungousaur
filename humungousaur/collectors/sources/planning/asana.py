from __future__ import annotations

from .common import PlanningWebhookCollector


ASANA_COLLECTOR = PlanningWebhookCollector(
    provider_id="asana",
    app="asana",
    description="Accepts Asana webhook and browser-extension task, story, section, and project events.",
    source_channel="asana_webhook+browser_extension",
)

