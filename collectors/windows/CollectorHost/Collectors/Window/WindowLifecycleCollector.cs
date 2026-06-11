using System.Collections.Concurrent;
using Humungousaur.Collectors.Windows.Contracts;

namespace Humungousaur.Collectors.Windows.Collectors.Window;

internal sealed class WindowLifecycleCollector
{
    private string _foregroundSignature = "";
    private readonly ConcurrentDictionary<IntPtr, string> _geometry = new();

    public bool MarkForegroundChanged(WindowSnapshot snapshot)
    {
        var signature = $"{snapshot.Handle}:{snapshot.ProcessId}:{snapshot.TitleHash}";
        if (signature == _foregroundSignature)
        {
            return false;
        }
        _foregroundSignature = signature;
        return true;
    }

    public bool MarkGeometryChanged(WindowSnapshot snapshot)
    {
        var geometry = $"{snapshot.Width}x{snapshot.Height}";
        if (_geometry.TryGetValue(snapshot.Handle, out var previous) && previous == geometry)
        {
            return false;
        }
        _geometry[snapshot.Handle] = geometry;
        return true;
    }

    public static NativeCollectorEvent Create(string stimulusType, WindowSnapshot snapshot) =>
        new(
            CollectorCatalog.WindowLifecycle,
            "activity",
            stimulusType,
            stimulusType switch
            {
                "window_opened" => $"Window opened: {snapshot.ProcessNameOrUnknown}.",
                "window_closed" => "Window closed.",
                "window_resized" => $"Window geometry changed: {snapshot.ProcessNameOrUnknown}.",
                _ => $"Window focused: {snapshot.ProcessNameOrUnknown}.",
            },
            snapshot.RedactedMetadata(),
            snapshot.RedactedPayload()
        );

    public static NativeCollectorEvent CreateClosed(IntPtr hwnd, int idObject) =>
        new(
            CollectorCatalog.WindowLifecycle,
            "activity",
            "window_closed",
            "Window closed.",
            new Dictionary<string, string> { ["window_handle"] = WindowSnapshot.HandleString(hwnd), ["id_object"] = idObject.ToString() },
            new Dictionary<string, string> { ["window_handle"] = WindowSnapshot.HandleString(hwnd) }
        );
}
