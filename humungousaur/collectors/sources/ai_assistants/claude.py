from __future__ import annotations

from .common import AiAssistantAppCollector


CLAUDE_COLLECTOR = AiAssistantAppCollector(
    assistant="claude",
    display_name="Claude",
    provider="anthropic",
    surfaces=("browser_app", "desktop_app"),
    description="Claude chat, prompt, response, file-context, tool-error, and artifact metadata.",
)
