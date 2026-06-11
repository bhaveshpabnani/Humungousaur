from __future__ import annotations

from .common import PlanningWebhookCollector


LINEAR_COLLECTOR = PlanningWebhookCollector(
    provider_id="linear",
    app="linear",
    description="Accepts Linear webhook and browser-extension issue, cycle, and project events.",
    source_channel="linear_webhook+browser_extension",
)

