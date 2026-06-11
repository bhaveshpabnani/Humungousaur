using System.Security.Cryptography;
using System.Text;
using Humungousaur.Collectors.EventWriter;
using Humungousaur.Collectors.Windows.Contracts;

namespace Humungousaur.Collectors.Windows.Core;

internal sealed class CollectorEventSink
{
    private readonly Dictionary<string, JsonlEventWriter> _writers;
    private readonly HelperHealthReporter _health;

    public CollectorEventSink(CollectorHostOptions options, HelperHealthReporter health)
    {
        _health = health;
        _writers = CollectorCatalog.WindowsCollectors.ToDictionary(
            collector => collector,
            collector => new JsonlEventWriter(Path.Combine(options.DataDir, "collector_spool", $"{collector}.jsonl"))
        );
    }

    public async Task EmitAsync(CollectorHostEvent collectorEvent, CancellationToken cancellationToken)
    {
        var now = DateTimeOffset.UtcNow.ToString("O");
        var signature = $"windows:{collectorEvent.Collector}:{collectorEvent.StimulusType}:{StableHash(string.Join("|", collectorEvent.Metadata.Select(pair => $"{pair.Key}={pair.Value}")))}";
        var eventId = $"{collectorEvent.Collector}-{StableHash($"{signature}:{now}")}";
        var envelope = CollectorEventEnvelope.MetadataEvent(
            eventId,
            collectorEvent.Collector,
            collectorEvent.Source,
            collectorEvent.StimulusType,
            now,
            signature,
            collectorEvent.Text,
            collectorEvent.Metadata,
            collectorEvent.PayloadOrMetadata,
            collectorEvent.PrivacyTier
        );
        await _writers[collectorEvent.Collector].AppendAsync(envelope, cancellationToken);
        _health.LastEventAt = now;
    }

    private static string StableHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant()[..12];
    }
}
