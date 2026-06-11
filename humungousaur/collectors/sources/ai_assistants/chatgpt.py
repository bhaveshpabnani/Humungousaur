from __future__ import annotations

from .common import AiAssistantAppCollector


CHATGPT_COLLECTOR = AiAssistantAppCollector(
    assistant="chatgpt",
    display_name="ChatGPT",
    provider="openai",
    surfaces=("browser_app", "desktop_app", "mobile_handoff"),
    description="ChatGPT chat, prompt, response, file-context, tool-error, and export metadata.",
)
