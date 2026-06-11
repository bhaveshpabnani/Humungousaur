using System.Collections.Concurrent;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Input;

internal sealed class PasteboardWorkflowActivityCollector
{
    private readonly ConcurrentDictionary<string, DateTimeOffset> _lastEmitted = new();

    public IEnumerable<CollectorHostEvent> ObserveKeyDown(uint virtualKey)
    {
        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        var win = NativeMethods.IsKeyDown(NativeMethods.VkLwin) || NativeMethods.IsKeyDown(NativeMethods.VkRwin);
        var pasteboard = PasteboardShortcut(virtualKey, ctrl, shift, win);
        if (pasteboard is null || !Throttle($"pasteboard:{pasteboard}", TimeSpan.FromMilliseconds(500)))
        {
            yield break;
        }
        yield return new CollectorHostEvent(
            CollectorCatalog.PasteboardWorkflowActivity,
            "activity",
            pasteboard,
            PasteboardText(pasteboard),
            new Dictionary<string, string>
            {
                ["shortcut_detected"] = "true",
                ["clipboard_content_omitted"] = "true",
                ["selected_text_omitted"] = "true",
            },
            PrivacyTier: "sensitive_metadata"
        );
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

    private static string? PasteboardShortcut(uint virtualKey, bool ctrl, bool shift, bool win)
    {
        if (win && virtualKey == 0x56) return "clipboard_manager_opened";
        if (!ctrl) return null;
        return virtualKey switch
        {
            0x43 => "copy_performed",
            0x58 => "cut_performed",
            0x56 when shift => "paste_and_match_style_performed",
            0x56 => "paste_performed",
            _ => null,
        };
    }

    private static string PasteboardText(string stimulusType) => stimulusType switch
    {
        "copy_performed" => "Copy performed; clipboard contents omitted.",
        "cut_performed" => "Cut performed; clipboard contents omitted.",
        "paste_performed" => "Paste performed; clipboard contents omitted.",
        "paste_and_match_style_performed" => "Paste and match style performed; clipboard contents omitted.",
        "clipboard_manager_opened" => "Clipboard manager opened; history contents omitted.",
        _ => "Pasteboard workflow changed; contents omitted.",
    };
}
