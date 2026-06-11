using System.Collections.Concurrent;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.SystemSurfaces;

internal sealed class SystemSurfaceActivityCollector
{
    private readonly ConcurrentDictionary<string, DateTimeOffset> _lastEmitted = new();
    private Dictionary<string, DriveSnapshot> _drives = SnapshotDrives();
    private Dictionary<int, CpuSample> _cpuSamples = SnapshotCpuSamples();
    private HashSet<int> _installerProcesses = InstallerProcesses();
    private int? _printSpoolFileCount = PrintSpoolFileCount();
    private bool _mediaPlaying;
    private DateTimeOffset? _lastLockAt;

    public IEnumerable<CollectorHostEvent> Diff()
    {
        foreach (var collectorEvent in ObserveStoragePressure())
        {
            yield return collectorEvent;
        }
        foreach (var collectorEvent in ObserveDriveTopology())
        {
            yield return collectorEvent;
        }
        foreach (var collectorEvent in ObserveResourcePressure())
        {
            yield return collectorEvent;
        }
        foreach (var collectorEvent in ObserveInstallerProcesses())
        {
            yield return collectorEvent;
        }
        foreach (var collectorEvent in ObservePrintSpool())
        {
            yield return collectorEvent;
        }
    }

    public IEnumerable<CollectorHostEvent> ObserveForeground(WindowSnapshot snapshot)
    {
        var process = SafeProcessName(snapshot.ProcessName);
        var metadata = WindowMetadata(snapshot);
        if (IsSearchSurface(process, snapshot.ClassName) && Throttle("foreground:search", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.SearchActivity, "activity", "system_search_performed", "System search surface focused; query omitted.", metadata, "sensitive_metadata");
        }
        if (IsPermissionSurface(process, snapshot.ClassName) && Throttle($"foreground:permission:{process}", TimeSpan.FromSeconds(10)))
        {
            yield return Create(CollectorCatalog.PermissionActivity, "system", "permission_requested", "Permission prompt observed; prompt text omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsLocationSurface(process, snapshot.ClassName) && Throttle("foreground:location", TimeSpan.FromSeconds(10)))
        {
            yield return Create(CollectorCatalog.LocationActivity, "system", "location_requested", "Location-related system surface observed; precise location omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsPrintSurface(process, snapshot.ClassName) && Throttle("foreground:print", TimeSpan.FromSeconds(5)))
        {
            yield return Create(CollectorCatalog.PrintScanActivity, "system", "printer_selected", "Print surface focused; document name and printer label omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsScanSurface(process, snapshot.ClassName) && Throttle("foreground:scan", TimeSpan.FromSeconds(5)))
        {
            yield return Create(CollectorCatalog.PrintScanActivity, "system", "scan_started", "Scan surface focused; scan preview and device label omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsPolicySurface(process, snapshot.ClassName) && Throttle($"foreground:policy:{process}", TimeSpan.FromSeconds(15)))
        {
            yield return Create(CollectorCatalog.PolicyActivity, "system", "policy_blocked_action", "Security or policy surface observed; message text omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsWellbeingSurface(process, snapshot.ClassName) && Throttle($"foreground:wellbeing:{process}", TimeSpan.FromSeconds(30)))
        {
            yield return Create(CollectorCatalog.WellbeingActivity, "system", "wellbeing_nudge_shown", "Wellbeing or focus surface observed; nudge text omitted.", metadata);
        }
        if (IsMediaSurface(process) && Throttle($"foreground:media:{process}", TimeSpan.FromSeconds(20)))
        {
            yield return Create(CollectorCatalog.MediaActivity, "activity", "media_playback_started", "Media app focused; track and media content omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsUpdateSurface(process) && Throttle($"foreground:update:{process}", TimeSpan.FromSeconds(30)))
        {
            yield return Create(CollectorCatalog.PolicyActivity, "system", "update_required", "Update or maintenance surface observed; update details omitted.", metadata);
        }
    }

    public IEnumerable<CollectorHostEvent> ObserveKeyDown(uint virtualKey)
    {
        var foreground = WindowSnapshot.FromForeground();
        var metadata = foreground is null ? BaseMetadata("windows_keyboard_system_surface") : WindowMetadata(foreground);
        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        var win = NativeMethods.IsKeyDown(NativeMethods.VkLwin) || NativeMethods.IsKeyDown(NativeMethods.VkRwin);
        metadata["modifier_set"] = ModifierSet(ctrl, alt, shift, win);
        metadata["raw_key_omitted"] = "true";

        if (win && virtualKey == 0x4E && Throttle("key:notification", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.NotificationActivity, "activity", "notification_clicked", "Notification center opened; notification contents omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (win && virtualKey == 0x53 && Throttle("key:system-search", TimeSpan.FromSeconds(1)))
        {
            yield return Create(CollectorCatalog.SearchActivity, "activity", "system_search_performed", "System search opened; query omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (ctrl && virtualKey == 0x50 && Throttle("key:print", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.PrintScanActivity, "system", "print_job_started", "Print command used; document content and name omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (win && virtualKey == 0x09 && Throttle("key:workspace", TimeSpan.FromSeconds(1)))
        {
            yield return Create(CollectorCatalog.FocusTaskActivity, "activity", "workspace_switched", "Task view or workspace switcher opened; window titles omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (win && ctrl && (virtualKey == (uint)NativeMethods.VkLeft || virtualKey == (uint)NativeMethods.VkRight) && Throttle($"key:desktop:{virtualKey}", TimeSpan.FromMilliseconds(750)))
        {
            yield return Create(CollectorCatalog.FocusTaskActivity, "activity", "desktop_space_changed", "Virtual desktop changed; workspace names omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (win && virtualKey == (uint)NativeMethods.VkL && Throttle("key:lock", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.FocusTaskActivity, "activity", "mode_changed", "Session lock requested; active content omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        foreach (var mediaEvent in ObserveMediaKey(virtualKey, metadata))
        {
            yield return mediaEvent;
        }
    }

    public IEnumerable<CollectorHostEvent> ObserveMouse(IntPtr message)
    {
        var foreground = WindowSnapshot.FromForeground();
        if (message.ToInt64() == NativeMethods.WmMouseWheel
            && foreground is not null
            && IsNotificationSurface(SafeProcessName(foreground.ProcessName), foreground.ClassName)
            && Throttle("mouse:notification-dismiss", TimeSpan.FromSeconds(15)))
        {
            yield return Create(
                CollectorCatalog.NotificationActivity,
                "activity",
                "notification_dismissed",
                "Notification surface interaction observed; notification contents omitted.",
                SensitiveMetadata(WindowMetadata(foreground)),
                "sensitive_metadata"
            );
        }
    }

    public IEnumerable<CollectorHostEvent> ObserveMessage(NativeMethods.Message message)
    {
        if (message.Msg == NativeMethods.WmDeviceChange)
        {
            var deviceEvent = message.WParam.ToUInt32();
            if (deviceEvent == NativeMethods.DbtDeviceArrival && Throttle("message:device-arrival", TimeSpan.FromSeconds(1)))
            {
                yield return Create(CollectorCatalog.PeripheralActivity, "system", "usb_device_connected", "Device arrival broadcast observed; device label omitted.", PeripheralMetadata("windows_wm_devicechange"));
            }
            if (deviceEvent == NativeMethods.DbtDeviceRemoveComplete && Throttle("message:device-remove", TimeSpan.FromSeconds(1)))
            {
                yield return Create(CollectorCatalog.PeripheralActivity, "system", "usb_device_disconnected", "Device removal broadcast observed; device label omitted.", PeripheralMetadata("windows_wm_devicechange"));
            }
            if (deviceEvent == NativeMethods.DbtDevnodesChanged && Throttle("message:devnodes", TimeSpan.FromSeconds(10)))
            {
                yield return Create(CollectorCatalog.PeripheralActivity, "system", "usb_device_connected", "Device topology changed; device labels omitted.", PeripheralMetadata("windows_wm_devicechange"));
            }
        }
        else if (message.Msg == NativeMethods.WmDisplayChange && Throttle("message:display", TimeSpan.FromSeconds(2)))
        {
            var metadata = PeripheralMetadata("windows_wm_displaychange");
            metadata["display_topology_changed"] = "true";
            yield return Create(CollectorCatalog.PeripheralActivity, "system", "external_display_connected", "Display topology changed; display labels omitted.", metadata);
        }
        else if (message.Msg == NativeMethods.WmPowerBroadcast)
        {
            var powerEvent = message.WParam.ToUInt32();
            if (powerEvent == NativeMethods.PbtApmSuspend && Throttle("message:suspend", TimeSpan.FromSeconds(2)))
            {
                yield return Create(CollectorCatalog.FocusTaskActivity, "activity", "mode_changed", "System suspend started; active content omitted.", SensitiveMetadata(BaseMetadata("windows_wm_powerbroadcast")), "sensitive_metadata");
            }
            if (powerEvent == NativeMethods.PbtApmResumeAutomatic && Throttle("message:resume", TimeSpan.FromSeconds(2)))
            {
                yield return Create(CollectorCatalog.FocusTaskActivity, "activity", "mode_changed", "System resumed; active content omitted.", SensitiveMetadata(BaseMetadata("windows_wm_powerbroadcast")), "sensitive_metadata");
            }
        }
        else if (message.Msg == NativeMethods.WmWtsSessionChange)
        {
            var sessionEvent = message.WParam.ToUInt32();
            if (sessionEvent == NativeMethods.WtsSessionLock && Throttle("message:session-lock", TimeSpan.FromSeconds(2)))
            {
                _lastLockAt = DateTimeOffset.UtcNow;
                yield return Create(CollectorCatalog.FocusTaskActivity, "activity", "mode_changed", "Session locked; active content omitted.", SensitiveMetadata(BaseMetadata("windows_wts_session")), "sensitive_metadata");
            }
            if (sessionEvent == NativeMethods.WtsSessionUnlock && Throttle("message:session-unlock", TimeSpan.FromSeconds(2)))
            {
                var metadata = SensitiveMetadata(BaseMetadata("windows_wts_session"));
                if (_lastLockAt is not null)
                {
                    metadata["locked_duration_bucket"] = BucketSeconds((DateTimeOffset.UtcNow - _lastLockAt.Value).TotalSeconds);
                }
                yield return Create(CollectorCatalog.FocusTaskActivity, "activity", "mode_changed", "Session unlocked; active content omitted.", metadata, "sensitive_metadata");
            }
        }
        else if (message.Msg == NativeMethods.WmSettingChange)
        {
            foreach (var collectorEvent in ObserveSettingChange(message))
            {
                yield return collectorEvent;
            }
        }
    }

    private IEnumerable<CollectorHostEvent> ObserveStoragePressure()
    {
        foreach (var drive in SnapshotDrives().Values)
        {
            if (drive.TotalBytes <= 0)
            {
                continue;
            }
            var ratio = (double)drive.FreeBytes / drive.TotalBytes;
            if (ratio <= 0.10 && Throttle($"storage:low:{drive.RootHash}", TimeSpan.FromMinutes(10)))
            {
                var metadata = BaseMetadata("windows_driveinfo_storage");
                metadata["drive_root_hash"] = drive.RootHash;
                metadata["drive_type"] = drive.DriveType;
                metadata["free_space_bucket"] = BucketBytes(drive.FreeBytes);
                metadata["total_space_bucket"] = BucketBytes(drive.TotalBytes);
                metadata["path_redacted"] = "true";
                yield return Create(CollectorCatalog.StorageActivity, "system", drive.DriveType == "Fixed" ? "disk_space_low" : "volume_space_low", "Storage free space is low; paths and filenames omitted.", metadata);
            }
        }
    }

    private IEnumerable<CollectorHostEvent> ObserveDriveTopology()
    {
        var current = SnapshotDrives();
        foreach (var pair in current)
        {
            if (!_drives.ContainsKey(pair.Key) && Throttle($"drive:mounted:{pair.Key}", TimeSpan.FromSeconds(2)))
            {
                yield return Create(CollectorCatalog.PeripheralActivity, "system", "storage_device_mounted", "Storage device mounted; volume label and path omitted.", DriveMetadata(pair.Value, "windows_driveinfo_topology"));
            }
        }
        foreach (var pair in _drives)
        {
            if (!current.ContainsKey(pair.Key) && Throttle($"drive:ejected:{pair.Key}", TimeSpan.FromSeconds(2)))
            {
                yield return Create(CollectorCatalog.PeripheralActivity, "system", "storage_device_ejected", "Storage device ejected; volume label and path omitted.", DriveMetadata(pair.Value, "windows_driveinfo_topology"));
            }
        }
        _drives = current;
    }

    private IEnumerable<CollectorHostEvent> ObserveResourcePressure()
    {
        var memory = NativeMethods.MemoryStatus();
        if (memory is { DwMemoryLoad: >= 90 } && Throttle("resource:memory", TimeSpan.FromMinutes(2)))
        {
            var metadata = BaseMetadata("windows_global_memory_status");
            metadata["memory_load_percent_bucket"] = BucketPercent(memory.Value.DwMemoryLoad);
            yield return Create(CollectorCatalog.ResourceActivity, "system", "memory_pressure_high", "System memory pressure is high; process contents omitted.", metadata);
        }

        var now = DateTimeOffset.UtcNow;
        var current = SnapshotCpuSamples();
        foreach (var pair in current)
        {
            if (!_cpuSamples.TryGetValue(pair.Key, out var previous))
            {
                continue;
            }
            var elapsedMs = Math.Max(1, (now - previous.ObservedAt).TotalMilliseconds);
            var cpuMs = Math.Max(0, (pair.Value.TotalProcessorTime - previous.TotalProcessorTime).TotalMilliseconds);
            var normalized = cpuMs / Math.Max(1, elapsedMs * Math.Max(1, Environment.ProcessorCount));
            if (normalized >= 0.80 && Throttle($"resource:cpu:{pair.Key}", TimeSpan.FromMinutes(2)))
            {
                var metadata = BaseMetadata("windows_process_cpu_sample");
                metadata["process_id"] = pair.Key.ToStringInvariant();
                metadata["process_name"] = pair.Value.ProcessName;
                metadata["cpu_ratio_bucket"] = BucketRatio(normalized);
                metadata["command_line_omitted"] = "true";
                metadata["process_path_omitted"] = "true";
                yield return Create(CollectorCatalog.ResourceActivity, "system", "process_high_cpu", "Process CPU pressure is high; command line and path omitted.", metadata);
            }
        }
        _cpuSamples = current;
    }

    private IEnumerable<CollectorHostEvent> ObserveInstallerProcesses()
    {
        var current = InstallerProcesses();
        foreach (var processId in current)
        {
            if (!_installerProcesses.Contains(processId) && Throttle($"installer:{processId}", TimeSpan.FromSeconds(30)))
            {
                var metadata = BaseMetadata("windows_process_installer_detection");
                metadata["process_id"] = processId.ToStringInvariant();
                metadata["app_name_omitted"] = "true";
                metadata["installer_package_omitted"] = "true";
                metadata["command_line_omitted"] = "true";
                yield return Create(CollectorCatalog.SoftwareActivity, "system", "installer_started", "Installer or updater process started; package details omitted.", metadata);
            }
        }
        _installerProcesses = current;
    }

    private IEnumerable<CollectorHostEvent> ObservePrintSpool()
    {
        var current = PrintSpoolFileCount();
        if (current is null)
        {
            yield break;
        }
        if (_printSpoolFileCount is not null && current > _printSpoolFileCount && Throttle("print:spool-start", TimeSpan.FromSeconds(5)))
        {
            var metadata = BaseMetadata("windows_print_spool_directory");
            metadata["spool_file_count_bucket"] = BucketCount(current.Value);
            metadata["document_name_omitted"] = "true";
            metadata["spool_path_redacted"] = "true";
            yield return Create(CollectorCatalog.PrintScanActivity, "system", "print_job_started", "Print spool activity started; document details omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (_printSpoolFileCount is not null && current < _printSpoolFileCount && Throttle("print:spool-complete", TimeSpan.FromSeconds(5)))
        {
            var metadata = BaseMetadata("windows_print_spool_directory");
            metadata["spool_file_count_bucket"] = BucketCount(current.Value);
            metadata["document_name_omitted"] = "true";
            metadata["spool_path_redacted"] = "true";
            yield return Create(CollectorCatalog.PrintScanActivity, "system", "print_job_completed", "Print spool activity completed; document details omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        _printSpoolFileCount = current;
    }

    private IEnumerable<CollectorHostEvent> ObserveMediaKey(uint virtualKey, Dictionary<string, string> metadata)
    {
        if (virtualKey == (uint)NativeMethods.VkMediaPlayPause && Throttle("media:playpause", TimeSpan.FromMilliseconds(750)))
        {
            _mediaPlaying = !_mediaPlaying;
            yield return Create(CollectorCatalog.MediaActivity, "activity", _mediaPlaying ? "media_playback_started" : "media_playback_paused", "Media playback key used; track metadata omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (virtualKey == (uint)NativeMethods.VkMediaStop && Throttle("media:stop", TimeSpan.FromMilliseconds(750)))
        {
            _mediaPlaying = false;
            yield return Create(CollectorCatalog.MediaActivity, "activity", "media_playback_stopped", "Media stop key used; track metadata omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if ((virtualKey == (uint)NativeMethods.VkMediaNextTrack || virtualKey == (uint)NativeMethods.VkMediaPreviousTrack) && Throttle($"media:track:{virtualKey}", TimeSpan.FromMilliseconds(750)))
        {
            yield return Create(CollectorCatalog.MediaActivity, "activity", "media_track_changed", "Media track changed; title and artist omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
    }

    private IEnumerable<CollectorHostEvent> ObserveSettingChange(NativeMethods.Message message)
    {
        var area = "";
        try
        {
            area = message.LParam == IntPtr.Zero ? "" : System.Runtime.InteropServices.Marshal.PtrToStringUni(message.LParam) ?? "";
        }
        catch
        {
            area = "";
        }
        var metadata = BaseMetadata("windows_wm_settingchange");
        metadata["setting_area_hash"] = StableHash(area.ToLowerInvariant());
        metadata["setting_area_omitted"] = "true";
        if (area.Contains("Policy", StringComparison.OrdinalIgnoreCase) && Throttle("setting:policy", TimeSpan.FromSeconds(10)))
        {
            yield return Create(CollectorCatalog.PolicyActivity, "system", "managed_profile_changed", "Policy settings changed; policy details omitted.", metadata);
        }
        if ((area.Contains("TimeZone", StringComparison.OrdinalIgnoreCase) || area.Contains("intl", StringComparison.OrdinalIgnoreCase)) && Throttle("setting:region", TimeSpan.FromSeconds(10)))
        {
            yield return Create(CollectorCatalog.LocationActivity, "system", area.Contains("TimeZone", StringComparison.OrdinalIgnoreCase) ? "timezone_changed" : "region_changed", "Region or timezone settings changed; location omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
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

    private static CollectorHostEvent Create(string collector, string source, string stimulusType, string text, Dictionary<string, string> metadata, string privacyTier = "metadata") =>
        new(collector, source, stimulusType, text, metadata, PrivacyTier: privacyTier);

    private static Dictionary<string, string> WindowMetadata(WindowSnapshot snapshot)
    {
        var metadata = BaseMetadata("windows_system_surface_window_metadata");
        metadata["process_id"] = snapshot.ProcessId.ToStringInvariant();
        metadata["process_name"] = snapshot.ProcessNameOrUnknown;
        metadata["window_class"] = snapshot.ClassName;
        metadata["window_title_omitted"] = "true";
        metadata["window_title_length"] = snapshot.TitleLength.ToStringInvariant();
        metadata["window_title_hash"] = snapshot.TitleHash;
        metadata["screen_content_omitted"] = "true";
        return metadata;
    }

    private static Dictionary<string, string> BaseMetadata(string nativeSource) => new()
    {
        ["native_source"] = nativeSource,
        ["raw_content_included"] = "false",
        ["screen_content_omitted"] = "true",
        ["text_content_omitted"] = "true",
        ["payload_omitted"] = "true",
    };

    private static Dictionary<string, string> SensitiveMetadata(Dictionary<string, string> metadata)
    {
        var copy = new Dictionary<string, string>(metadata);
        copy["sensitive_values_omitted"] = "true";
        copy["raw_text_omitted"] = "true";
        return copy;
    }

    private static Dictionary<string, string> PeripheralMetadata(string nativeSource)
    {
        var metadata = BaseMetadata(nativeSource);
        metadata["device_label_omitted"] = "true";
        metadata["device_serial_omitted"] = "true";
        metadata["device_path_omitted"] = "true";
        return metadata;
    }

    private static Dictionary<string, string> DriveMetadata(DriveSnapshot drive, string nativeSource)
    {
        var metadata = PeripheralMetadata(nativeSource);
        metadata["drive_root_hash"] = drive.RootHash;
        metadata["drive_type"] = drive.DriveType;
        metadata["drive_label_omitted"] = "true";
        metadata["path_redacted"] = "true";
        return metadata;
    }

    private static Dictionary<string, DriveSnapshot> SnapshotDrives()
    {
        try
        {
            return DriveInfo.GetDrives()
                .Where(drive => drive.IsReady)
                .ToDictionary(
                    drive => StableHash(drive.RootDirectory.FullName.ToLowerInvariant()),
                    drive => new DriveSnapshot(
                        StableHash(drive.RootDirectory.FullName.ToLowerInvariant()),
                        drive.DriveType.ToString(),
                        SafeDriveValue(() => drive.TotalFreeSpace),
                        SafeDriveValue(() => drive.TotalSize)
                    )
                );
        }
        catch
        {
            return new Dictionary<string, DriveSnapshot>();
        }
    }

    private static long SafeDriveValue(Func<long> value)
    {
        try
        {
            return value();
        }
        catch
        {
            return 0;
        }
    }

    private static Dictionary<int, CpuSample> SnapshotCpuSamples()
    {
        try
        {
            var now = DateTimeOffset.UtcNow;
            return Process.GetProcesses().ToDictionary(
                process => process.Id,
                process => new CpuSample(now, SafeProcessName(process.ProcessName), SafeProcessorTime(process))
            );
        }
        catch
        {
            return new Dictionary<int, CpuSample>();
        }
    }

    private static TimeSpan SafeProcessorTime(Process process)
    {
        try
        {
            return process.TotalProcessorTime;
        }
        catch
        {
            return TimeSpan.Zero;
        }
    }

    private static HashSet<int> InstallerProcesses()
    {
        var installerNames = new[] { "msiexec", "setup", "installer", "update", "updater", "winget", "trustedinstaller", "tiworker" };
        try
        {
            return Process.GetProcesses()
                .Where(process => installerNames.Any(name => SafeProcessName(process.ProcessName).Contains(name, StringComparison.OrdinalIgnoreCase)))
                .Select(process => process.Id)
                .ToHashSet();
        }
        catch
        {
            return new HashSet<int>();
        }
    }

    private static int? PrintSpoolFileCount()
    {
        try
        {
            var spool = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "spool", "PRINTERS");
            return Directory.Exists(spool) ? Directory.EnumerateFiles(spool).Count() : 0;
        }
        catch
        {
            return null;
        }
    }

    private static bool IsSearchSurface(string process, string className) =>
        process.Contains("search", StringComparison.OrdinalIgnoreCase)
        || className.Contains("Search", StringComparison.OrdinalIgnoreCase);

    private static bool IsNotificationSurface(string process, string className) =>
        process.Equals("explorer", StringComparison.OrdinalIgnoreCase)
        && (className.Contains("Notification", StringComparison.OrdinalIgnoreCase)
            || className.Contains("Tray", StringComparison.OrdinalIgnoreCase)
            || className.Contains("Shell", StringComparison.OrdinalIgnoreCase));

    private static bool IsPermissionSurface(string process, string className) =>
        process.Equals("consent", StringComparison.OrdinalIgnoreCase)
        || process.Contains("credential", StringComparison.OrdinalIgnoreCase)
        || process.Contains("accountcontrol", StringComparison.OrdinalIgnoreCase)
        || className.Contains("Credential", StringComparison.OrdinalIgnoreCase)
        || className.Contains("Consent", StringComparison.OrdinalIgnoreCase);

    private static bool IsLocationSurface(string process, string className) =>
        process.Contains("location", StringComparison.OrdinalIgnoreCase)
        || className.Contains("Location", StringComparison.OrdinalIgnoreCase);

    private static bool IsPrintSurface(string process, string className) =>
        process.Contains("print", StringComparison.OrdinalIgnoreCase)
        || className.Contains("Print", StringComparison.OrdinalIgnoreCase);

    private static bool IsScanSurface(string process, string className) =>
        process.Equals("wfs", StringComparison.OrdinalIgnoreCase)
        || process.Contains("scan", StringComparison.OrdinalIgnoreCase)
        || className.Contains("Scan", StringComparison.OrdinalIgnoreCase);

    private static bool IsPolicySurface(string process, string className) =>
        process.Contains("securityhealth", StringComparison.OrdinalIgnoreCase)
        || process.Contains("smartscreen", StringComparison.OrdinalIgnoreCase)
        || process.Contains("defender", StringComparison.OrdinalIgnoreCase)
        || process.Contains("cert", StringComparison.OrdinalIgnoreCase)
        || className.Contains("Security", StringComparison.OrdinalIgnoreCase);

    private static bool IsWellbeingSurface(string process, string className) =>
        process.Contains("clock", StringComparison.OrdinalIgnoreCase)
        || process.Contains("focus", StringComparison.OrdinalIgnoreCase)
        || className.Contains("Focus", StringComparison.OrdinalIgnoreCase);

    private static bool IsMediaSurface(string process) =>
        new[] { "spotify", "vlc", "wmplayer", "zune", "music", "media", "itunes" }.Any(name => process.Contains(name, StringComparison.OrdinalIgnoreCase));

    private static bool IsUpdateSurface(string process) =>
        process.Contains("windowsupdate", StringComparison.OrdinalIgnoreCase)
        || process.Contains("update", StringComparison.OrdinalIgnoreCase)
        || process.Contains("tiworker", StringComparison.OrdinalIgnoreCase)
        || process.Contains("trustedinstaller", StringComparison.OrdinalIgnoreCase);

    private static string ModifierSet(bool ctrl, bool alt, bool shift, bool win) =>
        string.Join("+", new[] { ctrl ? "ctrl" : "", alt ? "alt" : "", shift ? "shift" : "", win ? "win" : "" }.Where(value => value.Length > 0));

    private static string SafeProcessName(string processName)
    {
        var name = (processName ?? "").Trim();
        return name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? Path.GetFileNameWithoutExtension(name) : name;
    }

    private static string BucketBytes(long bytes) => bytes switch
    {
        < 0 => "unknown",
        < 1_000_000_000L => "under_1gb",
        < 5_000_000_000L => "1_5gb",
        < 20_000_000_000L => "5_20gb",
        < 100_000_000_000L => "20_100gb",
        _ => "100gb_plus",
    };

    private static string BucketPercent(uint percent) => percent switch
    {
        < 50 => "under_50",
        < 75 => "50_74",
        < 90 => "75_89",
        < 95 => "90_94",
        _ => "95_plus",
    };

    private static string BucketRatio(double ratio) => ratio switch
    {
        < 0.5 => "under_50",
        < 0.8 => "50_79",
        < 1.0 => "80_99",
        _ => "100_plus",
    };

    private static string BucketCount(int count) => count switch
    {
        < 1 => "zero",
        < 5 => "1_4",
        < 20 => "5_19",
        _ => "20_plus",
    };

    private static string BucketSeconds(double seconds) => seconds switch
    {
        < 60 => "under_60",
        < 300 => "60_299",
        < 900 => "300_899",
        < 3600 => "900_3599",
        _ => "3600_plus",
    };

    private static string StableHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant()[..16];
    }

    private sealed record DriveSnapshot(string RootHash, string DriveType, long FreeBytes, long TotalBytes);

    private sealed record CpuSample(DateTimeOffset ObservedAt, string ProcessName, TimeSpan TotalProcessorTime);
}
