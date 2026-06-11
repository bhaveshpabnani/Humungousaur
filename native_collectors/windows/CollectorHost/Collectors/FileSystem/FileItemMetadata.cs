using System.Security.Cryptography;
using System.Text;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.FileSystem;

internal static class FileItemMetadata
{
    private static readonly HashSet<string> SecretExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".key",
        ".pem",
        ".p12",
        ".pfx",
        ".crt",
    };

    public static Dictionary<string, string> FromPath(string path, string root, string kind)
    {
        var extension = "";
        var exists = false;
        long sizeBytes = 0;
        try
        {
            extension = Path.GetExtension(path);
            exists = File.Exists(path) || Directory.Exists(path);
            if (File.Exists(path))
            {
                sizeBytes = new FileInfo(path).Length;
            }
        }
        catch
        {
            // Metadata is best-effort and never falls back to reading contents.
        }

        return new Dictionary<string, string>
        {
            ["path_digest"] = StableHash(Normalize(path)),
            ["parent_digest"] = StableHash(Normalize(Path.GetDirectoryName(path) ?? "")),
            ["root_digest"] = StableHash(Normalize(root)),
            ["kind"] = kind,
            ["extension"] = SafeExtension(extension),
            ["size_bucket"] = SizeBucket(sizeBytes),
            ["exists"] = exists.ToString().ToLowerInvariant(),
            ["path_redacted"] = "true",
            ["filename_omitted"] = "true",
            ["contents_omitted"] = "true",
            ["secret_like_path_suppressed"] = IsSecretLikePath(path).ToString().ToLowerInvariant(),
            ["native_source"] = "windows_read_directory_changes",
        };
    }

    public static bool ShouldSuppress(string path)
    {
        var parts = Normalize(path).Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (parts.Any(part => part.Equals(".git", StringComparison.OrdinalIgnoreCase)
                || part.Equals(".venv", StringComparison.OrdinalIgnoreCase)
                || part.Equals("node_modules", StringComparison.OrdinalIgnoreCase)
                || part.Equals("__pycache__", StringComparison.OrdinalIgnoreCase)
                || part.Equals("artifacts", StringComparison.OrdinalIgnoreCase)
                || part.Equals(".codex", StringComparison.OrdinalIgnoreCase)))
        {
            return true;
        }
        return IsSecretLikePath(path);
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
            return path.ToLowerInvariant();
        }
    }

    private static string SafeExtension(string extension)
    {
        if (string.IsNullOrWhiteSpace(extension) || SecretExtensions.Contains(extension))
        {
            return "";
        }
        return extension.Trim().ToLowerInvariant();
    }

    private static bool IsSecretLikePath(string path)
    {
        var name = Path.GetFileName(path).ToLowerInvariant();
        return name == ".env" || name.StartsWith(".env.", StringComparison.Ordinal) || SecretExtensions.Contains(Path.GetExtension(path));
    }

    private static string SizeBucket(long bytes) => bytes switch
    {
        <= 0 => "unknown_or_empty",
        < 1_024 => "under_1kb",
        < 1_048_576 => "1kb_1mb",
        < 104_857_600 => "1mb_100mb",
        _ => "100mb_plus",
    };
}
