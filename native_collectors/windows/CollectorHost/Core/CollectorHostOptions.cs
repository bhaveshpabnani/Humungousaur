namespace Humungousaur.Collectors.Windows.Core;

internal sealed record CollectorHostOptions(
    string DataDir,
    bool Once,
    TimeSpan Interval,
    Uri? HelperHealthUrl,
    string Version,
    IReadOnlyList<string> WatchPaths
)
{
    public static CollectorHostOptions Parse(string[] args)
    {
        var dataDir = Args.ValueAfter(args, "--data-dir") ?? Path.Combine(Environment.CurrentDirectory, "artifacts");
        var once = args.Contains("--once", StringComparer.OrdinalIgnoreCase);
        var intervalMs = int.TryParse(Args.ValueAfter(args, "--interval-ms"), out var parsedInterval) ? parsedInterval : 1_000;
        var healthUrl = Args.ValueAfter(args, "--helper-health-url") ?? Environment.GetEnvironmentVariable("HUMUNGOUSAUR_COLLECTOR_HELPER_HEALTH_URL");
        return new CollectorHostOptions(
            dataDir,
            once,
            TimeSpan.FromMilliseconds(Math.Max(250, intervalMs)),
            Uri.TryCreate(healthUrl, UriKind.Absolute, out var parsedUrl) ? parsedUrl : null,
            "0.1.0",
            Args.ValuesAfter(args, "--watch-path")
        );
    }
}

internal static class Args
{
    public static string? ValueAfter(string[] args, string flag)
    {
        for (var index = 0; index < args.Length - 1; index++)
        {
            if (string.Equals(args[index], flag, StringComparison.OrdinalIgnoreCase))
            {
                return args[index + 1];
            }
        }
        return null;
    }

    public static IReadOnlyList<string> ValuesAfter(string[] args, string flag)
    {
        var values = new List<string>();
        for (var index = 0; index < args.Length - 1; index++)
        {
            if (string.Equals(args[index], flag, StringComparison.OrdinalIgnoreCase))
            {
                values.Add(args[index + 1]);
                index += 1;
            }
        }
        return values;
    }
}
