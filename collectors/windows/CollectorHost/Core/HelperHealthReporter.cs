using System.Net.Http.Json;
using Humungousaur.Collectors.Windows.Contracts;

namespace Humungousaur.Collectors.Windows.Core;

internal sealed class HelperHealthReporter
{
    private readonly CollectorHostOptions _options;
    private readonly HttpClient _client = new();

    public string LastEventAt { get; set; } = "";

    public HelperHealthReporter(CollectorHostOptions options)
    {
        _options = options;
    }

    public Task ReportForAllAsync(string status, string message, CancellationToken cancellationToken) =>
        Task.WhenAll(CollectorCatalog.WindowsCollectors.Select(collector => ReportAsync(collector, status, message, cancellationToken)));

    private async Task ReportAsync(string collector, string status, string message, CancellationToken cancellationToken)
    {
        if (_options.HelperHealthUrl is null)
        {
            return;
        }
        var payload = new
        {
            helper_id = "windows-core-os-context",
            collector,
            platform = "windows",
            status,
            pid = Environment.ProcessId,
            version = _options.Version,
            permission_state = "metadata_only",
            last_event_at = LastEventAt,
            restart_count = 0,
            message,
            metadata = new Dictionary<string, string>
            {
                ["collects_raw_text"] = "false",
                ["collects_screen_content"] = "false",
                ["collects_audio"] = "false",
            },
        };
        try
        {
            using var response = await _client.PostAsJsonAsync(_options.HelperHealthUrl, payload, cancellationToken);
            _ = response.StatusCode;
        }
        catch
        {
            // Health reporting is best-effort; event emission must not fail just because the runtime is offline.
        }
    }
}
