using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Input;

internal static class TextInputSurfaceActivityCollector
{
    public static CollectorHostEvent? Classify(WindowSnapshot snapshot)
    {
        var className = snapshot.ClassName.ToLowerInvariant();
        var isEdit = className.Contains("edit", StringComparison.Ordinal) || className.Contains("richedit", StringComparison.Ordinal);
        if (!isEdit)
        {
            return null;
        }
        var style = NativeMethods.GetWindowLong(snapshot.Handle, NativeMethods.GwlStyle);
        var secure = (style & NativeMethods.EsPassword) != 0;
        var multiline = (style & NativeMethods.EsMultiline) != 0;
        var stimulus = secure ? "secure_text_field_focused" : multiline ? "multiline_editor_focused" : "text_field_focused";
        return new CollectorHostEvent(
            CollectorCatalog.TextInputSurfaceActivity,
            "accessibility",
            stimulus,
            secure ? "Secure text field focused; field value omitted." : "Text input surface focused; field value omitted.",
            new Dictionary<string, string>
            {
                ["process_id"] = snapshot.ProcessId.ToStringInvariant(),
                ["process_name"] = snapshot.ProcessName,
                ["control_class"] = snapshot.ClassName,
                ["field_value_omitted"] = "true",
                ["secure"] = secure.ToString().ToLowerInvariant(),
                ["multiline"] = multiline.ToString().ToLowerInvariant(),
            },
            PrivacyTier: "sensitive_metadata"
        );
    }
}
