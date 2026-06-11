using System.Text.Json.Serialization;

namespace Humungousaur.Collectors.EventWriter;

public sealed record CollectorEventEnvelope(
    [property: JsonPropertyName("event_id")] string EventId,
    [property: JsonPropertyName("schema_version")] int SchemaVersion,
    [property: JsonPropertyName("collector")] string Collector,
    [property: JsonPropertyName("source")] string Source,
    [property: JsonPropertyName("platform")] string Platform,
    [property: JsonPropertyName("stimulus_type")] string StimulusType,
    [property: JsonPropertyName("privacy_tier")] string PrivacyTier,
    [property: JsonPropertyName("occurred_at")] string OccurredAt,
    [property: JsonPropertyName("received_at")] string ReceivedAt,
    [property: JsonPropertyName("signature")] string Signature,
    [property: JsonPropertyName("text")] string Text,
    [property: JsonPropertyName("metadata")] IReadOnlyDictionary<string, string> Metadata,
    [property: JsonPropertyName("payload")] IReadOnlyDictionary<string, string> Payload,
    [property: JsonPropertyName("redaction")] Redaction Redaction
)
{
    public static CollectorEventEnvelope MetadataEvent(
        string eventId,
        string collector,
        string source,
        string stimulusType,
        string occurredAt,
        string signature,
        string text,
        IReadOnlyDictionary<string, string>? metadata = null,
        IReadOnlyDictionary<string, string>? payload = null,
        string privacyTier = "metadata"
    ) => new(
        eventId,
        1,
        collector,
        source,
        "windows",
        stimulusType,
        privacyTier,
        occurredAt,
        DateTimeOffset.UtcNow.ToString("O"),
        signature,
        text,
        metadata ?? new Dictionary<string, string>(),
        payload ?? new Dictionary<string, string>(),
        Redaction.Metadata(privacyTier: privacyTier)
    );
}

public sealed record Redaction(
    [property: JsonPropertyName("raw_content_included")] bool RawContentIncluded,
    [property: JsonPropertyName("attention_safe")] bool AttentionSafe,
    [property: JsonPropertyName("paths_redacted")] bool PathsRedacted,
    [property: JsonPropertyName("payload_compacted_before_llm")] bool PayloadCompactedBeforeLlm,
    [property: JsonPropertyName("privacy_tier")] string PrivacyTier
)
{
    public static Redaction Metadata(bool pathsRedacted = true, string privacyTier = "metadata") => new(false, true, pathsRedacted, true, privacyTier);
}
