from __future__ import annotations

from typing import Any

from .chatgpt import CHATGPT_COLLECTOR
from .claude import CLAUDE_COLLECTOR
from .cody import CODY_COLLECTOR
from .copilot import COPILOT_COLLECTOR
from .cursor import CURSOR_COLLECTOR
from .gemini import GEMINI_COLLECTOR
from .local_llm import LOCAL_LLM_COLLECTOR


AI_ASSISTANT_APP_COLLECTORS: tuple[Any, ...] = (
    CHATGPT_COLLECTOR,
    CLAUDE_COLLECTOR,
    GEMINI_COLLECTOR,
    COPILOT_COLLECTOR,
    CURSOR_COLLECTOR,
    CODY_COLLECTOR,
    LOCAL_LLM_COLLECTOR,
)


def ai_assistant_collector_status_records() -> list[dict[str, Any]]:
    return [collector.status_record() for collector in AI_ASSISTANT_APP_COLLECTORS]


__all__ = ["AI_ASSISTANT_APP_COLLECTORS", "ai_assistant_collector_status_records"]
