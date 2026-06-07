from .base import Tool
from .activity import default_activity_tools
from .analysis import default_analysis_tools
from .browser import default_browser_tools
from .capabilities import default_capability_tools
from .channels import default_channel_tools
from .code import default_code_tools
from .codex import default_codex_tools
from .commerce import default_commerce_tools
from .content import default_content_tools
from .conversation import default_conversation_tools
from .cognition import default_cognition_tools
from .design import default_design_tools
from .external import default_external_tools
from .files import default_tools as default_file_tools
from .memory import default_memory_tools
from .media import default_media_tools
from .office import default_office_tools
from .os_control import default_os_tools
from .personal import default_personal_tools
from .plugins import default_plugin_tools
from .productivity import default_productivity_tools
from .research import default_research_tools
from .skills import default_skill_tools
from .system import default_system_tools
from .travel import default_travel_tools
from .visuals import default_visual_tools
from .voice import default_voice_tools
from .writing import default_writing_tools
from .workflow import default_workflow_tools

__all__ = ["Tool", "default_tools"]


class _ToolAlias(Tool):
    def __init__(self, alias: str, target: Tool) -> None:
        super().__init__(
            name=alias,
            description=f"Alias for {target.name}: {target.description}",
            risk_level=target.risk_level,
            requires_approval=target.requires_approval,
            input_schema=target.input_schema,
            capability_group=target.capability_group,
        )
        self._target = target

    def execute(self, tool_input, config):
        result = self._target.execute(tool_input, config)
        result.tool_name = self.name
        return result


def default_tools(config=None) -> dict[str, Tool]:
    tools = default_file_tools()
    tools.update(default_activity_tools())
    tools.update(default_analysis_tools())
    tools.update(default_browser_tools())
    tools.update(default_capability_tools())
    tools.update(default_channel_tools())
    tools.update(default_code_tools())
    tools.update(default_codex_tools())
    tools.update(default_commerce_tools())
    tools.update(default_content_tools())
    tools.update(default_conversation_tools())
    tools.update(default_cognition_tools())
    tools.update(default_design_tools())
    tools.update(default_external_tools())
    tools.update(default_system_tools())
    tools.update(default_os_tools())
    tools.update(default_travel_tools())
    tools.update(default_visual_tools())
    tools.update(default_voice_tools())
    tools.update(default_writing_tools())
    tools.update(default_workflow_tools())
    tools.update(default_memory_tools())
    tools.update(default_media_tools())
    tools.update(default_office_tools())
    tools.update(default_personal_tools())
    tools.update(default_research_tools())
    tools.update(default_skill_tools())
    tools.update(default_plugin_tools(config, set(tools)))
    tools.update(default_productivity_tools())
    _add_aliases(
        tools,
        {
            "fetch_webpage": "fetch_web_page",
            "research_webpages": "research_web_pages",
            "active_window": "os_active_window",
        },
    )
    return tools


def _add_aliases(tools: dict[str, Tool], aliases: dict[str, str]) -> None:
    for alias, target_name in aliases.items():
        target = tools.get(target_name)
        if target is not None and alias not in tools:
            tools[alias] = _ToolAlias(alias, target)
