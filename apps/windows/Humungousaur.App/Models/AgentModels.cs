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

public sealed class RuntimeRunItem
{
    [JsonPropertyName("run_id")]
    public string RunId { get; set; } = "";

    [JsonPropertyName("request")]
    public string Request { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("started_at")]
    public string StartedAt { get; set; } = "";

    [JsonPropertyName("finished_at")]
    public string? FinishedAt { get; set; }

    [JsonPropertyName("final_response")]
    public string? FinalResponse { get; set; }

    public string Title => $"{Status}  {ShortRunId}";
    public string Subtitle => string.IsNullOrWhiteSpace(Request) ? ShortRunId : Request;
    public string ShortRunId => RunId.Length <= 12 ? RunId : RunId[..12];
}

public sealed class ApprovalItem
{
    [JsonPropertyName("approval_token")]
    public string ApprovalToken { get; set; } = "";

    [JsonPropertyName("run_id")]
    public string RunId { get; set; } = "";

    [JsonPropertyName("request")]
    public string Request { get; set; } = "";

    [JsonPropertyName("tool_name")]
    public string ToolName { get; set; } = "";

    [JsonPropertyName("tool_input")]
    public JsonObject? ToolInput { get; set; }

    [JsonPropertyName("risk_level")]
    public string RiskLevel { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = "";

    public string Title => $"{ToolName}  {RiskLevel}";
    public string Subtitle => string.IsNullOrWhiteSpace(Reason) ? Request : Reason;
    public string ShortToken => ApprovalToken.Length <= 12 ? ApprovalToken : ApprovalToken[..12];
}

public sealed class ChatLogItem
{
    public string Speaker { get; init; } = "";
    public string Text { get; init; } = "";
    public string Tone { get; init; } = "neutral";
    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.Now;
    public string TimeText => Timestamp.ToLocalTime().ToString("h:mm tt");
}

public sealed class AgentStreamEvent
{
    public string Event { get; init; } = "";
    public JsonObject Data { get; init; } = [];
}
