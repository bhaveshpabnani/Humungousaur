using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Input;

internal sealed class KeyboardInputActivityCollector
{
    private bool? _capsLockOn;
    private string _keyboardLayout = "";

    public IEnumerable<NativeCollectorEvent> PollKeyboardState()
    {
        var capsLock = NativeMethods.IsKeyToggled(NativeMethods.VkCapital);
        if (_capsLockOn is not null && capsLock != _capsLockOn)
        {
            yield return Create("caps_lock_toggled", "Caps Lock toggled.", new Dictionary<string, string> { ["enabled"] = capsLock.ToString().ToLowerInvariant() });
        }
        _capsLockOn = capsLock;

        var layout = NativeMethods.KeyboardLayoutName();
        if (_keyboardLayout.Length > 0 && layout.Length > 0 && layout != _keyboardLayout)
        {
            yield return Create("keyboard_layout_changed", "Keyboard layout changed.", new Dictionary<string, string> { ["layout_id"] = layout });
        }
        _keyboardLayout = layout;
    }

    private static NativeCollectorEvent Create(string stimulusType, string text, Dictionary<string, string> metadata) =>
        new(CollectorCatalog.KeyboardInputActivity, "system", stimulusType, text, metadata);
}
