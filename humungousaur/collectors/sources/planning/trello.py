from __future__ import annotations

from .common import PlanningWebhookCollector


TRELLO_COLLECTOR = PlanningWebhookCollector(
    provider_id="trello",
    app="trello",
    description="Accepts Trello webhook and browser-extension card, list, board, and comment events.",
    source_channel="trello_webhook+browser_extension",
)

