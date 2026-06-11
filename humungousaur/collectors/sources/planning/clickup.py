from __future__ import annotations

from .common import PlanningWebhookCollector


CLICKUP_COLLECTOR = PlanningWebhookCollector(
    provider_id="clickup",
    app="clickup",
    description="Accepts ClickUp webhook and browser-extension task, list, sprint, and priority events.",
    source_channel="clickup_webhook+browser_extension",
)

