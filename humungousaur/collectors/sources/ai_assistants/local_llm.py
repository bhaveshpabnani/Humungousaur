from __future__ import annotations

from .common import AiAssistantAppCollector


LOCAL_LLM_COLLECTOR = AiAssistantAppCollector(
    assistant="local_llm",
    display_name="Local LLM tools",
    provider="local",
    surfaces=("desktop_app", "cli", "local_api", "ide_extension"),
    description="Ollama, LM Studio, llama.cpp, and OpenAI-compatible local assistant prompt, response, and error metadata.",
    source_channel="local_tool_bridge_or_app_plugin",
)
