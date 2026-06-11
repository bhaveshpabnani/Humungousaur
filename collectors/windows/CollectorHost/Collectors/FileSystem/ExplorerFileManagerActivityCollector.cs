using System.Collections.Concurrent;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.FileSystem;

internal sealed class ExplorerFileManagerActivityCollector
{
    private readonly ConcurrentDictionary<string, DateTimeOffset> _lastEmitted = new();

    public IEnumerable<NativeCollectorEvent> ObserveForeground(WindowSnapshot snapshot)
    {
        if (!IsExplorerWindow(snapshot) || !Throttle($"folder_opened:{snapshot.Handle}", TimeSpan.FromSeconds(5)))
        {
            yield break;
        }
        yield return new NativeCollectorEvent(
            CollectorCatalog.FolderNavigationActivity,
            "activity",
            "folder_opened",
            "File manager folder opened; folder path and name omitted.",
            ExplorerMetadata(snapshot),
            PrivacyTier: "sensitive_metadata"
        );
    }

    public IEnumerable<NativeCollectorEvent> ObserveKeyDown(uint virtualKey)
    {
        var foreground = WindowSnapshot.FromForeground();
        if (foreground is null || !IsExplorerWindow(foreground))
        {
            yield break;
        }

        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);

        if (alt && virtualKey == 0x50 && Throttle("preview_pane_opened", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(
                CollectorCatalog.FilePreviewActivity,
                "activity",
                "preview_pane_opened",
                "Explorer preview pane toggled; preview contents and filename omitted.",
                ExplorerMetadata(foreground),
                PrivacyTier: "sensitive_metadata"
            );
        }
        if (alt && virtualKey == 0x0D && Throttle("file_info_panel_opened", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(
                CollectorCatalog.FilePreviewActivity,
                "activity",
                "file_info_panel_opened",
                "File info panel opened; metadata details and filename omitted.",
                ExplorerMetadata(foreground),
                PrivacyTier: "sensitive_metadata"
            );
        }
        if (ctrl && shift && virtualKey == 0x4E && Throttle("folder_created_shortcut", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(
                CollectorCatalog.FolderNavigationActivity,
                "activity",
                "folder_created",
                "Explorer new folder shortcut used; folder name omitted.",
                ExplorerMetadata(foreground),
                PrivacyTier: "sensitive_metadata"
            );
        }
        if (virtualKey == 0x2E && Throttle("trash_shortcut", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(
                CollectorCatalog.TrashActivity,
                "activity",
                "file_moved_to_trash",
                "Explorer delete shortcut used; item path and filename omitted.",
                ExplorerMetadata(foreground),
                PrivacyTier: "sensitive_metadata"
            );
        }
    }

    private bool Throttle(string key, TimeSpan interval)
    {
        var now = DateTimeOffset.UtcNow;
        var previous = _lastEmitted.GetOrAdd(key, DateTimeOffset.MinValue);
        if (now - previous < interval)
        {
            return false;
        }
        _lastEmitted[key] = now;
        return true;
    }

    private static bool IsExplorerWindow(WindowSnapshot snapshot) =>
        snapshot.ProcessName.Equals("explorer", StringComparison.OrdinalIgnoreCase)
        && (snapshot.ClassName.Equals("CabinetWClass", StringComparison.OrdinalIgnoreCase)
            || snapshot.ClassName.Equals("ExploreWClass", StringComparison.OrdinalIgnoreCase));

    private static Dictionary<string, string> ExplorerMetadata(WindowSnapshot snapshot) => new()
    {
        ["process_id"] = snapshot.ProcessId.ToStringInvariant(),
        ["process_name"] = snapshot.ProcessName,
        ["window_class"] = snapshot.ClassName,
        ["path_redacted"] = "true",
        ["filename_omitted"] = "true",
        ["contents_omitted"] = "true",
        ["native_source"] = "windows_explorer_winevent_keyboard",
    };
}
