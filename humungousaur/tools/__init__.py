from .base import Tool
from .activity import default_activity_tools
from .browser import default_browser_tools
from .capabilities import default_capability_tools
from .channels import default_channel_tools
from .code import default_code_tools
from .codex import default_codex_tools
from .cognition import default_cognition_tools
from .external import default_external_tools
from .files import default_tools as default_file_tools
from .memory import default_memory_tools
from .os_control import default_os_tools
from .plugins import default_plugin_tools
from .skills import default_skill_tools
from .system import default_system_tools
from .voice import default_voice_tools
from .workflow import default_workflow_tools

__all__ = ["Tool", "default_tools"]


def default_tools(config=None) -> dict[str, Tool]:
    tools = default_file_tools()
    tools.update(default_activity_tools())
    tools.update(default_browser_tools())
    tools.update(default_capability_tools())
    tools.update(default_channel_tools())
    tools.update(default_code_tools())
    tools.update(default_codex_tools())
    tools.update(default_cognition_tools())
    tools.update(default_external_tools())
    tools.update(default_system_tools())
    tools.update(default_os_tools())
    tools.update(default_voice_tools())
    tools.update(default_workflow_tools())
    tools.update(default_memory_tools())
    tools.update(default_skill_tools())
    tools.update(default_plugin_tools(config, set(tools)))
    return tools
