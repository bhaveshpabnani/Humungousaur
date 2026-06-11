from __future__ import annotations

from .common import PlanningWebhookCollector


MONDAY_COLLECTOR = PlanningWebhookCollector(
    provider_id="monday",
    app="monday",
    description="Accepts Monday.com webhook and browser-extension item, board, column, and update events.",
    source_channel="monday_webhook+browser_extension",
)

