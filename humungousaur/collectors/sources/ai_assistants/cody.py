from __future__ import annotations

from .common import AiAssistantAppCollector


CODY_COLLECTOR = AiAssistantAppCollector(
    assistant="cody",
    display_name="Cody",
    provider="sourcegraph",
    surfaces=("ide_extension", "browser_app"),
    description="Cody chat, prompt, response, file-context, code suggestion, and model/tool error metadata.",
)
