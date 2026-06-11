using System.Collections.Concurrent;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.ScreenUi;

internal sealed class ScreenUiMetadataCollector
{
    private readonly ConcurrentDictionary<string, DateTimeOffset> _lastEmitted = new();

    public IEnumerable<NativeCollectorEvent> ObserveForeground(WindowSnapshot snapshot)
    {
        if (IsTaskbarOrShell(snapshot) && Throttle($"taskbar-focus:{snapshot.ClassName}", TimeSpan.FromSeconds(3)))
        {
            yield return CreateSystem(
                CollectorCatalog.DockTaskbarActivity,
                "taskbar_item_clicked",
                "Taskbar surface focused; item labels omitted.",
                snapshot
            );
        }
        if (IsWidgetSurface(snapshot) && Throttle($"widget-focus:{snapshot.ClassName}", TimeSpan.FromSeconds(5)))
        {
            yield return CreateSensitiveSystem(
                CollectorCatalog.WidgetActivity,
                "widget_panel_opened",
                "Widget panel opened; widget names and payloads omitted.",
                snapshot
            );
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveWinEvent(uint eventType, WindowSnapshot snapshot, int idObject, int idChild)
    {
        if (eventType == NativeMethods.EventObjectFocus)
        {
            yield return CreateSensitiveAccessibility(
                CollectorCatalog.AccessibilityContext,
                FocusStimulus(snapshot),
                FocusText(snapshot),
                snapshot,
                idObject,
                idChild
            );
        }
        else if (eventType is NativeMethods.EventObjectSelection or NativeMethods.EventObjectSelectionAdd or NativeMethods.EventObjectSelectionRemove or NativeMethods.EventObjectSelectionWithin)
        {
            yield return CreateSensitiveAccessibility(
                CollectorCatalog.SelectionActivity,
                eventType == NativeMethods.EventObjectSelectionWithin ? "multi_selection_changed" : "item_selected",
                "Selection changed; selected text and item labels omitted.",
                snapshot,
                idObject,
                idChild
            );
            yield return CreateSensitiveAccessibility(
                CollectorCatalog.AccessibilityContext,
                "selected_text_changed",
                "Accessibility selection changed; selected text omitted.",
                snapshot,
                idObject,
                idChild
            );
        }
        else if (eventType == NativeMethods.EventObjectInvoked)
        {
            yield return CreateSensitiveAccessibility(
                CollectorCatalog.CommandActivity,
                "toolbar_button_pressed",
                "UI command invoked; button label omitted.",
                snapshot,
                idObject,
                idChild
            );
        }
        else if (eventType == NativeMethods.EventObjectValueChange)
        {
            yield return CreateSensitiveAccessibility(
                CollectorCatalog.AccessibilityContext,
                "checkbox_toggled",
                "Control value changed; label and value omitted.",
                snapshot,
                idObject,
                idChild
            );
        }
        else if (eventType is NativeMethods.EventSystemMenuStart or NativeMethods.EventSystemMenuPopupStart)
        {
            yield return CreateSensitiveAccessibility(
                CollectorCatalog.AccessibilityContext,
                "menu_opened",
                "Menu opened; menu labels omitted.",
                snapshot,
                idObject,
                idChild
            );
            yield return CreateSensitiveAccessibility(
                CollectorCatalog.CommandActivity,
                eventType == NativeMethods.EventSystemMenuPopupStart ? "context_menu_opened" : "command_palette_opened",
                "Command/menu surface opened; labels omitted.",
                snapshot,
                idObject,
                idChild
            );
        }
        else if (eventType == NativeMethods.EventSystemMenuEnd)
        {
            yield return CreateSensitiveAccessibility(
                CollectorCatalog.CommandActivity,
                "menu_item_selected",
                "Menu interaction completed; selected item label omitted.",
                snapshot,
                idObject,
                idChild
            );
        }
    }

    public IEnumerable<NativeCollectorEvent> ObserveKeyDown(uint virtualKey)
    {
        var foreground = WindowSnapshot.FromForeground();
        if (foreground is null)
        {
            yield break;
        }
        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        var win = NativeMethods.IsKeyDown(NativeMethods.VkLwin) || NativeMethods.IsKeyDown(NativeMethods.VkRwin);
        var metadata = KeyboardMetadata(foreground, ctrl, alt, shift, win);

        foreach (var collectorEvent in ObserveSystemShortcut(virtualKey, ctrl, alt, shift, win, foreground, metadata))
        {
            yield return collectorEvent;
        }
        foreach (var collectorEvent in ObserveUiShortcut(virtualKey, ctrl, alt, shift, win, foreground, metadata))
        {
            yield return collectorEvent;
        }
    }

    private IEnumerable<NativeCollectorEvent> ObserveSystemShortcut(uint virtualKey, bool ctrl, bool alt, bool shift, bool win, WindowSnapshot snapshot, Dictionary<string, string> metadata)
    {
        if (win && virtualKey == 0x41 && Throttle("quick_settings_opened", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.QuickSettingsActivity, "system", "quick_settings_opened", "Quick settings opened.", metadata);
        }
        if (win && virtualKey == 0x57 && Throttle("widget_panel_opened", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.WidgetActivity, "system", "widget_panel_opened", "Widget panel opened; widget names and payloads omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (win && virtualKey == 0x42 && Throttle("taskbar_item_clicked", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.DockTaskbarActivity, "system", "taskbar_item_clicked", "Taskbar focus changed; app labels omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (win && virtualKey == 0x4E && Throttle("tray_notification_clicked", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.MenuBarTrayActivity, "system", "tray_notification_clicked", "Notification/tray surface opened; notification text omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (alt && virtualKey == 0x09 && Throttle("pane_switched", TimeSpan.FromSeconds(1)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.NavigationActivity, "accessibility", "pane_switched", "Application/window switcher used; window titles omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
    }

    private IEnumerable<NativeCollectorEvent> ObserveUiShortcut(uint virtualKey, bool ctrl, bool alt, bool shift, bool win, WindowSnapshot snapshot, Dictionary<string, string> metadata)
    {
        if (!ctrl && !alt && !win)
        {
            yield break;
        }
        if (ctrl && shift && virtualKey == 0x50 && Throttle("command_palette_opened", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.CommandActivity, "accessibility", "command_palette_opened", "Command palette opened; query and command labels omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (ctrl && virtualKey == 0x5A && Throttle("undo_performed", TimeSpan.FromMilliseconds(500)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.EditHistoryActivity, "accessibility", "undo_performed", "Undo performed; edited content omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (ctrl && (virtualKey == 0x59 || (shift && virtualKey == 0x5A)) && Throttle("redo_performed", TimeSpan.FromMilliseconds(500)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.EditHistoryActivity, "accessibility", "redo_performed", "Redo performed; edited content omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (ctrl && virtualKey == 0x53 && Throttle("manual_save_completed", TimeSpan.FromSeconds(1)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.EditHistoryActivity, "accessibility", "manual_save_completed", "Manual save shortcut used; document path and content omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (alt && virtualKey == 0x25 && Throttle("in_app_back", TimeSpan.FromMilliseconds(750)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.NavigationActivity, "accessibility", "in_app_back", "Back navigation used; destination omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (alt && virtualKey == 0x27 && Throttle("in_app_forward", TimeSpan.FromMilliseconds(750)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.NavigationActivity, "accessibility", "in_app_forward", "Forward navigation used; destination omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (ctrl && virtualKey == 0x46 && Throttle("search_result_opened", TimeSpan.FromSeconds(2)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.NavigationActivity, "accessibility", "search_result_opened", "Search/find surface used; query omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if (ctrl && virtualKey == 0x41 && Throttle("multi_selection_changed", TimeSpan.FromSeconds(1)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.SelectionActivity, "accessibility", "multi_selection_changed", "Multi-selection changed; selected labels and text omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
        if ((ctrl || alt || win) && Throttle($"shortcut_action:{virtualKey}:{ctrl}:{alt}:{shift}:{win}", TimeSpan.FromSeconds(1)))
        {
            yield return new NativeCollectorEvent(CollectorCatalog.CommandActivity, "accessibility", "shortcut_action_triggered", "Keyboard shortcut action triggered; raw key content omitted.", metadata, PrivacyTier: "sensitive_metadata");
        }
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

    private static NativeCollectorEvent CreateSensitiveAccessibility(string collector, string stimulusType, string text, WindowSnapshot snapshot, int idObject, int idChild) =>
        new(collector, "accessibility", stimulusType, text, AccessibilityMetadata(snapshot, idObject, idChild), PrivacyTier: "sensitive_metadata");

    private static NativeCollectorEvent CreateSystem(string collector, string stimulusType, string text, WindowSnapshot snapshot) =>
        new(collector, "system", stimulusType, text, ShellMetadata(snapshot));

    private static NativeCollectorEvent CreateSensitiveSystem(string collector, string stimulusType, string text, WindowSnapshot snapshot) =>
        new(collector, "system", stimulusType, text, ShellMetadata(snapshot), PrivacyTier: "sensitive_metadata");

    private static Dictionary<string, string> AccessibilityMetadata(WindowSnapshot snapshot, int idObject, int idChild)
    {
        var metadata = ShellMetadata(snapshot);
        metadata["id_object"] = idObject.ToStringInvariant();
        metadata["id_child"] = idChild.ToStringInvariant();
        metadata["control_name_omitted"] = "true";
        metadata["control_value_omitted"] = "true";
        metadata["selected_text_omitted"] = "true";
        metadata["native_source"] = "windows_winevent_accessibility_metadata";
        return metadata;
    }

    private static Dictionary<string, string> ShellMetadata(WindowSnapshot snapshot) => new()
    {
        ["process_id"] = snapshot.ProcessId.ToStringInvariant(),
        ["process_name"] = snapshot.ProcessName,
        ["window_class"] = snapshot.ClassName,
        ["window_title_omitted"] = "true",
        ["screen_content_omitted"] = "true",
        ["label_omitted"] = "true",
        ["payload_omitted"] = "true",
        ["native_source"] = "windows_winevent_shell_metadata",
    };

    private static Dictionary<string, string> KeyboardMetadata(WindowSnapshot snapshot, bool ctrl, bool alt, bool shift, bool win)
    {
        var metadata = ShellMetadata(snapshot);
        metadata["modifier_set"] = string.Join("+", new[] { ctrl ? "ctrl" : "", alt ? "alt" : "", shift ? "shift" : "", win ? "win" : "" }.Where(value => value.Length > 0));
        metadata["raw_key_omitted"] = "true";
        metadata["native_source"] = "windows_keyboard_shell_metadata";
        return metadata;
    }

    private static string FocusStimulus(WindowSnapshot snapshot)
    {
        var className = snapshot.ClassName.ToLowerInvariant();
        if (className.Contains("button", StringComparison.Ordinal)) return "button_available";
        if (className.Contains("edit", StringComparison.Ordinal)) return "form_field_focused";
        if (className.Contains("list", StringComparison.Ordinal)) return "table_row_selected";
        return "focused_control_changed";
    }

    private static string FocusText(WindowSnapshot snapshot) => FocusStimulus(snapshot) switch
    {
        "button_available" => "Button/control focused; label omitted.",
        "form_field_focused" => "Form field focused; value omitted.",
        "table_row_selected" => "List/table control focused; row labels omitted.",
        _ => "Focused control changed; control label and value omitted.",
    };

    private static bool IsTaskbarOrShell(WindowSnapshot snapshot) =>
        snapshot.ProcessName.Equals("explorer", StringComparison.OrdinalIgnoreCase)
        && (snapshot.ClassName.Contains("Tray", StringComparison.OrdinalIgnoreCase)
            || snapshot.ClassName.Contains("Task", StringComparison.OrdinalIgnoreCase)
            || snapshot.ClassName.Contains("Shell", StringComparison.OrdinalIgnoreCase));

    private static bool IsWidgetSurface(WindowSnapshot snapshot) =>
        snapshot.ProcessName.Contains("widget", StringComparison.OrdinalIgnoreCase)
        || snapshot.ClassName.Contains("Widget", StringComparison.OrdinalIgnoreCase)
        || snapshot.ClassName.Contains("Dashboard", StringComparison.OrdinalIgnoreCase);
}
