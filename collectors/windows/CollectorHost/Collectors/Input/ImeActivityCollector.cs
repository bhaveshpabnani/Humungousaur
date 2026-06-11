using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Input;

internal sealed class ImeActivityCollector
{
    private string _lastLayout = "";
    private bool? _lastImeOpen;

    public NativeCollectorEvent? Diff(WindowSnapshot snapshot)
    {
        var layout = NativeMethods.KeyboardLayoutNameForWindow(snapshot.Handle);
        var imeOpen = NativeMethods.ImeOpen(snapshot.Handle);
        if (_lastLayout.Length > 0 && layout.Length > 0 && layout != _lastLayout)
        {
            _lastLayout = layout;
            _lastImeOpen = imeOpen;
            return Create(
                "language_input_switched",
                "Language input switched; composition text omitted.",
                new Dictionary<string, string>
                {
                    ["layout_id"] = layout,
                    ["ime_open"] = imeOpen?.ToString().ToLowerInvariant() ?? "unknown",
                    ["composition_text_omitted"] = "true",
                }
            );
        }
        if (_lastImeOpen is not null && imeOpen is not null && imeOpen != _lastImeOpen)
        {
            _lastLayout = layout;
            _lastImeOpen = imeOpen;
            return Create(
                imeOpen.Value ? "ime_composition_started" : "ime_composition_cancelled",
                "IME composition state changed; composition text omitted.",
                new Dictionary<string, string>
                {
                    ["layout_id"] = layout,
                    ["ime_open"] = imeOpen.Value.ToString().ToLowerInvariant(),
                    ["composition_text_omitted"] = "true",
                    ["candidate_text_omitted"] = "true",
                }
            );
        }
        _lastLayout = layout;
        _lastImeOpen = imeOpen;
        return null;
    }

    private static NativeCollectorEvent Create(string stimulusType, string text, Dictionary<string, string> metadata) =>
        new(CollectorCatalog.ImeActivity, "accessibility", stimulusType, text, metadata, PrivacyTier: "sensitive_metadata");
}
