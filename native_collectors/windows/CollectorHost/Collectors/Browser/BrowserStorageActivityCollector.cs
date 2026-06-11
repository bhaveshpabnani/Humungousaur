using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Core;

namespace Humungousaur.Collectors.Windows.Collectors.Browser;

internal sealed class BrowserStorageActivityCollector : IDisposable
{
    private readonly List<FileSystemWatcher> _watchers = [];
    private readonly Action<NativeCollectorEvent> _emit;

    public BrowserStorageActivityCollector(CollectorHostOptions options, Action<NativeCollectorEvent> emit)
    {
        _emit = emit;
        foreach (var root in ResolveBrowserRoots(options.WatchPaths))
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

    private void AddWatcher(BrowserRoot root)
    {
        if (!Directory.Exists(root.Path))
        {
            return;
        }
        try
        {
            var watcher = new FileSystemWatcher(root.Path)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.DirectoryName | NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.CreationTime,
            };
            watcher.Created += (_, eventArgs) => ObservePath(root, eventArgs.FullPath, "created");
            watcher.Changed += (_, eventArgs) => ObservePath(root, eventArgs.FullPath, "changed");
            watcher.Deleted += (_, eventArgs) => ObservePath(root, eventArgs.FullPath, "deleted");
            watcher.Renamed += (_, eventArgs) =>
            {
                ObservePath(root, eventArgs.OldFullPath, "deleted");
                ObservePath(root, eventArgs.FullPath, "created");
            };
            watcher.Error += (_, _) => { };
            watcher.EnableRaisingEvents = true;
            _watchers.Add(watcher);
        }
        catch
        {
            // Browser profile folders may be locked or policy-managed. Helper health covers degraded states.
        }
    }

    private void ObservePath(BrowserRoot root, string path, string changeKind)
    {
        var normalized = BrowserMetadata.Normalize(path);
        foreach (var collectorEvent in ClassifyPath(root, normalized, changeKind))
        {
            _emit(collectorEvent);
        }
    }

    private static IEnumerable<NativeCollectorEvent> ClassifyPath(BrowserRoot root, string path, string changeKind)
    {
        if (ShouldSuppress(path))
        {
            yield break;
        }

        var fileName = Path.GetFileName(path);
        var metadata = BrowserMetadata.FromPath(path, root.BrowserKind, "profile_store");
        metadata["browser_profile_change_kind"] = changeKind;

        if (IsProfileDirectory(root, path) && changeKind == "created")
        {
            metadata["browser_profile_name_omitted"] = "true";
            yield return Sensitive(
                CollectorCatalog.BrowserProfileActivity,
                "browser_profile_created",
                "Browser profile directory created; profile name and account details are omitted.",
                metadata
            );
        }

        if (IsExtensionPath(path, root.BrowserKind))
        {
            metadata["extension_id_digest"] = BrowserMetadata.StableHash(ExtensionIdentity(path));
            metadata["extension_name_omitted"] = "true";
            var stimulusType = changeKind switch
            {
                "created" => "extension_installed",
                "deleted" => "extension_removed",
                _ => "extension_enabled",
            };
            yield return Sensitive(
                CollectorCatalog.BrowserExtensionActivity,
                stimulusType,
                "Browser extension metadata changed; extension name and permissions are omitted.",
                metadata
            );
        }

        if (IsWebAppPath(path))
        {
            metadata["web_app_id_digest"] = BrowserMetadata.StableHash(WebAppIdentity(path));
            metadata["web_app_name_omitted"] = "true";
            var stimulusType = changeKind == "deleted" ? "web_app_uninstalled" : "web_app_installed";
            yield return Sensitive(
                CollectorCatalog.BrowserWebAppActivity,
                stimulusType,
                "Browser web app metadata changed; app name and origin are omitted.",
                metadata
            );
        }

        if (IsBookmarkStore(fileName, root.BrowserKind))
        {
            metadata["store_kind"] = "bookmarks";
            yield return Sensitive(
                CollectorCatalog.BookmarkHistoryActivity,
                changeKind == "deleted" ? "bookmark_removed" : "bookmark_added",
                "Browser bookmark store changed; URLs, titles, and queries are omitted.",
                metadata
            );
        }

        if (IsHistoryStore(fileName, root.BrowserKind))
        {
            metadata["store_kind"] = "history";
            yield return Sensitive(
                CollectorCatalog.BookmarkHistoryActivity,
                "history_item_opened",
                "Browser history store changed; URLs, titles, and queries are omitted.",
                metadata
            );
        }

        if (IsPreferenceStore(fileName))
        {
            metadata["store_kind"] = "preferences";
            yield return Sensitive(
                CollectorCatalog.BrowserTabGroupActivity,
                "tab_group_saved",
                "Browser tab-group preference state changed; group names, tab titles, and URLs are omitted.",
                metadata
            );
            yield return Sensitive(
                CollectorCatalog.BookmarkHistoryActivity,
                "saved_tab_group_changed",
                "Saved browser tab-group state changed; group names, tab titles, and URLs are omitted.",
                metadata
            );
        }
    }

    private static NativeCollectorEvent Sensitive(string collector, string stimulusType, string text, Dictionary<string, string> metadata) =>
        new(collector, "browser", stimulusType, text, metadata, PrivacyTier: "sensitive_metadata");

    private static bool IsProfileDirectory(BrowserRoot root, string path)
    {
        if (!Directory.Exists(path))
        {
            return false;
        }
        var parent = BrowserMetadata.Normalize(Path.GetDirectoryName(path) ?? "");
        if (!parent.Equals(BrowserMetadata.Normalize(root.Path), StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }
        var name = Path.GetFileName(path);
        return name.Equals("Default", StringComparison.OrdinalIgnoreCase)
            || name.StartsWith("Profile ", StringComparison.OrdinalIgnoreCase)
            || (root.BrowserKind == "firefox" && name.EndsWith(".default-release", StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsExtensionPath(string path, string browserKind)
    {
        var parts = Split(path);
        return browserKind == "firefox"
            ? parts.Contains("extensions", StringComparer.OrdinalIgnoreCase)
            : parts.Contains("extensions", StringComparer.OrdinalIgnoreCase) && !Path.GetFileName(path).StartsWith("_", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsWebAppPath(string path) =>
        Split(path).Any(part => part.Equals("web applications", StringComparison.OrdinalIgnoreCase)
            || part.Equals("webappsstore.sqlite", StringComparison.OrdinalIgnoreCase)
            || part.Equals("manifest resources", StringComparison.OrdinalIgnoreCase));

    private static bool IsBookmarkStore(string fileName, string browserKind) =>
        fileName.Equals("Bookmarks", StringComparison.OrdinalIgnoreCase)
            || (browserKind == "firefox" && fileName.Equals("places.sqlite", StringComparison.OrdinalIgnoreCase));

    private static bool IsHistoryStore(string fileName, string browserKind) =>
        fileName.Equals("History", StringComparison.OrdinalIgnoreCase)
            || fileName.Equals("Visited Links", StringComparison.OrdinalIgnoreCase)
            || (browserKind == "firefox" && (fileName.Equals("places.sqlite", StringComparison.OrdinalIgnoreCase) || fileName.Equals("places.sqlite-wal", StringComparison.OrdinalIgnoreCase)));

    private static bool IsPreferenceStore(string fileName) =>
        fileName.Equals("Preferences", StringComparison.OrdinalIgnoreCase)
            || fileName.Equals("Secure Preferences", StringComparison.OrdinalIgnoreCase);

    private static string ExtensionIdentity(string path)
    {
        var parts = Split(path);
        var index = Array.FindIndex(parts, part => part.Equals("extensions", StringComparison.OrdinalIgnoreCase));
        return index >= 0 && index + 1 < parts.Length ? parts[index + 1] : path;
    }

    private static string WebAppIdentity(string path)
    {
        var parts = Split(path);
        var index = Array.FindIndex(parts, part => part.Equals("web applications", StringComparison.OrdinalIgnoreCase));
        return index >= 0 && index + 1 < parts.Length ? parts[index + 1] : path;
    }

    private static string[] Split(string path) => BrowserMetadata.Normalize(path).Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

    private static bool ShouldSuppress(string path)
    {
        var parts = Split(path);
        return parts.Any(part => part.Equals("cache", StringComparison.OrdinalIgnoreCase)
            || part.Equals("code cache", StringComparison.OrdinalIgnoreCase)
            || part.Equals("gpucache", StringComparison.OrdinalIgnoreCase)
            || part.Equals("crashpad", StringComparison.OrdinalIgnoreCase)
            || part.Equals("service worker", StringComparison.OrdinalIgnoreCase)
            || part.Equals("session storage", StringComparison.OrdinalIgnoreCase)
            || part.Equals("local storage", StringComparison.OrdinalIgnoreCase)
            || part.Equals("indexeddb", StringComparison.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<BrowserRoot> ResolveBrowserRoots(IReadOnlyList<string> configured)
    {
        var roots = new List<BrowserRoot>();
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        if (!string.IsNullOrWhiteSpace(localAppData))
        {
            roots.Add(new BrowserRoot("chrome", Path.Combine(localAppData, "Google", "Chrome", "User Data")));
            roots.Add(new BrowserRoot("edge", Path.Combine(localAppData, "Microsoft", "Edge", "User Data")));
            roots.Add(new BrowserRoot("brave", Path.Combine(localAppData, "BraveSoftware", "Brave-Browser", "User Data")));
            roots.Add(new BrowserRoot("vivaldi", Path.Combine(localAppData, "Vivaldi", "User Data")));
        }
        if (!string.IsNullOrWhiteSpace(appData))
        {
            roots.Add(new BrowserRoot("firefox", Path.Combine(appData, "Mozilla", "Firefox", "Profiles")));
            roots.Add(new BrowserRoot("opera", Path.Combine(appData, "Opera Software", "Opera Stable")));
            roots.Add(new BrowserRoot("opera_gx", Path.Combine(appData, "Opera Software", "Opera GX Stable")));
        }

        roots.AddRange(configured
            .Where(path => path.Contains("browser", StringComparison.OrdinalIgnoreCase) || path.Contains("chrome", StringComparison.OrdinalIgnoreCase) || path.Contains("edge", StringComparison.OrdinalIgnoreCase) || path.Contains("firefox", StringComparison.OrdinalIgnoreCase))
            .Select(path => new BrowserRoot("configured_browser", Environment.ExpandEnvironmentVariables(path))));

        return roots
            .Where(root => Directory.Exists(root.Path))
            .GroupBy(root => BrowserMetadata.Normalize(root.Path), StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .Take(16)
            .ToList();
    }

    private sealed record BrowserRoot(string BrowserKind, string Path);
}
