from __future__ import annotations

from .common import AiAssistantAppCollector


GEMINI_COLLECTOR = AiAssistantAppCollector(
    assistant="gemini",
    display_name="Gemini",
    provider="google",
    surfaces=("browser_app", "workspace_side_panel", "mobile_handoff"),
    description="Gemini chat, prompt, response, file-context, tool-error, and workspace assistant metadata.",
)
