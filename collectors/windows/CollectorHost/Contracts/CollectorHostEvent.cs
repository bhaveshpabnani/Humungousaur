namespace Humungousaur.Collectors.Windows.Contracts;

internal sealed record NativeCollectorEvent(
    string Collector,
    string Source,
    string StimulusType,
    string Text,
    Dictionary<string, string> Metadata,
    Dictionary<string, string>? Payload = null,
    string PrivacyTier = "metadata"
)
{
    public Dictionary<string, string> PayloadOrMetadata => Payload ?? Metadata;
}
