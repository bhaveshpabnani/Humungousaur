using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Window;

internal sealed record WindowSnapshot(
    IntPtr Handle,
    int ProcessId,
    string ProcessName,
    string ClassName,
    bool IsVisible,
    int Width,
    int Height,
    int TitleLength,
    string TitleHash
)
{
    public string ProcessNameOrUnknown => string.IsNullOrWhiteSpace(ProcessName) ? "unknown" : ProcessName;

    public static WindowSnapshot? FromForeground() => FromHandle(NativeMethods.GetForegroundWindow());

    public static WindowSnapshot? FromHandle(IntPtr handle)
    {
        if (handle == IntPtr.Zero)
        {
            return null;
        }
        NativeMethods.GetWindowThreadProcessId(handle, out var processId);
        var processName = "unknown";
        try
        {
            processName = Process.GetProcessById((int)processId).ProcessName;
        }
        catch
        {
            // Process metadata is best-effort and intentionally excludes command lines and paths.
        }
        var className = NativeMethods.ClassName(handle);
        NativeMethods.GetWindowRect(handle, out var rect);
        var title = NativeMethods.WindowTitle(handle);
        return new WindowSnapshot(
            handle,
            (int)processId,
            processName,
            className,
            NativeMethods.IsWindowVisible(handle),
            Math.Max(0, rect.Right - rect.Left),
            Math.Max(0, rect.Bottom - rect.Top),
            title.Length,
            string.IsNullOrEmpty(title) ? "" : StableHash(title)
        );
    }

    public Dictionary<string, string> RedactedMetadata() => new()
    {
        ["window_handle"] = HandleString(Handle),
        ["process_id"] = ProcessId.ToStringInvariant(),
        ["process_name"] = ProcessNameOrUnknown,
        ["app_name"] = ProcessNameOrUnknown,
        ["window_class"] = ClassName,
        ["window_title_omitted"] = "true",
        ["window_title_length"] = TitleLength.ToStringInvariant(),
        ["window_title_hash"] = TitleHash,
        ["visible"] = IsVisible.ToString().ToLowerInvariant(),
    };

    public Dictionary<string, string> RedactedPayload()
    {
        var payload = RedactedMetadata();
        payload["width_bucket"] = Bucket(Width);
        payload["height_bucket"] = Bucket(Height);
        payload["screen_content_omitted"] = "true";
        return payload;
    }

    public static string HandleString(IntPtr handle) => $"0x{handle.ToInt64():x}";

    private static string Bucket(int value) => value switch
    {
        <= 0 => "unknown",
        < 640 => "small",
        < 1280 => "medium",
        < 1920 => "large",
        _ => "xlarge",
    };

    private static string StableHash(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant()[..12];
    }
}
