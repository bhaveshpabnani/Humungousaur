using Humungousaur.Collectors.Windows.Contracts;

namespace Humungousaur.Collectors.Windows.Collectors.Window;

internal static class ActiveWindowCollector
{
    public static CollectorHostEvent Create(WindowSnapshot snapshot) =>
        new(
            CollectorCatalog.ActiveWindow,
            "activity",
            "active_window_changed",
            $"Active window changed: {snapshot.ProcessNameOrUnknown}.",
            snapshot.RedactedMetadata(),
            snapshot.RedactedPayload()
        );
}
