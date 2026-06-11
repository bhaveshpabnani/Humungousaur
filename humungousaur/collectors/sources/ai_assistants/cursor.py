from __future__ import annotations

from .common import AiAssistantAppCollector


CURSOR_COLLECTOR = AiAssistantAppCollector(
    assistant="cursor",
    display_name="Cursor",
    provider="cursor",
    surfaces=("ide_extension", "desktop_app"),
    description="Cursor chat, prompt, response, file-context, code suggestion, and model/tool error metadata.",
)
