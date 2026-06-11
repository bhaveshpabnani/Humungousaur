using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net.NetworkInformation;
using System.Security.Cryptography;
using System.Text;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Core;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.DeveloperWorkflow;

internal sealed class DeveloperWorkflowActivityCollector : IDisposable
{
    private readonly List<FileSystemWatcher> _watchers = [];
    private readonly Action<NativeCollectorEvent> _emit;
    private readonly ConcurrentDictionary<string, DateTimeOffset> _lastEmitted = new();
    private Dictionary<int, ProcessSnapshot> _processes = SnapshotProcesses();
    private HashSet<string> _listeners = SnapshotLocalListeners();
    private string _lastForegroundSignature = "";

    public DeveloperWorkflowActivityCollector(CollectorHostOptions options, Action<NativeCollectorEvent> emit)
    {
        _emit = emit;
        foreach (var root in ResolveWatchRoots(options.WatchPaths))
        {
            AddWatcher(root);
        }
    }

    public void Dispose()
    {
        foreach (var watcher in _watchers)
        {
            watcher.Dispose();
        }
        _watchers.Clear();
    }

    public IEnumerable<NativeCollectorEvent> Diff()
    {
        foreach (var processEvent in ObserveProcessDiff())
        {
            yield return processEvent;
        }
        foreach (var listenerEvent in ObserveLocalListeners())
        {
            yield return listenerEvent;
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveForeground(WindowSnapshot snapshot)
    {
        var process = SafeProcessName(snapshot.ProcessName);
        var signature = $"{process}:{snapshot.TitleHash}:{snapshot.TitleLength}";
        if (_lastForegroundSignature == signature)
        {
            yield break;
        }
        _lastForegroundSignature = signature;

        var metadata = WindowMetadata(snapshot);
        if (ToolSets.Terminals.Contains(process) && Throttle($"foreground:terminal:{process}", TimeSpan.FromSeconds(5)))
        {
            yield return Create(CollectorCatalog.TerminalActivity, "terminal_command_started", "Terminal focused; command text and arguments omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (ToolSets.Ides.Contains(process) && Throttle($"foreground:ide:{process}", TimeSpan.FromSeconds(5)))
        {
            yield return Create(CollectorCatalog.IdeActivity, "file_opened_in_ide", "IDE/editor focused; active file path and contents omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (ToolSets.GithubApps.Contains(process) && Throttle($"foreground:github:{process}", TimeSpan.FromSeconds(10)))
        {
            yield return Create(CollectorCatalog.GithubActivity, "pr_opened", "GitHub desktop surface focused; repository, PR, and issue identifiers omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (ToolSets.DatabaseClients.Contains(process) && Throttle($"foreground:database:{process}", TimeSpan.FromSeconds(10)))
        {
            yield return Create(CollectorCatalog.DatabaseActivity, "database_connected", "Database client focused; connection details, SQL, and results omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (ToolSets.CloudConsoles.Contains(process) && Throttle($"foreground:cloud:{process}", TimeSpan.FromSeconds(10)))
        {
            yield return Create(CollectorCatalog.CloudConsoleActivity, "cloud_resource_opened", "Cloud console/tool focused; resource identifiers and URLs omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (ToolSets.Debuggers.Contains(process) && Throttle($"foreground:debugger:{process}", TimeSpan.FromSeconds(10)))
        {
            yield return Create(CollectorCatalog.DebuggerActivity, "debugger_attached", "Debugger focused; stack frames and variable values omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveKeyDown(uint virtualKey)
    {
        var snapshot = WindowSnapshot.FromForeground();
        if (snapshot is null)
        {
            yield break;
        }
        var process = SafeProcessName(snapshot.ProcessName);
        var metadata = SensitiveMetadata(WindowMetadata(snapshot));
        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        metadata["modifier_ctrl"] = ctrl.ToString().ToLowerInvariant();
        metadata["modifier_shift"] = shift.ToString().ToLowerInvariant();
        metadata["modifier_alt"] = alt.ToString().ToLowerInvariant();
        metadata["raw_key_omitted"] = "true";

        if (ToolSets.Ides.Contains(process) && virtualKey == (uint)NativeMethods.VkF5 && Throttle("key:ide-debug-start", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.IdeActivity, "debug_session_started", "IDE debug shortcut observed; target and path omitted.", metadata, "sensitive_metadata");
            yield return Create(CollectorCatalog.DebuggerActivity, "debugger_attached", "Debugger start shortcut observed; stack frames and variables omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.Ides.Contains(process) && shift && virtualKey == (uint)NativeMethods.VkF5 && Throttle("key:ide-debug-stop", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.DebuggerActivity, "debugger_detached", "Debugger stop shortcut observed; target and stack omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.Ides.Contains(process) && virtualKey == (uint)NativeMethods.VkF9 && Throttle("key:ide-breakpoint", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.DebuggerActivity, "breakpoint_added", "Breakpoint shortcut observed; file path and line omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.Ides.Contains(process) && ctrl && shift && virtualKey == (uint)NativeMethods.VkB && Throttle("key:ide-build", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.BuildToolActivity, "build_task_started", "IDE build shortcut observed; target and logs omitted.", metadata, "sensitive_metadata");
            yield return Create(CollectorCatalog.TerminalActivity, "build_started", "Build workflow started; command and logs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.Ides.Contains(process) && ctrl && virtualKey == (uint)NativeMethods.VkOem3 && Throttle("key:ide-terminal", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.TerminalActivity, "terminal_command_started", "Integrated terminal opened; command text omitted.", metadata, "sensitive_metadata");
        }
    }

    private IEnumerable<NativeCollectorEvent> ObserveProcessDiff()
    {
        var current = SnapshotProcesses();
        foreach (var pair in current)
        {
            if (!_processes.ContainsKey(pair.Key))
            {
                foreach (var processEvent in ProcessStarted(pair.Value))
                {
                    yield return processEvent;
                }
            }
        }
        foreach (var pair in _processes)
        {
            if (!current.ContainsKey(pair.Key))
            {
                foreach (var processEvent in ProcessStopped(pair.Value))
                {
                    yield return processEvent;
                }
            }
        }
        _processes = current;
    }

    private IEnumerable<NativeCollectorEvent> ObserveLocalListeners()
    {
        var current = SnapshotLocalListeners();
        foreach (var listener in current)
        {
            if (!_listeners.Contains(listener) && Throttle($"listener:start:{listener}", TimeSpan.FromSeconds(2)))
            {
                var metadata = BaseMetadata("windows_ipglobalproperties_tcp_listener");
                metadata["listener_hash"] = StableHash(listener);
                metadata["port_bucket"] = ListenerPortBucket(listener);
                metadata["endpoint_omitted"] = "true";
                yield return Create(CollectorCatalog.LocalServiceActivity, "dev_server_started", "Local TCP listener appeared; endpoint path and logs omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
            }
        }
        foreach (var listener in _listeners)
        {
            if (!current.Contains(listener) && Throttle($"listener:stop:{listener}", TimeSpan.FromSeconds(2)))
            {
                var metadata = BaseMetadata("windows_ipglobalproperties_tcp_listener");
                metadata["listener_hash"] = StableHash(listener);
                metadata["port_bucket"] = ListenerPortBucket(listener);
                metadata["endpoint_omitted"] = "true";
                yield return Create(CollectorCatalog.LocalServiceActivity, "dev_server_stopped", "Local TCP listener stopped; endpoint path and logs omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
            }
        }
        _listeners = current;
    }

    private IEnumerable<NativeCollectorEvent> ProcessStarted(ProcessSnapshot process)
    {
        var metadata = ProcessMetadata(process, "windows_process_snapshot_start");
        if (ToolSets.Terminals.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.TerminalActivity, "terminal_command_started", "Terminal process started; command line omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.PackageManagers.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.PackageManagerActivity, "dependency_install_started", "Package-manager process started; package names and arguments omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.BuildTools.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.BuildToolActivity, "build_task_started", "Build-tool process started; target names and logs omitted.", metadata, "sensitive_metadata");
            yield return Create(CollectorCatalog.TerminalActivity, "build_started", "Build command observed; command line and logs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.TestRunners.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.TestRunnerActivity, "test_suite_started", "Test-runner process started; test names and assertions omitted.", metadata, "sensitive_metadata");
            yield return Create(CollectorCatalog.TerminalActivity, "tests_started", "Test command observed; command line and logs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.LocalServices.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.LocalServiceActivity, "dev_server_started", "Local development service process started; endpoints and logs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.Debuggers.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.DebuggerActivity, "debugger_attached", "Debugger process started; stack frames and variables omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.DatabaseClients.Contains(process.Name) || ToolSets.DatabaseServices.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.DatabaseActivity, "database_connected", "Database tool/process observed; SQL, connection details, and results omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.CloudConsoles.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.CloudConsoleActivity, "cloud_resource_opened", "Cloud CLI/tool process observed; resource identifiers and URLs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.GitTools.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.GitActivity, "working_tree_dirty", "Git process observed; command line, branch, and paths omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.GithubTools.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.GithubActivity, "pr_opened", "GitHub tool process observed; repository and PR identifiers omitted.", metadata, "sensitive_metadata");
        }
    }

    private IEnumerable<NativeCollectorEvent> ProcessStopped(ProcessSnapshot process)
    {
        var metadata = ProcessMetadata(process, "windows_process_snapshot_stop");
        if (ToolSets.Terminals.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.TerminalActivity, "terminal_command_finished", "Terminal process exited; command line and output omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.PackageManagers.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.PackageManagerActivity, "dependency_install_completed", "Package-manager process exited; package names and logs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.BuildTools.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.BuildToolActivity, "build_task_completed", "Build-tool process exited; target names and logs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.TestRunners.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.TestRunnerActivity, "test_suite_completed", "Test-runner process exited; test names and logs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.LocalServices.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.LocalServiceActivity, "dev_server_stopped", "Local development service process exited; endpoints and logs omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.Debuggers.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.DebuggerActivity, "debugger_detached", "Debugger process exited; target and stack omitted.", metadata, "sensitive_metadata");
        }
        if (ToolSets.DatabaseClients.Contains(process.Name) || ToolSets.DatabaseServices.Contains(process.Name))
        {
            yield return Create(CollectorCatalog.DatabaseActivity, "database_disconnected", "Database tool/process exited; SQL and connection details omitted.", metadata, "sensitive_metadata");
        }
    }

    private void AddWatcher(string root)
    {
        if (!Directory.Exists(root))
        {
            return;
        }
        try
        {
            var watcher = new FileSystemWatcher(root)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.DirectoryName | NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.CreationTime,
            };
            watcher.Created += (_, args) => ObserveFileChange(root, args.FullPath, args.ChangeType);
            watcher.Changed += (_, args) => ObserveFileChange(root, args.FullPath, args.ChangeType);
            watcher.Deleted += (_, args) => ObserveFileChange(root, args.FullPath, args.ChangeType);
            watcher.Renamed += (_, args) => ObserveFileChange(root, args.FullPath, args.ChangeType);
            watcher.Error += (_, _) => { };
            watcher.EnableRaisingEvents = true;
            _watchers.Add(watcher);
        }
        catch
        {
            // Developer workflow file watching is best-effort and never blocks the helper.
        }
    }

    private void ObserveFileChange(string root, string path, WatcherChangeTypes changeType)
    {
        foreach (var collectorEvent in ClassifyDeveloperFileChange(root, path, changeType))
        {
            _emit(collectorEvent);
        }
    }

    private IEnumerable<NativeCollectorEvent> ClassifyDeveloperFileChange(string root, string path, WatcherChangeTypes changeType)
    {
        var normalized = Normalize(path);
        var fileName = Path.GetFileName(normalized);
        var extension = Path.GetExtension(normalized);
        var metadata = PathMetadata(root, path, "windows_developer_filesystem");
        metadata["change_kind"] = changeType.ToString().ToLowerInvariant();

        if (IsGitMetadata(normalized, fileName))
        {
            foreach (var gitEvent in ClassifyGitMetadata(normalized, fileName, changeType, metadata))
            {
                yield return gitEvent;
            }
        }
        if (IsLockfile(fileName) && Throttle($"lockfile:{StableHash(normalized)}", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.PackageManagerActivity, "lockfile_changed", "Dependency lockfile changed; package names and path omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsBuildConfig(fileName, extension) && Throttle($"build-config:{StableHash(normalized)}", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.BuildToolActivity, "build_config_changed", "Build configuration changed; target names and path omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsArtifactPath(normalized) && changeType is WatcherChangeTypes.Created or WatcherChangeTypes.Changed && Throttle($"artifact:{StableHash(normalized)}", TimeSpan.FromSeconds(3)))
        {
            yield return Create(CollectorCatalog.BuildToolActivity, "artifact_generated", "Build artifact changed; artifact path and contents omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (IsCoveragePath(normalized) && Throttle($"coverage:{StableHash(normalized)}", TimeSpan.FromSeconds(3)))
        {
            yield return Create(CollectorCatalog.TestRunnerActivity, "coverage_report_generated", "Coverage report changed; test names and coverage details omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (extension.Equals(".snap", StringComparison.OrdinalIgnoreCase) && Throttle($"snapshot:{StableHash(normalized)}", TimeSpan.FromSeconds(3)))
        {
            yield return Create(CollectorCatalog.TestRunnerActivity, "snapshot_test_updated", "Snapshot test artifact changed; expected output omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
    }

    private IEnumerable<NativeCollectorEvent> ClassifyGitMetadata(string normalized, string fileName, WatcherChangeTypes changeType, Dictionary<string, string> metadata)
    {
        if (fileName.Equals("head", StringComparison.OrdinalIgnoreCase) && Throttle($"git-head:{StableHash(normalized)}", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.GitActivity, "git_branch_changed", "Git HEAD changed; branch name and path omitted.", metadata);
            yield return Create(CollectorCatalog.IdeActivity, "git_branch_changed", "IDE git branch context changed; branch name omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (fileName.Equals("index", StringComparison.OrdinalIgnoreCase) && Throttle($"git-index:{StableHash(normalized)}", TimeSpan.FromSeconds(2)))
        {
            yield return Create(CollectorCatalog.GitActivity, "working_tree_dirty", "Git index changed; file paths omitted.", metadata);
        }
        if (fileName.Equals("commit_editmsg", StringComparison.OrdinalIgnoreCase) && changeType is WatcherChangeTypes.Changed or WatcherChangeTypes.Created && Throttle($"git-commit:{StableHash(normalized)}", TimeSpan.FromSeconds(5)))
        {
            yield return Create(CollectorCatalog.GitActivity, "commit_created", "Git commit metadata changed; commit message and files omitted.", metadata);
            yield return Create(CollectorCatalog.IdeActivity, "commit_created", "Commit workflow observed; commit message and files omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (fileName.Equals("merge_head", StringComparison.OrdinalIgnoreCase) && Throttle($"git-merge:{StableHash(normalized)}", TimeSpan.FromSeconds(5)))
        {
            yield return Create(CollectorCatalog.GitActivity, "merge_conflict_detected", "Git merge state changed; conflicted paths omitted.", metadata);
            yield return Create(CollectorCatalog.IdeActivity, "merge_conflict_detected", "Merge conflict state observed; conflicted paths omitted.", SensitiveMetadata(metadata), "sensitive_metadata");
        }
        if (normalized.Contains($"{Path.DirectorySeparatorChar}rebase-merge{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains($"{Path.DirectorySeparatorChar}rebase-apply{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase))
        {
            var stimulusType = fileName.Contains("stopped", StringComparison.OrdinalIgnoreCase) ? "rebase_conflict_detected" : "rebase_started";
            if (Throttle($"git-rebase:{stimulusType}:{StableHash(normalized)}", TimeSpan.FromSeconds(5)))
            {
                yield return Create(CollectorCatalog.GitActivity, stimulusType, "Git rebase state changed; branch names and paths omitted.", metadata);
            }
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

    private static NativeCollectorEvent Create(string collector, string stimulusType, string text, Dictionary<string, string> metadata, string privacyTier = "metadata") =>
        new(collector, "activity", stimulusType, text, metadata, PrivacyTier: privacyTier);

    private static Dictionary<string, string> ProcessMetadata(ProcessSnapshot process, string nativeSource)
    {
        var metadata = BaseMetadata(nativeSource);
        metadata["process_id"] = process.ProcessId.ToStringInvariant();
        metadata["process_name"] = process.Name;
        metadata["tool_kind"] = process.ToolKind;
        metadata["command_line_omitted"] = "true";
        metadata["process_path_omitted"] = "true";
        return SensitiveMetadata(metadata);
    }

    private static Dictionary<string, string> WindowMetadata(WindowSnapshot snapshot)
    {
        var metadata = BaseMetadata("windows_developer_foreground");
        metadata["process_id"] = snapshot.ProcessId.ToStringInvariant();
        metadata["process_name"] = snapshot.ProcessNameOrUnknown;
        metadata["window_class"] = snapshot.ClassName;
        metadata["window_title_omitted"] = "true";
        metadata["window_title_hash"] = snapshot.TitleHash;
        metadata["window_title_length"] = snapshot.TitleLength.ToStringInvariant();
        metadata["screen_content_omitted"] = "true";
        return metadata;
    }

    private static Dictionary<string, string> PathMetadata(string root, string path, string nativeSource)
    {
        var extension = Path.GetExtension(path);
        return new Dictionary<string, string>
        {
            ["native_source"] = nativeSource,
            ["root_digest"] = StableHash(Normalize(root)),
            ["path_digest"] = StableHash(Normalize(path)),
            ["parent_digest"] = StableHash(Normalize(Path.GetDirectoryName(path) ?? "")),
            ["extension"] = SafeExtension(extension),
            ["filename_omitted"] = "true",
            ["path_redacted"] = "true",
            ["contents_omitted"] = "true",
            ["command_line_omitted"] = "true",
            ["log_output_omitted"] = "true",
        };
    }

    private static Dictionary<string, string> BaseMetadata(string nativeSource) => new()
    {
        ["native_source"] = nativeSource,
        ["raw_content_included"] = "false",
        ["text_content_omitted"] = "true",
        ["terminal_text_omitted"] = "true",
        ["log_output_omitted"] = "true",
        ["url_omitted"] = "true",
    };

    private static Dictionary<string, string> SensitiveMetadata(Dictionary<string, string> metadata)
    {
        var copy = new Dictionary<string, string>(metadata);
        copy["sensitive_values_omitted"] = "true";
        copy["raw_text_omitted"] = "true";
        return copy;
    }

    private static Dictionary<int, ProcessSnapshot> SnapshotProcesses()
    {
        try
        {
            return Process.GetProcesses().ToDictionary(
                process => process.Id,
                process =>
                {
                    var name = SafeProcessName(process);
                    return new ProcessSnapshot(process.Id, name, ToolKind(name));
                }
            );
        }
        catch
        {
            return new Dictionary<int, ProcessSnapshot>();
        }
    }

    private static HashSet<string> SnapshotLocalListeners()
    {
        try
        {
            return IPGlobalProperties.GetIPGlobalProperties()
                .GetActiveTcpListeners()
                .Where(endpoint => endpoint.Address.ToString() is "127.0.0.1" or "::1" or "0.0.0.0" or "::")
                .Where(endpoint => IsDeveloperPort(endpoint.Port))
                .Select(endpoint => $"{endpoint.Address}:{endpoint.Port}")
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
        }
        catch
        {
            return new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        }
    }

    private static string ListenerPortBucket(string listener)
    {
        var portText = listener.Split(':').LastOrDefault() ?? "";
        if (!int.TryParse(portText, out var port))
        {
            return "unknown";
        }
        return port switch
        {
            < 1024 => "system",
            < 3000 => "low_dev",
            < 5000 => "frontend_dev",
            < 9000 => "app_dev",
            < 20000 => "service_dev",
            _ => "high_ephemeral",
        };
    }

    private static List<string> ResolveWatchRoots(IReadOnlyList<string> configured)
    {
        var roots = configured.Count > 0 ? configured : [Environment.CurrentDirectory];
        return roots.Select(ExpandPath).Where(Directory.Exists).Distinct(StringComparer.OrdinalIgnoreCase).Take(10).ToList();
    }

    private static string ExpandPath(string path)
    {
        if (path.StartsWith("~", StringComparison.Ordinal))
        {
            var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            return Path.GetFullPath(Path.Combine(home, path.TrimStart('~', '/', '\\')));
        }
        return Path.GetFullPath(path);
    }

    private static bool IsDeveloperPort(int port) =>
        port is 3000 or 3001 or 4173 or 4200 or 4321 or 5000 or 5173 or 5432 or 5601 or 5672 or 6379 or 8000 or 8001 or 8080 or 8081 or 9000 or 9200
        || port is >= 49152 and <= 65535;

    private static bool IsGitMetadata(string normalized, string fileName) =>
        normalized.Contains($"{Path.DirectorySeparatorChar}.git{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase)
        || fileName.Equals(".git", StringComparison.OrdinalIgnoreCase);

    private static bool IsLockfile(string fileName) =>
        ToolSets.Lockfiles.Contains(fileName);

    private static bool IsBuildConfig(string fileName, string extension) =>
        ToolSets.BuildConfigFiles.Contains(fileName)
        || extension is ".csproj" or ".fsproj" or ".vbproj" or ".vcxproj" or ".sln" or ".props" or ".targets" or ".gradle";

    private static bool IsArtifactPath(string normalized)
    {
        var parts = normalized.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        return parts.Any(part => part is "bin" or "obj" or "dist" or "build" or "target" or "out" or ".next");
    }

    private static bool IsCoveragePath(string normalized) =>
        normalized.Contains($"{Path.DirectorySeparatorChar}coverage{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase)
        || normalized.EndsWith($"{Path.DirectorySeparatorChar}coverage.xml", StringComparison.OrdinalIgnoreCase)
        || normalized.EndsWith($"{Path.DirectorySeparatorChar}lcov.info", StringComparison.OrdinalIgnoreCase);

    private static string ToolKind(string processName)
    {
        if (ToolSets.Terminals.Contains(processName)) return "terminal";
        if (ToolSets.Ides.Contains(processName)) return "ide";
        if (ToolSets.PackageManagers.Contains(processName)) return "package_manager";
        if (ToolSets.BuildTools.Contains(processName)) return "build_tool";
        if (ToolSets.TestRunners.Contains(processName)) return "test_runner";
        if (ToolSets.LocalServices.Contains(processName)) return "local_service";
        if (ToolSets.Debuggers.Contains(processName)) return "debugger";
        if (ToolSets.DatabaseClients.Contains(processName) || ToolSets.DatabaseServices.Contains(processName)) return "database";
        if (ToolSets.CloudConsoles.Contains(processName)) return "cloud_console";
        if (ToolSets.GitTools.Contains(processName)) return "git";
        if (ToolSets.GithubTools.Contains(processName) || ToolSets.GithubApps.Contains(processName)) return "github";
        return "developer_tool";
    }

    private static string SafeProcessName(Process process)
    {
        try
        {
            return SafeProcessName(process.ProcessName);
        }
        catch
        {
            return "unknown";
        }
    }

    private static string SafeProcessName(string processName)
    {
        var name = (processName ?? "").Trim();
        return name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? Path.GetFileNameWithoutExtension(name).ToLowerInvariant() : name.ToLowerInvariant();
    }

    private static string SafeExtension(string extension)
    {
        if (string.IsNullOrWhiteSpace(extension))
        {
            return "";
        }
        return ToolSets.SecretExtensions.Contains(extension) ? "" : extension.Trim().ToLowerInvariant();
    }

    private static string Normalize(string path)
    {
        try
        {
            return Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar).ToLowerInvariant();
        }
        catch
        {
            return (path ?? "").Trim().ToLowerInvariant();
        }
    }

    private static string StableHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant()[..16];
    }

    private sealed record ProcessSnapshot(int ProcessId, string Name, string ToolKind);

    private static class ToolSets
    {
        public static readonly HashSet<string> Terminals = new(StringComparer.OrdinalIgnoreCase)
        {
            "cmd", "powershell", "pwsh", "wt", "windowsterminal", "bash", "zsh", "wsl", "ubuntu", "debian", "alacritty", "wezterm", "mintty",
        };

        public static readonly HashSet<string> Ides = new(StringComparer.OrdinalIgnoreCase)
        {
            "code", "codium", "devenv", "rider64", "rider", "idea64", "pycharm64", "webstorm64", "phpstorm64", "goland64", "rubymine64", "clion64", "cursor", "windsurf", "sublime_text", "notepad++",
        };

        public static readonly HashSet<string> PackageManagers = new(StringComparer.OrdinalIgnoreCase)
        {
            "npm", "pnpm", "yarn", "bun", "pip", "pipx", "poetry", "uv", "cargo", "nuget", "composer", "gem", "bundle", "go", "winget", "choco", "scoop",
        };

        public static readonly HashSet<string> BuildTools = new(StringComparer.OrdinalIgnoreCase)
        {
            "msbuild", "dotnet", "csc", "cl", "link", "ninja", "cmake", "make", "mingw32-make", "gradle", "mvn", "webpack", "vite", "rollup", "esbuild", "turbo", "next", "tsc", "javac", "xcodebuild",
        };

        public static readonly HashSet<string> TestRunners = new(StringComparer.OrdinalIgnoreCase)
        {
            "pytest", "jest", "vitest", "mocha", "nunit3-console", "vstest.console", "ctest", "go test", "phpunit", "rspec", "playwright", "cypress",
        };

        public static readonly HashSet<string> LocalServices = new(StringComparer.OrdinalIgnoreCase)
        {
            "node", "deno", "python", "python3", "ruby", "java", "php", "nginx", "httpd", "redis-server", "postgres", "mysqld", "mongod", "docker", "docker-compose",
        };

        public static readonly HashSet<string> Debuggers = new(StringComparer.OrdinalIgnoreCase)
        {
            "vsdbg", "cdb", "windbg", "windbgx", "lldb", "gdb", "debugpy", "node-inspect", "dlv",
        };

        public static readonly HashSet<string> DatabaseClients = new(StringComparer.OrdinalIgnoreCase)
        {
            "psql", "mysql", "sqlite3", "sqlcmd", "mongosh", "redis-cli", "pgadmin4", "dbeaver", "datagrip64", "tableplus",
        };

        public static readonly HashSet<string> DatabaseServices = new(StringComparer.OrdinalIgnoreCase)
        {
            "postgres", "mysqld", "mongod", "redis-server", "sqlservr",
        };

        public static readonly HashSet<string> CloudConsoles = new(StringComparer.OrdinalIgnoreCase)
        {
            "aws", "az", "gcloud", "kubectl", "helm", "terraform", "pulumi", "flyctl", "vercel", "netlify", "wrangler", "doctl",
        };

        public static readonly HashSet<string> GitTools = new(StringComparer.OrdinalIgnoreCase)
        {
            "git",
        };

        public static readonly HashSet<string> GithubTools = new(StringComparer.OrdinalIgnoreCase)
        {
            "gh",
        };

        public static readonly HashSet<string> GithubApps = new(StringComparer.OrdinalIgnoreCase)
        {
            "githubdesktop", "github desktop",
        };

        public static readonly HashSet<string> Lockfiles = new(StringComparer.OrdinalIgnoreCase)
        {
            "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "poetry.lock", "uv.lock", "cargo.lock", "packages.lock.json", "composer.lock", "gemfile.lock", "go.sum",
        };

        public static readonly HashSet<string> BuildConfigFiles = new(StringComparer.OrdinalIgnoreCase)
        {
            "package.json", "pyproject.toml", "cargo.toml", "go.mod", "cmakelists.txt", "makefile", "pom.xml", "build.gradle", "settings.gradle", "vite.config.js", "vite.config.ts", "webpack.config.js", "rollup.config.js", "tsconfig.json", "next.config.js",
        };

        public static readonly HashSet<string> SecretExtensions = new(StringComparer.OrdinalIgnoreCase)
        {
            ".key", ".pem", ".p12", ".pfx", ".crt",
        };
    }
}
