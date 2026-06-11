from __future__ import annotations

from .common import PlanningWebhookCollector


JIRA_COLLECTOR = PlanningWebhookCollector(
    provider_id="jira",
    app="jira",
    description="Accepts Jira webhook and browser-extension issue, sprint, board, and project events.",
    source_channel="jira_webhook+browser_extension",
)

