using System.Text.Json.Nodes;
using System.Text.Json.Serialization;

namespace Humungousaur.App.Models;

public sealed class ChannelInfo
{
    [JsonPropertyName("channel_id")]
    public string ChannelId { get; set; } = "";

    [JsonPropertyName("display_name")]
    public string DisplayName { get; set; } = "";

    [JsonPropertyName("transport")]
    public string Transport { get; set; } = "";

    [JsonPropertyName("plugin_kind")]
    public string PluginKind { get; set; } = "";

    [JsonPropertyName("setup_kind")]
    public string SetupKind { get; set; } = "";

    [JsonPropertyName("conversation_types")]
    public List<string> ConversationTypes { get; set; } = [];

    [JsonPropertyName("supports_text")]
    public bool SupportsText { get; set; }

    [JsonPropertyName("supports_media")]
    public bool SupportsMedia { get; set; }

    [JsonPropertyName("supports_reactions")]
    public bool SupportsReactions { get; set; }

    [JsonPropertyName("setup")]
    public JsonObject? Setup { get; set; }

    [JsonPropertyName("delivery")]
    public JsonObject? Delivery { get; set; }

    [JsonPropertyName("policies")]
    public JsonObject? Policies { get; set; }

    [JsonPropertyName("runtime")]
    public JsonObject? Runtime { get; set; }
}

public sealed class ToolCatalog
{
    [JsonPropertyName("tool_count")]
    public int ToolCount { get; set; }

    [JsonPropertyName("groups")]
    public List<ToolGroup> Groups { get; set; } = [];

    [JsonPropertyName("tools")]
    public List<ToolInfo> Tools { get; set; } = [];
}

public sealed class ToolGroup
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("tool_count")]
    public int ToolCount { get; set; }
}

public sealed class ToolInfo
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("description")]
    public string Description { get; set; } = "";

    [JsonPropertyName("risk_level")]
    public string RiskLevel { get; set; } = "";

    [JsonPropertyName("requires_approval")]
    public bool RequiresApproval { get; set; }

    [JsonPropertyName("capability_group")]
    public string CapabilityGroup { get; set; } = "";
}

public sealed class OutboxEnvelope
{
    [JsonPropertyName("messages")]
    public List<JsonObject> Messages { get; set; } = [];
}

public sealed class ChatLogItem
{
    public string Speaker { get; init; } = "";
    public string Text { get; init; } = "";
    public string Tone { get; init; } = "neutral";
    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.Now;
    public string TimeText => Timestamp.ToLocalTime().ToString("h:mm tt");
}
