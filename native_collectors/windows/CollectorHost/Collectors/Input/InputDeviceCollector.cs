using System.Collections.Concurrent;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Input;

internal sealed class InputDeviceCollector
{
    private readonly ConcurrentDictionary<string, DateTimeOffset> _lastEmitted = new();

    public IEnumerable<NativeCollectorEvent> ObserveKeyDown(uint virtualKey)
    {
        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        var win = NativeMethods.IsKeyDown(NativeMethods.VkLwin) || NativeMethods.IsKeyDown(NativeMethods.VkRwin);
        if (!(ctrl || alt || win))
        {
            yield break;
        }

        var modifierSet = string.Join("+", new[] { ctrl ? "ctrl" : "", alt ? "alt" : "", shift ? "shift" : "", win ? "win" : "" }.Where(value => value.Length > 0));
        var category = KeyCategory(virtualKey);
        if (!Throttle($"keyboard:{modifierSet}:{category}", TimeSpan.FromSeconds(1)))
        {
            yield break;
        }
        yield return new NativeCollectorEvent(
            CollectorCatalog.InputDevice,
            "activity",
            "keyboard_shortcut_pressed",
            "Keyboard shortcut pressed.",
            new Dictionary<string, string>
            {
                ["modifier_set"] = modifierSet,
                ["key_category"] = category,
                ["raw_key_omitted"] = "true",
            }
        );
    }

    public IEnumerable<NativeCollectorEvent> ObserveMouse(IntPtr message)
    {
        string? stimulusType = message.ToInt64() switch
        {
            NativeMethods.WmLButtonDown => "mouse_clicked",
            NativeMethods.WmLButtonDblClk => "mouse_double_clicked",
            NativeMethods.WmRButtonDown => "mouse_right_clicked",
            NativeMethods.WmMouseWheel => "mouse_scroll_burst",
            _ => null,
        };
        if (stimulusType is null || !Throttle($"mouse:{stimulusType}", TimeSpan.FromMilliseconds(250)))
        {
            yield break;
        }
        yield return new NativeCollectorEvent(
            CollectorCatalog.InputDevice,
            "activity",
            stimulusType,
            $"{stimulusType.Replace('_', ' ')}.",
            new Dictionary<string, string> { ["coordinates_omitted"] = "true" }
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

    private static string KeyCategory(uint virtualKey) => virtualKey switch
    {
        >= 0x30 and <= 0x39 => "digit",
        >= 0x41 and <= 0x5A => "letter",
        >= 0x70 and <= 0x87 => "function",
        >= 0x25 and <= 0x28 => "navigation",
        0x1B or 0x09 or 0x0D or 0x2E or 0x2D or 0x24 or 0x23 => "system",
        _ => "other",
    };
}
