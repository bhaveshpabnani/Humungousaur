from __future__ import annotations

from .common import AiAssistantAppCollector


COPILOT_COLLECTOR = AiAssistantAppCollector(
    assistant="copilot",
    display_name="Copilot",
    provider="microsoft_github",
    surfaces=("browser_app", "office_side_panel", "ide_extension"),
    description="Copilot chat, prompt, response, file-context, code suggestion, and model/tool error metadata.",
)
