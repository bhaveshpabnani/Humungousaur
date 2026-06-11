using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Workspace;

internal sealed class WorkspaceActivityCollector
{
    private readonly ConcurrentDictionary<string, string> _lastArrangementByWindow = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<int> _seenAppWorkspaces = [];
    private string _lastAppWorkspaceSignature = "";
    private DisplaySnapshot _displaySnapshot = DisplaySnapshot.Current();

    public IEnumerable<NativeCollectorEvent> Diff()
    {
        var current = DisplaySnapshot.Current();
        foreach (var collectorEvent in _displaySnapshot.Diff(current))
        {
            yield return collectorEvent;
        }
        _displaySnapshot = current;
    }

    public IEnumerable<NativeCollectorEvent> ObserveForeground(WindowSnapshot snapshot)
    {
        foreach (var appWorkspaceEvent in ObserveAppWorkspace(snapshot))
        {
            yield return appWorkspaceEvent;
        }
        foreach (var windowEvent in ObserveWindowGeometry(snapshot))
        {
            yield return windowEvent;
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveWindowGeometry(WindowSnapshot snapshot)
    {
        if (!snapshot.IsVisible)
        {
            yield break;
        }

        var monitor = MonitorSnapshot.ForWindow(snapshot.Handle);
        var arrangement = ClassifyArrangement(snapshot, monitor);
        if (arrangement is null)
        {
            yield break;
        }

        var signature = $"{arrangement.StimulusType}:{arrangement.Kind}:{monitor.MonitorDigest}:{snapshot.Width}x{snapshot.Height}";
        var handle = WindowSnapshot.HandleString(snapshot.Handle);
        if (_lastArrangementByWindow.TryGetValue(handle, out var previous) && previous == signature)
        {
            yield break;
        }
        _lastArrangementByWindow[handle] = signature;

        var metadata = WindowWorkspaceMetadata(snapshot, monitor);
        metadata["arrangement_kind"] = arrangement.Kind;
        metadata["arrangement_confidence"] = arrangement.Confidence;
        metadata["window_title_omitted"] = "true";
        metadata["screen_content_omitted"] = "true";
        yield return new NativeCollectorEvent(
            CollectorCatalog.WindowArrangementActivity,
            "system",
            arrangement.StimulusType,
            arrangement.Text,
            metadata,
            PrivacyTier: "sensitive_metadata"
        );
    }

    public IEnumerable<NativeCollectorEvent> ObserveKeyDown(uint virtualKey)
    {
        var foreground = WindowSnapshot.FromForeground();
        var metadata = foreground is null
            ? BaseMetadata("windows_workspace_keyboard")
            : WindowWorkspaceMetadata(foreground, MonitorSnapshot.ForWindow(foreground.Handle));
        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        var win = NativeMethods.IsKeyDown(NativeMethods.VkLwin) || NativeMethods.IsKeyDown(NativeMethods.VkRwin);
        metadata["modifier_ctrl"] = ctrl.ToString().ToLowerInvariant();
        metadata["modifier_alt"] = alt.ToString().ToLowerInvariant();
        metadata["modifier_shift"] = shift.ToString().ToLowerInvariant();
        metadata["modifier_win"] = win.ToString().ToLowerInvariant();
        metadata["raw_key_omitted"] = "true";

        if (win && virtualKey == (uint)NativeMethods.VkTab)
        {
            yield return new NativeCollectorEvent(
                CollectorCatalog.WorkspaceLayoutActivity,
                "system",
                "workspace_overview_opened",
                "Windows Task View opened; window titles and visible contents are omitted.",
                SensitiveMetadata(metadata),
                PrivacyTier: "sensitive_metadata"
            );
        }
        else if (win && ctrl && (virtualKey == (uint)NativeMethods.VkLeft || virtualKey == (uint)NativeMethods.VkRight))
        {
            metadata["desktop_direction"] = virtualKey == (uint)NativeMethods.VkLeft ? "previous" : "next";
            yield return new NativeCollectorEvent(
                CollectorCatalog.WorkspaceLayoutActivity,
                "system",
                "desktop_space_switched",
                "Virtual desktop switch shortcut observed; workspace names and contents are omitted.",
                SensitiveMetadata(metadata),
                PrivacyTier: "sensitive_metadata"
            );
        }
        else if (win && shift && (virtualKey == (uint)NativeMethods.VkLeft || virtualKey == (uint)NativeMethods.VkRight))
        {
            metadata["display_move_direction"] = virtualKey == (uint)NativeMethods.VkLeft ? "previous_display" : "next_display";
            yield return new NativeCollectorEvent(
                CollectorCatalog.WindowArrangementActivity,
                "system",
                "window_moved_to_display",
                "Window move-to-display shortcut observed; window title and display labels are omitted.",
                SensitiveMetadata(metadata),
                PrivacyTier: "sensitive_metadata"
            );
        }
        else if (win && (virtualKey == (uint)NativeMethods.VkLeft || virtualKey == (uint)NativeMethods.VkRight || virtualKey == (uint)NativeMethods.VkUp || virtualKey == (uint)NativeMethods.VkDown))
        {
            metadata["snap_direction"] = SnapDirection(virtualKey);
            yield return new NativeCollectorEvent(
                CollectorCatalog.WindowArrangementActivity,
                "system",
                "window_snapped",
                "Window snap shortcut observed; window title and visible contents are omitted.",
                SensitiveMetadata(metadata),
                PrivacyTier: "sensitive_metadata"
            );
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveMessage(NativeMethods.Message message)
    {
        if (message.Msg != NativeMethods.WmDisplayChange)
        {
            yield break;
        }
        var current = DisplaySnapshot.Current();
        var metadata = current.Metadata("windows_wm_displaychange");
        metadata["display_message_observed"] = "true";
        metadata["display_labels_omitted"] = "true";
        metadata["visible_contents_omitted"] = "true";
        yield return new NativeCollectorEvent(
            CollectorCatalog.DisplayArrangementActivity,
            "system",
            "display_arrangement_changed",
            "Display topology change broadcast observed; display labels and visible contents are omitted.",
            metadata
        );
        _displaySnapshot = current;
    }

    private IEnumerable<NativeCollectorEvent> ObserveAppWorkspace(WindowSnapshot snapshot)
    {
        var signature = $"{snapshot.ProcessId}:{snapshot.ProcessName}:{snapshot.TitleHash}";
        if (signature == _lastAppWorkspaceSignature)
        {
            yield break;
        }

        var firstSeen = _seenAppWorkspaces.Add(snapshot.ProcessId);
        _lastAppWorkspaceSignature = signature;
        var metadata = WindowWorkspaceMetadata(snapshot, MonitorSnapshot.ForWindow(snapshot.Handle));
        metadata["workspace_name_omitted"] = "true";
        metadata["project_name_omitted"] = "true";
        metadata["profile_name_omitted"] = "true";
        metadata["path_omitted"] = "true";
        metadata["restored_contents_omitted"] = "true";

        yield return new NativeCollectorEvent(
            CollectorCatalog.AppWorkspaceActivity,
            "activity",
            firstSeen ? "app_workspace_opened" : "app_workspace_switched",
            firstSeen
                ? "App workspace opened; workspace names, paths, and restored contents are omitted."
                : "App workspace switched; workspace names, paths, and restored contents are omitted.",
            metadata,
            PrivacyTier: "sensitive_metadata"
        );
    }

    private static ArrangementClassification? ClassifyArrangement(WindowSnapshot snapshot, MonitorSnapshot monitor)
    {
        if (monitor.WorkWidth <= 0 || monitor.WorkHeight <= 0 || snapshot.Width <= 0 || snapshot.Height <= 0)
        {
            return null;
        }

        var widthRatio = (double)snapshot.Width / monitor.WorkWidth;
        var heightRatio = (double)snapshot.Height / monitor.WorkHeight;
        if (widthRatio >= 0.94 && heightRatio >= 0.94)
        {
            return new ArrangementClassification(
                "window_fullscreen_entered",
                "fills_work_area",
                "high",
                "Window fills the active work area; title and visible contents are omitted."
            );
        }
        if (heightRatio >= 0.82 && widthRatio is >= 0.42 and <= 0.58)
        {
            return new ArrangementClassification(
                "window_snapped",
                "half_screen_snap",
                "medium",
                "Window appears snapped to a side of the work area; title and visible contents are omitted."
            );
        }
        if (heightRatio is >= 0.38 and <= 0.62 && widthRatio is >= 0.38 and <= 0.62)
        {
            return new ArrangementClassification(
                "window_tiled",
                "quadrant_tile",
                "medium",
                "Window appears tiled in a display quadrant; title and visible contents are omitted."
            );
        }
        return null;
    }

    private static Dictionary<string, string> WindowWorkspaceMetadata(WindowSnapshot snapshot, MonitorSnapshot monitor)
    {
        var metadata = BaseMetadata("windows_workspace_winevent");
        metadata["app_name"] = snapshot.ProcessNameOrUnknown;
        metadata["process_id"] = snapshot.ProcessId.ToStringInvariant();
        metadata["window_handle"] = WindowSnapshot.HandleString(snapshot.Handle);
        metadata["window_class"] = snapshot.ClassName;
        metadata["window_title_omitted"] = "true";
        metadata["window_title_length"] = snapshot.TitleLength.ToStringInvariant();
        metadata["window_title_hash"] = snapshot.TitleHash;
        metadata["window_width_bucket"] = BucketPixels(snapshot.Width);
        metadata["window_height_bucket"] = BucketPixels(snapshot.Height);
        metadata["monitor_digest"] = monitor.MonitorDigest;
        metadata["monitor_primary"] = monitor.IsPrimary.ToString().ToLowerInvariant();
        metadata["monitor_width_bucket"] = BucketPixels(monitor.Width);
        metadata["monitor_height_bucket"] = BucketPixels(monitor.Height);
        metadata["work_area_width_bucket"] = BucketPixels(monitor.WorkWidth);
        metadata["work_area_height_bucket"] = BucketPixels(monitor.WorkHeight);
        metadata["display_label_omitted"] = "true";
        metadata["screen_content_omitted"] = "true";
        return metadata;
    }

    private static string SnapDirection(uint virtualKey)
    {
        if (virtualKey == (uint)NativeMethods.VkLeft) return "left";
        if (virtualKey == (uint)NativeMethods.VkRight) return "right";
        if (virtualKey == (uint)NativeMethods.VkUp) return "up";
        return "down";
    }

    private static Dictionary<string, string> BaseMetadata(string nativeSource) => new()
    {
        ["native_source"] = nativeSource,
        ["platform"] = "windows",
    };

    private static Dictionary<string, string> SensitiveMetadata(Dictionary<string, string> metadata)
    {
        var copy = new Dictionary<string, string>(metadata);
        copy["privacy_level"] = "redacted";
        return copy;
    }

    private static string BucketPixels(int value) => value switch
    {
        <= 0 => "unknown",
        < 640 => "small",
        < 1280 => "medium",
        < 1920 => "large",
        < 2560 => "xlarge",
        _ => "xxlarge",
    };

    private static string StableHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant()[..16];
    }

    private sealed record ArrangementClassification(string StimulusType, string Kind, string Confidence, string Text);

    private sealed record MonitorSnapshot(
        string MonitorDigest,
        bool IsPrimary,
        int Width,
        int Height,
        int WorkWidth,
        int WorkHeight
    )
    {
        public static MonitorSnapshot ForWindow(IntPtr hwnd)
        {
            var monitor = NativeMethods.MonitorFromWindow(hwnd, NativeMethods.MonitorDefaultToNearest);
            var info = NativeMethods.MonitorInfoEx.Create();
            if (monitor == IntPtr.Zero || !NativeMethods.GetMonitorInfo(monitor, ref info))
            {
                return new MonitorSnapshot("unknown", false, 0, 0, 0, 0);
            }
            return FromInfo(info);
        }

        public static MonitorSnapshot FromInfo(NativeMethods.MonitorInfoEx info)
        {
            var monitorRect = info.RcMonitor;
            var workRect = info.RcWork;
            var digestMaterial = $"{info.SzDevice}:{monitorRect.Left}:{monitorRect.Top}:{monitorRect.Right}:{monitorRect.Bottom}";
            return new MonitorSnapshot(
                StableHash(digestMaterial),
                (info.DwFlags & 1) == 1,
                Math.Max(0, monitorRect.Right - monitorRect.Left),
                Math.Max(0, monitorRect.Bottom - monitorRect.Top),
                Math.Max(0, workRect.Right - workRect.Left),
                Math.Max(0, workRect.Bottom - workRect.Top)
            );
        }
    }

    private sealed record DisplaySnapshot(
        string Signature,
        string ResolutionSignature,
        string PrimaryDigest,
        int MonitorCount,
        int VirtualWidth,
        int VirtualHeight
    )
    {
        public static DisplaySnapshot Current()
        {
            var monitors = EnumerateMonitors();
            var signature = string.Join("|", monitors.Select(monitor => $"{monitor.MonitorDigest}:{monitor.Width}x{monitor.Height}:{monitor.IsPrimary}").OrderBy(value => value, StringComparer.Ordinal));
            var resolution = string.Join("|", monitors.Select(monitor => $"{monitor.Width}x{monitor.Height}").OrderBy(value => value, StringComparer.Ordinal));
            var primary = monitors.FirstOrDefault(monitor => monitor.IsPrimary)?.MonitorDigest ?? "";
            return new DisplaySnapshot(
                signature,
                resolution,
                primary,
                monitors.Count,
                NativeMethods.GetSystemMetrics(NativeMethods.SmCxVirtualScreen),
                NativeMethods.GetSystemMetrics(NativeMethods.SmCyVirtualScreen)
            );
        }

        public IEnumerable<NativeCollectorEvent> Diff(DisplaySnapshot current)
        {
            if (Signature == current.Signature)
            {
                yield break;
            }

            var metadata = current.Metadata("windows_enum_display_monitors");
            metadata["previous_monitor_count"] = MonitorCount.ToStringInvariant();
            metadata["previous_primary_digest"] = PrimaryDigest;
            yield return new NativeCollectorEvent(
                CollectorCatalog.DisplayArrangementActivity,
                "system",
                "display_arrangement_changed",
                "Display arrangement changed; display labels and visible contents are omitted.",
                metadata
            );

            if (ResolutionSignature != current.ResolutionSignature)
            {
                yield return new NativeCollectorEvent(
                    CollectorCatalog.DisplayArrangementActivity,
                    "system",
                    "display_resolution_changed",
                    "Display resolution changed; display labels and visible contents are omitted.",
                    metadata
                );
            }
            if (!string.Equals(PrimaryDigest, current.PrimaryDigest, StringComparison.OrdinalIgnoreCase))
            {
                yield return new NativeCollectorEvent(
                    CollectorCatalog.DisplayArrangementActivity,
                    "system",
                    "primary_display_changed",
                    "Primary display changed; display labels and visible contents are omitted.",
                    metadata
                );
            }
        }

        public Dictionary<string, string> Metadata(string nativeSource) => new()
        {
            ["native_source"] = nativeSource,
            ["platform"] = "windows",
            ["monitor_count"] = MonitorCount.ToStringInvariant(),
            ["monitor_count_system"] = NativeMethods.GetSystemMetrics(NativeMethods.SmCMonitors).ToStringInvariant(),
            ["primary_display_digest"] = PrimaryDigest,
            ["virtual_screen_width_bucket"] = BucketPixels(VirtualWidth),
            ["virtual_screen_height_bucket"] = BucketPixels(VirtualHeight),
            ["display_labels_omitted"] = "true",
            ["visible_contents_omitted"] = "true",
        };

        private static List<MonitorSnapshot> EnumerateMonitors()
        {
            var monitors = new List<MonitorSnapshot>();
            bool Enumerate(IntPtr monitor, IntPtr hdc, ref NativeMethods.Rect rect, IntPtr data)
            {
                var info = NativeMethods.MonitorInfoEx.Create();
                if (NativeMethods.GetMonitorInfo(monitor, ref info))
                {
                    monitors.Add(MonitorSnapshot.FromInfo(info));
                }
                return true;
            }
            NativeMethods.MonitorEnumProc callback = Enumerate;
            NativeMethods.EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, callback, IntPtr.Zero);
            return monitors;
        }
    }
}
