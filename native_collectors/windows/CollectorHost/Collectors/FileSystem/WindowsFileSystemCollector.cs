using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Core;

namespace Humungousaur.Collectors.Windows.Collectors.FileSystem;

internal sealed class WindowsFileSystemCollector : IDisposable
{
    private readonly List<FileSystemWatcher> _watchers = [];
    private readonly List<string> _downloadRoots;
    private readonly List<string> _trashRoots;
    private readonly Action<NativeCollectorEvent> _emit;

    public WindowsFileSystemCollector(CollectorHostOptions options, Action<NativeCollectorEvent> emit)
    {
        _emit = emit;
        var watchRoots = ResolveWatchRoots(options.WatchPaths);
        _downloadRoots = ResolveDownloadRoots(options.WatchPaths);
        _trashRoots = ResolveTrashRoots();
        foreach (var root in watchRoots.Concat(_downloadRoots).Concat(_trashRoots).Distinct(StringComparer.OrdinalIgnoreCase))
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
            watcher.Created += (_, eventArgs) => EmitForChange(root, eventArgs.FullPath, eventArgs.ChangeType, oldPath: null);
            watcher.Changed += (_, eventArgs) => EmitForChange(root, eventArgs.FullPath, eventArgs.ChangeType, oldPath: null);
            watcher.Deleted += (_, eventArgs) => EmitForChange(root, eventArgs.FullPath, eventArgs.ChangeType, oldPath: null);
            watcher.Renamed += (_, eventArgs) => EmitForChange(root, eventArgs.FullPath, eventArgs.ChangeType, eventArgs.OldFullPath);
            watcher.Error += (_, _) => { };
            watcher.EnableRaisingEvents = true;
            _watchers.Add(watcher);
        }
        catch
        {
            // Permission-sensitive roots such as recycle-bin folders are best-effort.
        }
    }

    private void EmitForChange(string root, string path, WatcherChangeTypes changeType, string? oldPath)
    {
        if (FileItemMetadata.ShouldSuppress(path) || (oldPath is not null && FileItemMetadata.ShouldSuppress(oldPath)))
        {
            return;
        }
        var kind = Directory.Exists(path) ? "folder" : "file";
        var metadata = FileItemMetadata.FromPath(path, root, kind);
        if (oldPath is not null)
        {
            metadata["previous_path_digest"] = FileItemMetadata.StableHash(FileItemMetadata.Normalize(oldPath));
        }

        if (kind == "file")
        {
            EmitFilesystem(changeType, metadata);
            EmitDownloads(path, metadata);
            EmitFileOperation(path, oldPath, metadata, changeType);
        }
        else
        {
            EmitFolderNavigation(path, oldPath, metadata, changeType);
        }
        EmitTrash(path, metadata, changeType, kind);
    }

    private void EmitFilesystem(WatcherChangeTypes changeType, Dictionary<string, string> metadata)
    {
        var stimulusType = changeType switch
        {
            WatcherChangeTypes.Created => "file_created",
            WatcherChangeTypes.Deleted => "file_deleted",
            WatcherChangeTypes.Renamed => "file_changed",
            _ => "file_modified",
        };
        _emit(new NativeCollectorEvent(
            CollectorCatalog.Filesystem,
            "activity",
            stimulusType,
            stimulusType.Replace("_", " ").CapitalizeSentence(),
            metadata
        ));
    }

    private void EmitDownloads(string path, Dictionary<string, string> metadata)
    {
        if (!_downloadRoots.Any(root => IsUnder(path, root)))
        {
            return;
        }
        _emit(new NativeCollectorEvent(
            CollectorCatalog.Downloads,
            "activity",
            "downloaded_file",
            "Downloaded or exported file changed; filename and contents omitted.",
            metadata
        ));
    }

    private void EmitFileOperation(string path, string? oldPath, Dictionary<string, string> metadata, WatcherChangeTypes changeType)
    {
        var stimulusType = changeType switch
        {
            WatcherChangeTypes.Created => "file_saved",
            WatcherChangeTypes.Changed => "file_saved",
            WatcherChangeTypes.Renamed when oldPath is not null && Path.GetDirectoryName(oldPath) != Path.GetDirectoryName(path) => "file_moved",
            WatcherChangeTypes.Renamed => "file_renamed",
            _ => "",
        };
        if (stimulusType.Length == 0)
        {
            return;
        }
        metadata["file_action"] = stimulusType.Replace("file_", "");
        _emit(new NativeCollectorEvent(
            CollectorCatalog.FileOperationActivity,
            "activity",
            stimulusType,
            stimulusType.Replace("_", " ").CapitalizeSentence(),
            metadata,
            PrivacyTier: "sensitive_metadata"
        ));
    }

    private void EmitFolderNavigation(string path, string? oldPath, Dictionary<string, string> metadata, WatcherChangeTypes changeType)
    {
        var stimulusType = changeType switch
        {
            WatcherChangeTypes.Created => "folder_created",
            WatcherChangeTypes.Changed => "folder_changed",
            WatcherChangeTypes.Renamed when oldPath is not null && Path.GetDirectoryName(oldPath) != Path.GetDirectoryName(path) => "folder_moved",
            WatcherChangeTypes.Renamed => "folder_renamed",
            _ => "",
        };
        if (stimulusType.Length == 0)
        {
            return;
        }
        metadata["folder_action"] = stimulusType.Replace("folder_", "");
        _emit(new NativeCollectorEvent(
            CollectorCatalog.FolderNavigationActivity,
            "activity",
            stimulusType,
            stimulusType.Replace("_", " ").CapitalizeSentence(),
            metadata,
            PrivacyTier: "sensitive_metadata"
        ));
    }

    private void EmitTrash(string path, Dictionary<string, string> metadata, WatcherChangeTypes changeType, string kind)
    {
        if (!_trashRoots.Any(root => IsUnder(path, root)))
        {
            return;
        }
        var stimulusType = changeType switch
        {
            WatcherChangeTypes.Created when kind == "folder" => "folder_moved_to_trash",
            WatcherChangeTypes.Created => "file_moved_to_trash",
            WatcherChangeTypes.Deleted => "trash_item_deleted",
            _ => "",
        };
        if (stimulusType.Length == 0)
        {
            return;
        }
        metadata["trash_action"] = stimulusType;
        _emit(new NativeCollectorEvent(
            CollectorCatalog.TrashActivity,
            "activity",
            stimulusType,
            stimulusType.Replace("_", " ").CapitalizeSentence(),
            metadata,
            PrivacyTier: "sensitive_metadata"
        ));
    }

    private static List<string> ResolveWatchRoots(IReadOnlyList<string> configured)
    {
        var roots = configured.Count > 0 ? configured : [Environment.CurrentDirectory];
        return roots.Select(ExpandPath).Where(Directory.Exists).Distinct(StringComparer.OrdinalIgnoreCase).Take(10).ToList();
    }

    private static List<string> ResolveDownloadRoots(IReadOnlyList<string> configured)
    {
        var roots = new List<string>();
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        if (!string.IsNullOrWhiteSpace(home))
        {
            roots.Add(Path.Combine(home, "Downloads"));
        }
        roots.AddRange(configured.Select(ExpandPath).Where(path => path.Contains("download", StringComparison.OrdinalIgnoreCase)));
        return roots.Where(Directory.Exists).Distinct(StringComparer.OrdinalIgnoreCase).Take(5).ToList();
    }

    private static List<string> ResolveTrashRoots()
    {
        var roots = new List<string>();
        var driveRoots = DriveInfo.GetDrives().Where(drive => drive.IsReady).Select(drive => drive.RootDirectory.FullName);
        foreach (var driveRoot in driveRoots)
        {
            var recycleRoot = Path.Combine(driveRoot, "$Recycle.Bin");
            if (Directory.Exists(recycleRoot))
            {
                roots.Add(recycleRoot);
            }
        }
        return roots.Take(10).ToList();
    }

    private static bool IsUnder(string path, string root)
    {
        var normalizedPath = FileItemMetadata.Normalize(path);
        var normalizedRoot = FileItemMetadata.Normalize(root);
        return normalizedPath.Equals(normalizedRoot, StringComparison.OrdinalIgnoreCase)
            || normalizedPath.StartsWith(normalizedRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
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
}

internal static class FileSystemTextExtensions
{
    public static string CapitalizeSentence(this string value) =>
        string.IsNullOrWhiteSpace(value) ? value : char.ToUpperInvariant(value[0]) + value[1..];
}
