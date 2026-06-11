using System.Security.Cryptography;
using System.Text;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Browser;

internal static class BrowserMetadata
{
    private static readonly Dictionary<string, string> BrowserProcessNames = new(StringComparer.OrdinalIgnoreCase)
    {
        ["chrome"] = "chrome",
        ["msedge"] = "edge",
        ["firefox"] = "firefox",
        ["brave"] = "brave",
        ["vivaldi"] = "vivaldi",
        ["opera"] = "opera",
        ["opera_gx"] = "opera_gx",
    };

    public static bool IsBrowserProcess(string processName) => BrowserProcessNames.ContainsKey(SafeProcessName(processName));

    public static string BrowserKind(string processName) =>
        BrowserProcessNames.TryGetValue(SafeProcessName(processName), out var kind) ? kind : "browser";

    public static Dictionary<string, string> FromWindow(WindowSnapshot snapshot)
    {
        var browserKind = BrowserKind(snapshot.ProcessName);
        return new Dictionary<string, string>
        {
            ["app_name"] = snapshot.ProcessNameOrUnknown,
            ["browser_kind"] = browserKind,
            ["process_id"] = snapshot.ProcessId.ToStringInvariant(),
            ["window_handle"] = WindowSnapshot.HandleString(snapshot.Handle),
            ["window_class"] = snapshot.ClassName,
            ["window_title_omitted"] = "true",
            ["window_title_length"] = snapshot.TitleLength.ToStringInvariant(),
            ["window_title_hash"] = snapshot.TitleHash,
            ["url_omitted"] = "true",
            ["page_title_omitted"] = "true",
            ["tab_titles_omitted"] = "true",
            ["page_content_omitted"] = "true",
            ["private_url_omitted"] = "true",
            ["native_source"] = "windows_winevent_foreground",
        };
    }

    public static Dictionary<string, string> FromPath(string path, string browserKind, string storeKind)
    {
        var normalized = Normalize(path);
        return new Dictionary<string, string>
        {
            ["browser_kind"] = browserKind,
            ["store_kind"] = storeKind,
            ["path_digest"] = StableHash(normalized),
            ["parent_digest"] = StableHash(Normalize(Path.GetDirectoryName(path) ?? "")),
            ["profile_digest"] = StableHash(ProfileIdentity(path)),
            ["path_redacted"] = "true",
            ["filename_omitted"] = "true",
            ["url_omitted"] = "true",
            ["title_omitted"] = "true",
            ["query_omitted"] = "true",
            ["page_content_omitted"] = "true",
            ["native_source"] = "windows_browser_profile_filesystem",
        };
    }

    public static string StableHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant()[..16];
    }

    public static string Normalize(string path)
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

    private static string ProfileIdentity(string path)
    {
        var normalized = Normalize(path);
        var parts = normalized.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        for (var index = 0; index < parts.Length; index++)
        {
            var part = parts[index];
            if (part.Equals("user data", StringComparison.OrdinalIgnoreCase) && index + 1 < parts.Length)
            {
                return string.Join(Path.DirectorySeparatorChar, parts.Take(index + 2));
            }
            if (part.Equals("profiles", StringComparison.OrdinalIgnoreCase) && index + 1 < parts.Length)
            {
                return string.Join(Path.DirectorySeparatorChar, parts.Take(index + 2));
            }
        }
        return Path.GetDirectoryName(normalized) ?? normalized;
    }

    private static string SafeProcessName(string processName)
    {
        var name = (processName ?? "").Trim();
        return name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? Path.GetFileNameWithoutExtension(name) : name;
    }
}
