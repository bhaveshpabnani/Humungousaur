using System.Diagnostics;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Application;

internal sealed class AppLifecycleCollector
{
    private Dictionary<int, string> _previous = Snapshot();

    public IEnumerable<CollectorHostEvent> Diff()
    {
        var current = Snapshot();
        foreach (var pair in current)
        {
            if (!_previous.ContainsKey(pair.Key))
            {
                yield return Create("app_opened", pair.Key, pair.Value);
            }
        }
        foreach (var pair in _previous)
        {
            if (!current.ContainsKey(pair.Key))
            {
                yield return Create("app_closed", pair.Key, pair.Value);
            }
        }
        _previous = current;
    }

    public static CollectorHostEvent CreateFocus(int processId, string processName) => Create("app_focused", processId, processName);

    private static CollectorHostEvent Create(string stimulusType, int processId, string processName)
    {
        var safeName = string.IsNullOrWhiteSpace(processName) ? "unknown" : processName.Trim();
        var metadata = new Dictionary<string, string>
        {
            ["process_id"] = processId.ToStringInvariant(),
            ["process_name"] = safeName,
            ["app_name"] = safeName,
        };
        return new CollectorHostEvent(CollectorCatalog.AppLifecycle, "activity", stimulusType, $"App lifecycle changed: {safeName}.", metadata);
    }

    private static Dictionary<int, string> Snapshot()
    {
        try
        {
            return Process.GetProcesses().ToDictionary(process => process.Id, process => SafeProcessName(process));
        }
        catch
        {
            return new Dictionary<int, string>();
        }
    }

    private static string SafeProcessName(Process process)
    {
        try
        {
            return process.ProcessName;
        }
        catch
        {
            return "unknown";
        }
    }
}
