from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/connectors/callback"


@dataclass(frozen=True, slots=True)
class ConnectorProviderManifest:
    provider_id: str
    display_name: str
    category: str
    api_base_url: str
    default_scopes: tuple[str, ...] = ()
    workspace_apps: tuple[str, ...] = ()
    tool_hints: tuple[str, ...] = ()
    auth_url: str = ""
    token_url: str = ""
    auth_type: str = "oauth2_authorization_code"
    credential_fields: tuple[str, ...] = ("client_id", "client_secret")
    oauth_management: str = "managed_or_byo"
    advanced_client_config: bool = True
    supports_pkce: bool = True
    docs_url: str = ""
    icon: str = ""
    brand_color: str = ""
    logo_asset: str = ""
    logo_url: str = ""
    api_auth_scheme: str = "bearer"
    supported_connection_types: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["default_scopes"] = list(self.default_scopes)
        record["workspace_apps"] = list(self.workspace_apps)
        record["tool_hints"] = list(self.tool_hints)
        record["credential_fields"] = list(self.credential_fields)
        record["supported_connection_types"] = list(self.supported_connection_types or (self.auth_type,))
        record["advanced_client_config"] = bool(self.advanced_client_config)
        record["icon"] = self.icon or connector_icon(self.provider_id, self.category)
        record["brand_color"] = self.brand_color or connector_brand_color(self.provider_id, self.category)
        record["logo_asset"] = self.logo_asset or connector_logo_asset(self.provider_id)
        return record


@dataclass(frozen=True, slots=True)
class ConnectorClientConfig:
    provider_id: str
    client_id: str
    redirect_uri: str = DEFAULT_REDIRECT_URI
    updated_at: str = ""
    client_secret_ref: str = ""

    def public_record(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "client_id": redact_secret(self.client_id),
            "redirect_uri": self.redirect_uri,
            "updated_at": self.updated_at,
            "has_client_secret": bool(self.client_secret_ref),
        }


@dataclass(frozen=True, slots=True)
class ConnectorTokenStatus:
    provider_id: str
    connected: bool
    connected_at: str = ""
    expires_at: int = 0
    scopes: tuple[str, ...] = ()
    access_token_ref: str = ""
    refresh_token_ref: str = ""
    bot_access_token_ref: str = ""
    token_type: str = ""

    @property
    def has_refresh_token(self) -> bool:
        return bool(self.refresh_token_ref)

    def public_record(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "connected": self.connected,
            "connected_at": self.connected_at,
            "expires_at": self.expires_at,
            "has_refresh_token": self.has_refresh_token,
            "scopes": list(self.scopes),
            "token_type": self.token_type,
        }


@dataclass(frozen=True, slots=True)
class ConnectorOAuthState:
    state: str
    provider_id: str
    redirect_uri: str
    scopes: tuple[str, ...]
    created_at: str
    created_at_epoch: float
    code_verifier: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "provider_id": self.provider_id,
            "redirect_uri": self.redirect_uri,
            "scopes": list(self.scopes),
            "created_at": self.created_at,
            "created_at_epoch": self.created_at_epoch,
            "code_verifier": self.code_verifier,
        }


@dataclass(frozen=True, slots=True)
class ConnectorOperationRequest:
    provider_id: str
    operation: str
    method: str = "GET"
    path: str = ""
    query: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    required_scopes: tuple[str, ...] = ()
    reason: str = ""


def redact_secret(value: str) -> str:
    text = str(value or "")
    if len(text) <= 8:
        return "***" if text else ""
    return f"{text[:4]}...{text[-4:]}"


def connector_icon(provider_id: str, category: str) -> str:
    provider_icons = {
        "google_workspace": "square.grid.3x3.fill",
        "microsoft_365": "window.horizontal",
        "slack": "message.badge.filled.fill",
        "linear": "checklist",
        "github": "chevron.left.forwardslash.chevron.right",
        "notion": "doc.text",
        "airtable": "tablecells",
        "apple_local": "apple.logo",
        "browser_use": "safari",
        "mcp": "point.3.connected.trianglepath.dotted",
        "onepassword": "key.fill",
        "screenpipe": "record.circle",
        "shopify": "bag.fill",
        "spotify": "music.note",
        "figma": "paintpalette.fill",
        "canva": "paintbrush.pointed.fill",
        "zoom": "video.fill",
        "stripe": "creditcard.fill",
        "openai": "sparkles",
        "anthropic": "brain.head.profile",
        "ollama": "cpu",
        "vscode": "curlybraces.square",
        "xcode": "hammer.fill",
    }
    category_icons = {
        "workspace_suite": "rectangle.3.group",
        "communication": "bubble.left.and.bubble.right.fill",
        "planning": "checklist",
        "developer_platform": "chevron.left.forwardslash.chevron.right",
        "developer_tool": "terminal.fill",
        "business_data": "tablecells.fill",
        "knowledge_base": "doc.text.fill",
        "cloud_files": "folder.fill",
        "local_apps": "desktopcomputer",
        "browser": "safari.fill",
        "automation": "switch.2",
        "mlops": "cpu.fill",
        "tool_runtime": "point.3.connected.trianglepath.dotted",
        "credentials": "key.fill",
        "local_capture": "record.circle.fill",
        "commerce": "bag.fill",
        "media": "play.rectangle.fill",
        "observability": "waveform.path.ecg",
        "incident_management": "bell.badge.fill",
        "cloud": "cloud.fill",
        "design": "paintpalette.fill",
        "meetings": "video.fill",
        "crm": "person.2.fill",
        "support": "questionmark.bubble.fill",
        "finance": "banknote.fill",
        "marketing": "megaphone.fill",
        "data": "cylinder.split.1x2.fill",
        "analytics": "chart.bar.xaxis",
        "research": "magnifyingglass",
        "ai": "sparkles",
    }
    return provider_icons.get(provider_id, category_icons.get(category, "link.badge.plus"))


def connector_brand_color(provider_id: str, category: str) -> str:
    provider_colors = {
        "google_workspace": "#4285F4",
        "microsoft_365": "#0078D4",
        "slack": "#611F69",
        "linear": "#5E6AD2",
        "github": "#24292F",
        "notion": "#111111",
        "airtable": "#18BFFF",
        "apple_local": "#6E6E73",
        "browser_use": "#0A84FF",
        "mcp": "#6D5DFB",
        "onepassword": "#0094F5",
        "shopify": "#7AB55C",
        "spotify": "#1DB954",
        "figma": "#A259FF",
        "canva": "#00C4CC",
        "zoom": "#2D8CFF",
        "stripe": "#635BFF",
        "openai": "#10A37F",
        "anthropic": "#D97757",
        "ollama": "#111827",
        "vscode": "#007ACC",
        "xcode": "#147EFB",
    }
    category_colors = {
        "workspace_suite": "#2563EB",
        "communication": "#16A34A",
        "planning": "#7C3AED",
        "developer_platform": "#0F172A",
        "developer_tool": "#0369A1",
        "business_data": "#0891B2",
        "knowledge_base": "#52525B",
        "cloud_files": "#0284C7",
        "local_apps": "#64748B",
        "browser": "#0EA5E9",
        "automation": "#EA580C",
        "mlops": "#9333EA",
        "tool_runtime": "#4F46E5",
        "credentials": "#0D9488",
        "local_capture": "#DB2777",
        "commerce": "#65A30D",
        "media": "#E11D48",
        "observability": "#DC2626",
        "incident_management": "#D97706",
        "cloud": "#0284C7",
        "design": "#C026D3",
        "meetings": "#2563EB",
        "crm": "#0D9488",
        "support": "#0891B2",
        "finance": "#15803D",
        "marketing": "#F59E0B",
        "data": "#334155",
        "analytics": "#7C2D12",
        "research": "#4338CA",
        "ai": "#10A37F",
    }
    return provider_colors.get(provider_id, category_colors.get(category, "#64748B"))


def connector_logo_asset(provider_id: str) -> str:
    direct_tool_logos = {
        "airtable",
        "anthropic",
        "asana",
        "box",
        "canva",
        "clickup",
        "confluence",
        "discord",
        "dropbox",
        "evernote",
        "figma",
        "github",
        "gitlab",
        "hubspot",
        "icloud",
        "jira",
        "kubernetes",
        "linear",
        "netlify",
        "notion",
        "obsidian",
        "openai",
        "salesforce",
        "slack",
        "supabase",
        "todoist",
        "trello",
        "vercel",
        "vscode",
        "zendesk",
        "zoom",
    }
    aliases = {
        "apple_local": "tool-logos-apple.png",
        "azure_devops": "tool-logos-azure.png",
        "browser_use": "tool-logos-chrome.png",
        "docker_hub": "tool-logos-docker.png",
        "google_workspace": "tool-logos-google.png",
        "googlechat": "tool-logos-google.png",
        "homeassistant": "tool-logos-make.png",
        "hugging_face": "tool-logos-memory.png",
        "microsoft_365": "tool-logos-outlook.png",
        "msteams": "tool-logos-teams.png",
        "screenpipe": "tool-logos-screen.png",
        "voice_call": "tool-logos-voice.png",
        "webchat": "channel-logos-webchat.png",
        "whatsapp": "channel-logos-whatsapp.png",
        "telegram": "channel-logos-telegram.png",
        "signal": "channel-logos-signal.png",
        "grok_xai": "provider-logos-grok.png",
        "groq": "provider-logos-groq.png",
        "ollama": "provider-logos-ollama.png",
    }
    if provider_id in direct_tool_logos:
        return f"tool-logos-{provider_id}.png"
    return aliases.get(provider_id, "")
