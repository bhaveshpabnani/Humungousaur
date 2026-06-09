#!/usr/bin/env python3
"""Source-level parity checks for Windows and macOS desktop shells."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_API = ROOT / "apps/windows/Humungousaur.App/Services/AgentApiClient.cs"
WINDOWS_DEFAULTS = ROOT / "apps/windows/Humungousaur.App/Models/AppRuntimeDefaults.cs"
MACOS_API = ROOT / "apps/macos/Sources/AgentAPIClient.swift"
WINDOWS_PROCESS = ROOT / "apps/windows/Humungousaur.App/Services/LocalAgentProcess.cs"
MACOS_PROCESS = ROOT / "apps/macos/Sources/LocalAgentProcess.swift"
WINDOWS_MAIN_WINDOW = ROOT / "apps/windows/Humungousaur.App/MainWindow.xaml"
WINDOWS_MAIN_CODE = ROOT / "apps/windows/Humungousaur.App/MainWindow.xaml.cs"
MACOS_ROOT = ROOT / "apps/macos/Sources/RootView.swift"
MACOS_SIDEBAR = ROOT / "apps/macos/Sources/SidebarView.swift"
MACOS_DESIGN = ROOT / "apps/macos/Sources/DesignSystem.swift"
MACOS_CHAT = ROOT / "apps/macos/Sources/ChatView.swift"
MACOS_TOOLS_CHANNELS = ROOT / "apps/macos/Sources/ToolsChannelsViews.swift"
MACOS_RUNS_APPROVALS = ROOT / "apps/macos/Sources/RunsApprovalsViews.swift"
MACOS_VOICE_AUTONOMY_SETTINGS = ROOT / "apps/macos/Sources/VoiceAutonomySettingsViews.swift"


REQUIRED_API_SURFACES: dict[str, tuple[str, ...]] = {
    "health": ("health",),
    "system status": ("system/status",),
    "tool catalog": ("tools",),
    "runs list": ("runs?limit",),
    "run timeline": ("runs/", "timeline?limit"),
    "run cancellation": ("runs/", "/cancel"),
    "pending approvals": ("approvals?status", "limit"),
    "approval approve": ("approvals/", "/approve"),
    "approval reject": ("approvals/", "/reject"),
    "chat/stimulus": ("stimuli",),
    "voice status": ("voice/status",),
    "autonomous status": ("autonomous/status?limit",),
    "autonomous cycles": ("autonomous/cycles",),
    "channels catalog": ("channels",),
    "channel setup status": ("channels/status",),
    "channel setup doctor": ("channels/doctor",),
    "channel setup requirements": ("channels/requirements?channel_id=",),
    "channel smoke": ("channels/smoke",),
    "channel listeners": ("channels/listeners",),
    "channel listener tick": ("channels/listeners/tick",),
    "channel setup save": ("channels/setup",),
    "channel inbound preview": ("channels/inbound",),
    "channel outbound prepare": ("channels/message/prepare",),
    "channel outbound send": ("channels/message/send",),
    "channel outbox": ("channels/outbox",),
}

REQUIRED_SECRET_NAMES = {
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "XAI_API_KEY",
    "OLLAMA_API_KEY",
    "LOCAL_LLM_API_KEY",
    "DEEPGRAM_API_KEY",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_VOICE_ID",
    "ELEVENLABS_MODEL_ID",
}

REQUIRED_MODEL_PROVIDERS = {
    "openai",
    "groq",
    "grok",
    "ollama",
    "local-openai",
}

REQUIRED_UI_SURFACES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "chat console": (
        ("AssistantPage", "PromptBox", "StimulusSourceBox", "ResponseModeBox", "SendButton"),
        ("ChatView()", "ComposerView", "Message Assistant", "voiceInputMode", "Send"),
    ),
    "runtime process controls": (
        ("StartAgentButton", "StopAgentButton", "RuntimeSummaryText", "ProcessLog"),
        ("toggleAgentProcess", "Start Agent", "Stop Agent", "Local daemon"),
    ),
    "runs and approvals": (
        ("RuntimePage", "RuntimeRunList", "CancelRunButton_Click", "ApprovalList", "ApproveSelectedButton_Click", "RejectSelectedButton_Click"),
        ("RunsView()", "ApprovalsView()", "cancelSelectedRun", "approveSelected", "rejectSelected", "Technical action details"),
    ),
    "tool catalog": (
        ("ToolsPage", "ToolSearchBox", "ToolGroupList", "ToolList", "RequiresApproval"),
        ("ToolsView()", "Search capabilities", "filteredTools", "requiresApproval", "RiskBadge"),
    ),
    "channel setup and diagnostics": (
        ("ChannelsPage", "ChannelRequirementText", "RunChannelDoctorButton_Click", "RunChannelSmokeButton_Click", "SaveChannelButton_Click"),
        ("ChannelsView()", "Setup Guide", "runChannelDoctor", "runChannelSmoke", "saveChannelSetup"),
    ),
    "channel messaging and polling": (
        ("PrepareOutboundButton_Click", "SendOutboundButton_Click", "TickChannelButton_Click", "TickAllChannelsButton_Click", "ContinuousChannelListenSwitch"),
        ("prepareOutbound", "sendOutbound", "tickChannel", "tickAllChannels", "Keep checking"),
    ),
    "voice setup and test": (
        ("VoicePage", "DeepgramApiKeyBox", "ElevenLabsApiKeyBox", "TtsProviderBox", "SpeakTestButton_Click"),
        ("VoiceView()", "Listening API key", "Speaking API key", "Speaking voice", "Test Voice"),
    ),
    "autonomy controls": (
        ("AutonomyPage", "AllowInitiativeSwitch", "MaxCyclesBox", "ContinuousLoopSwitch", "RunCycleButton_Click"),
        ("AutonomyView()", "Allow initiative", "Work steps", "runAutonomyCycle", "Technical autonomy status"),
    ),
    "settings and model configuration": (
        ("SettingsPage", "WorkspacePathBox", "PythonPathBox", "ModelProviderBox", "ModelApiKeyBox", "ApproveHighRiskSwitch"),
        ("SettingsView()", "Project folder", "Python path", "Provider", "API key", "Allow protected actions without asking"),
    ),
}

REQUIRED_MACOS_FILES = [
    "apps/macos/Sources/AgentAPIClient.swift",
    "apps/macos/Sources/AppSettings.swift",
    "apps/macos/Sources/AppViewModel.swift",
    "apps/macos/Sources/KeychainStore.swift",
    "apps/macos/Sources/LocalAgentProcess.swift",
    "apps/macos/Sources/ToolsChannelsViews.swift",
    "apps/macos/Sources/RunsApprovalsViews.swift",
    "apps/macos/Sources/VoiceAutonomySettingsViews.swift",
]

REQUIRED_WINDOWS_FILES = [
    "apps/windows/Humungousaur.App/Services/AgentApiClient.cs",
    "apps/windows/Humungousaur.App/Models/AppSettings.cs",
    "apps/windows/Humungousaur.App/Services/AppSettingsStore.cs",
    "apps/windows/Humungousaur.App/Services/LocalAgentProcess.cs",
    "apps/windows/Humungousaur.App/MainWindow.xaml",
    "apps/windows/Humungousaur.App/MainWindow.xaml.cs",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def has_all(text: str, needles: tuple[str, ...]) -> bool:
    return all(needle in text for needle in needles)


def main() -> int:
    errors: list[str] = []
    passed: list[str] = []

    for rel in REQUIRED_MACOS_FILES + REQUIRED_WINDOWS_FILES:
        path = ROOT / rel
        if path.is_file():
            passed.append(f"required desktop source exists: {rel}")
        else:
            errors.append(f"missing required desktop source: {rel}")

    if errors:
        return finish(passed, errors)

    windows_api = read(WINDOWS_API)
    macos_api = read(MACOS_API)
    for name, route_parts in REQUIRED_API_SURFACES.items():
        windows_ok = has_all(windows_api, route_parts)
        macos_ok = has_all(macos_api, route_parts)
        if windows_ok and macos_ok:
            passed.append(f"API parity surface present: {name}")
        else:
            if not windows_ok:
                errors.append(f"Windows API client is missing route surface '{name}' via {route_parts}")
            if not macos_ok:
                errors.append(f"macOS API client is missing route surface '{name}' via {route_parts}")

    windows_process = read(WINDOWS_PROCESS)
    macos_process = read(MACOS_PROCESS)
    windows_defaults = read(WINDOWS_DEFAULTS)
    combined_windows = windows_api + "\n" + windows_process + "\n" + windows_defaults
    combined_macos = macos_api + "\n" + macos_process
    for secret_name in sorted(REQUIRED_SECRET_NAMES):
        if secret_name in combined_windows and secret_name in combined_macos:
            passed.append(f"runtime secret parity present: {secret_name}")
        else:
            if secret_name not in combined_windows:
                errors.append(f"Windows desktop runtime does not plumb {secret_name}")
            if secret_name not in combined_macos:
                errors.append(f"macOS desktop runtime does not plumb {secret_name}")

    windows_ui = "\n".join(read(path) for path in [WINDOWS_MAIN_WINDOW, WINDOWS_MAIN_CODE])
    macos_ui = "\n".join(
        read(path)
        for path in [
            MACOS_ROOT,
            MACOS_SIDEBAR,
            MACOS_DESIGN,
            MACOS_CHAT,
            MACOS_TOOLS_CHANNELS,
            MACOS_RUNS_APPROVALS,
            MACOS_VOICE_AUTONOMY_SETTINGS,
        ]
    )
    for provider in sorted(REQUIRED_MODEL_PROVIDERS):
        if f'Tag="{provider}"' in windows_ui and f'tag("{provider}")' in macos_ui:
            passed.append(f"model provider UI parity present: {provider}")
        else:
            if f'Tag="{provider}"' not in windows_ui:
                errors.append(f"Windows desktop settings UI does not expose model provider {provider}")
            if f'tag("{provider}")' not in macos_ui:
                errors.append(f"macOS desktop settings UI does not expose model provider {provider}")

    for surface_name, (windows_needles, macos_needles) in REQUIRED_UI_SURFACES.items():
        windows_ok = has_all(windows_ui, windows_needles)
        macos_ok = has_all(macos_ui, macos_needles)
        if windows_ok and macos_ok:
            passed.append(f"desktop UI parity surface present: {surface_name}")
        else:
            if not windows_ok:
                missing = [needle for needle in windows_needles if needle not in windows_ui]
                errors.append(f"Windows desktop UI is missing surface '{surface_name}' markers {missing}")
            if not macos_ok:
                missing = [needle for needle in macos_needles if needle not in macos_ui]
                errors.append(f"macOS desktop UI is missing surface '{surface_name}' markers {missing}")

    for source_name in ["windows_app", "macos_app"]:
        source_text = windows_api if source_name == "windows_app" else macos_api
        if source_name in source_text:
            passed.append(f"channel metadata source marker present: {source_name}")
        else:
            errors.append(f"missing channel metadata source marker: {source_name}")

    return finish(passed, errors)


def finish(passed: list[str], errors: list[str]) -> int:
    for message in passed:
        print(f"PASS {message}")
    for message in errors:
        print(f"FAIL {message}")
    print(f"\nDesktop parity: {len(passed)} passed, {len(errors)} failures")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
