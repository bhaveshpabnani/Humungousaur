using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Collectors.Browser;

internal sealed class BrowserForegroundCollector
{
    private string _lastTabSignature = "";
    private string _lastFocusedWindow = "";
    private readonly HashSet<string> _knownBrowserWindows = new(StringComparer.OrdinalIgnoreCase);

    public IEnumerable<NativeCollectorEvent> ObserveForeground(WindowSnapshot snapshot)
    {
        if (!BrowserMetadata.IsBrowserProcess(snapshot.ProcessName))
        {
            yield break;
        }

        var metadata = BrowserMetadata.FromWindow(snapshot);
        var handle = WindowSnapshot.HandleString(snapshot.Handle);
        var tabSignature = $"{BrowserMetadata.BrowserKind(snapshot.ProcessName)}:{snapshot.TitleHash}:{snapshot.TitleLength}";
        _knownBrowserWindows.Add(handle);

        yield return new NativeCollectorEvent(
            CollectorCatalog.Browser,
            "browser",
            "browser_tab_changed",
            "Browser foreground tab changed; URL, title, and page contents are omitted.",
            metadata
        );

        yield return new NativeCollectorEvent(
            CollectorCatalog.BrowserLifecycle,
            "browser",
            string.IsNullOrEmpty(_lastTabSignature) || _lastTabSignature == tabSignature ? "browser_tab_observed" : "browser_tab_switched",
            "Browser tab lifecycle observed; URL, title, and page contents are omitted.",
            metadata
        );
        _lastTabSignature = tabSignature;

        if (_lastFocusedWindow != handle)
        {
            yield return new NativeCollectorEvent(
                CollectorCatalog.BrowserWindowActivity,
                "browser",
                "browser_window_focused",
                "Browser window focused; titles and tab lists are omitted.",
                metadata
            );
            _lastFocusedWindow = handle;
        }

    }

    public IEnumerable<NativeCollectorEvent> ObserveWindowOpened(WindowSnapshot snapshot)
    {
        if (!BrowserMetadata.IsBrowserProcess(snapshot.ProcessName))
        {
            yield break;
        }
        _knownBrowserWindows.Add(WindowSnapshot.HandleString(snapshot.Handle));
        yield return new NativeCollectorEvent(
            CollectorCatalog.BrowserWindowActivity,
            "browser",
            "browser_window_opened",
            "Browser window opened; titles and tab lists are omitted.",
            BrowserMetadata.FromWindow(snapshot)
        );
    }

    public IEnumerable<NativeCollectorEvent> ObserveWindowClosed(IntPtr hwnd, int idObject)
    {
        var handle = WindowSnapshot.HandleString(hwnd);
        if (!_knownBrowserWindows.Remove(handle))
        {
            yield break;
        }
        if (_lastFocusedWindow == handle)
        {
            _lastFocusedWindow = "";
        }
        yield return new NativeCollectorEvent(
            CollectorCatalog.BrowserWindowActivity,
            "browser",
            "browser_window_closed",
            "Browser window closed; titles and tab lists are omitted.",
            new Dictionary<string, string>
            {
                ["window_handle"] = handle,
                ["id_object"] = idObject.ToStringInvariant(),
                ["title_omitted"] = "true",
                ["tab_titles_omitted"] = "true",
                ["native_source"] = "windows_winevent_destroy",
            }
        );
    }

    public IEnumerable<NativeCollectorEvent> ObserveKeyDown(uint virtualKeyCode)
    {
        var snapshot = WindowSnapshot.FromForeground();
        if (snapshot is null || !BrowserMetadata.IsBrowserProcess(snapshot.ProcessName))
        {
            yield break;
        }

        var metadata = BrowserMetadata.FromWindow(snapshot);
        var ctrl = NativeMethods.IsKeyDown(NativeMethods.VkControl);
        var alt = NativeMethods.IsKeyDown(NativeMethods.VkMenu);
        var shift = NativeMethods.IsKeyDown(NativeMethods.VkShift);
        metadata["keyboard_shortcut_observed"] = "true";
        metadata["shortcut_text_omitted"] = "true";
        metadata["modifier_ctrl"] = ctrl.ToString().ToLowerInvariant();
        metadata["modifier_alt"] = alt.ToString().ToLowerInvariant();
        metadata["modifier_shift"] = shift.ToString().ToLowerInvariant();

        if (ctrl && virtualKeyCode == (uint)NativeMethods.VkF)
        {
            yield return BrowserViewMode("find_in_page_performed", metadata);
        }
        else if (ctrl && (virtualKeyCode == (uint)NativeMethods.VkOemPlus || virtualKeyCode == (uint)NativeMethods.VkOemMinus || virtualKeyCode == (uint)NativeMethods.VkD0))
        {
            yield return BrowserViewMode("page_zoom_changed", metadata);
        }
        else if (virtualKeyCode == (uint)NativeMethods.VkF5 || (ctrl && virtualKeyCode == (uint)NativeMethods.VkR))
        {
            yield return BrowserLifecycle("browser_reloaded", metadata);
        }
        else if (alt && virtualKeyCode == (uint)NativeMethods.VkLeft)
        {
            yield return BrowserLifecycle("browser_back", metadata);
        }
        else if (alt && virtualKeyCode == (uint)NativeMethods.VkRight)
        {
            yield return BrowserLifecycle("browser_forward", metadata);
        }
        else if (ctrl && virtualKeyCode == (uint)NativeMethods.VkL)
        {
            yield return new NativeCollectorEvent(
                CollectorCatalog.BrowserPageActivity,
                "browser",
                "selected_page_text_changed",
                "Browser location field selection changed; URL text is omitted.",
                metadata,
                PrivacyTier: "sensitive_metadata"
            );
        }
    }

    private static NativeCollectorEvent BrowserLifecycle(string stimulusType, Dictionary<string, string> metadata) =>
        new(
            CollectorCatalog.BrowserLifecycle,
            "browser",
            stimulusType,
            "Browser navigation action observed; URL and title are omitted.",
            metadata
        );

    private static NativeCollectorEvent BrowserViewMode(string stimulusType, Dictionary<string, string> metadata) =>
        new(
            CollectorCatalog.BrowserViewModeActivity,
            "browser",
            stimulusType,
            "Browser view-mode action observed; page contents and query text are omitted.",
            metadata,
            PrivacyTier: "sensitive_metadata"
        );
}
