using System.Runtime.InteropServices;
using Humungousaur.Collectors.Windows.Collectors.Application;
using Humungousaur.Collectors.Windows.Collectors.Browser;
using Humungousaur.Collectors.Windows.Collectors.Communication;
using Humungousaur.Collectors.Windows.Collectors.DeveloperWorkflow;
using Humungousaur.Collectors.Windows.Collectors.Device;
using Humungousaur.Collectors.Windows.Collectors.FileSystem;
using Humungousaur.Collectors.Windows.Collectors.Input;
using Humungousaur.Collectors.Windows.Collectors.MailCalendar;
using Humungousaur.Collectors.Windows.Collectors.ScreenUi;
using Humungousaur.Collectors.Windows.Collectors.SystemSurfaces;
using Humungousaur.Collectors.Windows.Collectors.Window;
using Humungousaur.Collectors.Windows.Collectors.Workspace;
using Humungousaur.Collectors.Windows.Contracts;
using Humungousaur.Collectors.Windows.Win32;

namespace Humungousaur.Collectors.Windows.Core;

internal sealed class WindowsCoreOsContextHelper
{
    private readonly CollectorHostOptions _options;
    private readonly HelperHealthReporter _health;
    private readonly CollectorEventSink _sink;
    private WindowsFileSystemCollector? _fileSystem;
    private BrowserStorageActivityCollector? _browserStorage;
    private DeveloperWorkflowActivityCollector? _developerWorkflow;
    private MailCalendarActivityCollector? _mailCalendar;
    private readonly BrowserForegroundCollector _browserForeground = new();
    private readonly ExplorerFileManagerActivityCollector _fileManagerActivity = new();
    private readonly ScreenUiMetadataCollector _screenUiMetadata = new();
    private readonly SystemSurfaceActivityCollector _systemSurfaces = new();
    private readonly WorkspaceActivityCollector _workspaceActivity = new();
    private readonly CommunicationActivityCollector _communicationActivity = new();
    private readonly AppLifecycleCollector _appLifecycle = new();
    private readonly DeviceStateCollector _deviceState = new();
    private readonly InputDeviceCollector _inputDevice = new();
    private readonly KeyboardInputActivityCollector _keyboardInput = new();
    private readonly PasteboardWorkflowActivityCollector _pasteboardWorkflow = new();
    private readonly WindowLifecycleCollector _windowLifecycle = new();
    private readonly ImeActivityCollector _imeActivity = new();
    private NativeMethods.WinEventDelegate? _winEventDelegate;
    private NativeMethods.LowLevelKeyboardProc? _keyboardDelegate;
    private NativeMethods.LowLevelMouseProc? _mouseDelegate;
    private IntPtr _winEventFocusHook;
    private IntPtr _winEventCreateHook;
    private IntPtr _winEventDestroyHook;
    private IntPtr _winEventLocationHook;
    private IntPtr _winEventAccessibilityHook;
    private IntPtr _winEventMenuHook;
    private IntPtr _keyboardHook;
    private IntPtr _mouseHook;
    private IDisposable? _messageWindow;

    public WindowsCoreOsContextHelper(CollectorHostOptions options)
    {
        _options = options;
        _health = new HelperHealthReporter(options);
        _sink = new CollectorEventSink(options, _health);
    }

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        await _health.ReportForAllAsync("starting", "metadata-only Windows core OS context helper starting.", cancellationToken);
        if (!OperatingSystem.IsWindows())
        {
            await _health.ReportForAllAsync("degraded", "Windows collector host can only observe native OS APIs on Windows.", cancellationToken);
            return;
        }

        _fileSystem = new WindowsFileSystemCollector(_options, collectorEvent => _ = _sink.EmitAsync(collectorEvent, CancellationToken.None));
        _browserStorage = new BrowserStorageActivityCollector(_options, collectorEvent => _ = _sink.EmitAsync(collectorEvent, CancellationToken.None));
        _developerWorkflow = new DeveloperWorkflowActivityCollector(_options, collectorEvent => _ = _sink.EmitAsync(collectorEvent, CancellationToken.None));
        _mailCalendar = new MailCalendarActivityCollector(_options, collectorEvent => _ = _sink.EmitAsync(collectorEvent, CancellationToken.None));
        InstallHooks();
        await EmitInitialSnapshotAsync(cancellationToken);
        await _health.ReportForAllAsync("running", "Windows hooks and snapshot loops are active.", cancellationToken);

        if (_options.Once)
        {
            await PollAsync(cancellationToken);
            await _health.ReportForAllAsync("stopped", "One-shot Windows core OS context helper completed.", cancellationToken);
            UninstallHooks();
            return;
        }

        var polling = Task.Run(async () =>
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                await PollAsync(cancellationToken);
                await Task.Delay(_options.Interval, cancellationToken);
            }
        }, cancellationToken);

        try
        {
            NativeMessageLoop.Run(cancellationToken);
        }
        finally
        {
            UninstallHooks();
            await _health.ReportForAllAsync("stopped", "Windows core OS context helper stopped.", CancellationToken.None);
            await polling.WaitAsync(TimeSpan.FromSeconds(2)).ContinueWith(_ => { }, CancellationToken.None);
        }
    }

    private async Task EmitInitialSnapshotAsync(CancellationToken cancellationToken)
    {
        var foreground = WindowSnapshot.FromForeground();
        if (foreground is null)
        {
            return;
        }
        await EmitForegroundContextAsync(foreground, cancellationToken);
    }

    private async Task PollAsync(CancellationToken cancellationToken)
    {
        foreach (var appEvent in _appLifecycle.Diff())
        {
            await _sink.EmitAsync(appEvent, cancellationToken);
        }
        foreach (var deviceEvent in _deviceState.Diff())
        {
            await _sink.EmitAsync(deviceEvent, cancellationToken);
        }
        foreach (var systemSurfaceEvent in _systemSurfaces.Diff())
        {
            await _sink.EmitAsync(systemSurfaceEvent, cancellationToken);
        }
        foreach (var workspaceEvent in _workspaceActivity.Diff())
        {
            await _sink.EmitAsync(workspaceEvent, cancellationToken);
        }
        foreach (var communicationEvent in _communicationActivity.Diff())
        {
            await _sink.EmitAsync(communicationEvent, cancellationToken);
        }
        if (_developerWorkflow is not null)
        {
            foreach (var developerEvent in _developerWorkflow.Diff())
            {
                await _sink.EmitAsync(developerEvent, cancellationToken);
            }
        }
        if (_mailCalendar is not null)
        {
            foreach (var mailCalendarEvent in _mailCalendar.Diff())
            {
                await _sink.EmitAsync(mailCalendarEvent, cancellationToken);
            }
        }

        var foreground = WindowSnapshot.FromForeground();
        if (foreground is not null)
        {
            if (_windowLifecycle.MarkForegroundChanged(foreground))
            {
                await EmitForegroundContextAsync(foreground, cancellationToken);
            }
            if (_windowLifecycle.MarkGeometryChanged(foreground))
            {
                await _sink.EmitAsync(WindowLifecycleCollector.Create("window_resized", foreground), cancellationToken);
                await EmitAllAsync(_workspaceActivity.ObserveWindowGeometry(foreground), cancellationToken);
            }
            await EmitIfPresentAsync(_imeActivity.Diff(foreground), cancellationToken);
        }

        foreach (var keyboardEvent in _keyboardInput.PollKeyboardState())
        {
            await _sink.EmitAsync(keyboardEvent, cancellationToken);
        }
    }

    private async Task EmitForegroundContextAsync(WindowSnapshot snapshot, CancellationToken cancellationToken)
    {
        await _sink.EmitAsync(ActiveWindowCollector.Create(snapshot), cancellationToken);
        await _sink.EmitAsync(WindowLifecycleCollector.Create("window_focused", snapshot), cancellationToken);
        await _sink.EmitAsync(AppLifecycleCollector.CreateFocus(snapshot.ProcessId, snapshot.ProcessName), cancellationToken);
        await EmitAllAsync(_browserForeground.ObserveForeground(snapshot), cancellationToken);
        await EmitAllAsync(_screenUiMetadata.ObserveForeground(snapshot), cancellationToken);
        await EmitAllAsync(_systemSurfaces.ObserveForeground(snapshot), cancellationToken);
        await EmitAllAsync(_workspaceActivity.ObserveForeground(snapshot), cancellationToken);
        await EmitAllAsync(_communicationActivity.ObserveForeground(snapshot), cancellationToken);
        if (_developerWorkflow is not null)
        {
            await EmitAllAsync(_developerWorkflow.ObserveForeground(snapshot), cancellationToken);
        }
        if (_mailCalendar is not null)
        {
            await EmitAllAsync(_mailCalendar.ObserveForeground(snapshot), cancellationToken);
        }
        await EmitIfPresentAsync(TextInputSurfaceActivityCollector.Classify(snapshot), cancellationToken);
        await EmitIfPresentAsync(_imeActivity.Diff(snapshot), cancellationToken);
    }

    private async Task EmitIfPresentAsync(NativeCollectorEvent? collectorEvent, CancellationToken cancellationToken)
    {
        if (collectorEvent is not null)
        {
            await _sink.EmitAsync(collectorEvent, cancellationToken);
        }
    }

    private async Task EmitAllAsync(IEnumerable<NativeCollectorEvent> collectorEvents, CancellationToken cancellationToken)
    {
        foreach (var collectorEvent in collectorEvents)
        {
            await _sink.EmitAsync(collectorEvent, cancellationToken);
        }
    }

    private void InstallHooks()
    {
        _messageWindow = NativeMessageLoop.CreateMessageWindow(OnSystemMessage);
        _winEventDelegate = OnWinEvent;
        _winEventFocusHook = NativeMethods.SetWinEventHook(NativeMethods.EventSystemForeground, NativeMethods.EventSystemForeground, IntPtr.Zero, _winEventDelegate, 0, 0, NativeMethods.WineventOutOfContext | NativeMethods.WineventSkipOwnProcess);
        _winEventCreateHook = NativeMethods.SetWinEventHook(NativeMethods.EventObjectCreate, NativeMethods.EventObjectCreate, IntPtr.Zero, _winEventDelegate, 0, 0, NativeMethods.WineventOutOfContext | NativeMethods.WineventSkipOwnProcess);
        _winEventDestroyHook = NativeMethods.SetWinEventHook(NativeMethods.EventObjectDestroy, NativeMethods.EventObjectDestroy, IntPtr.Zero, _winEventDelegate, 0, 0, NativeMethods.WineventOutOfContext | NativeMethods.WineventSkipOwnProcess);
        _winEventLocationHook = NativeMethods.SetWinEventHook(NativeMethods.EventObjectLocationChange, NativeMethods.EventObjectLocationChange, IntPtr.Zero, _winEventDelegate, 0, 0, NativeMethods.WineventOutOfContext | NativeMethods.WineventSkipOwnProcess);
        _winEventAccessibilityHook = NativeMethods.SetWinEventHook(NativeMethods.EventObjectFocus, NativeMethods.EventObjectInvoked, IntPtr.Zero, _winEventDelegate, 0, 0, NativeMethods.WineventOutOfContext | NativeMethods.WineventSkipOwnProcess);
        _winEventMenuHook = NativeMethods.SetWinEventHook(NativeMethods.EventSystemMenuStart, NativeMethods.EventSystemMenuPopupEnd, IntPtr.Zero, _winEventDelegate, 0, 0, NativeMethods.WineventOutOfContext | NativeMethods.WineventSkipOwnProcess);

        _keyboardDelegate = OnKeyboardEvent;
        _mouseDelegate = OnMouseEvent;
        var moduleHandle = NativeMethods.GetModuleHandle(null);
        _keyboardHook = NativeMethods.SetWindowsHookEx(NativeMethods.WhKeyboardLl, _keyboardDelegate, moduleHandle, 0);
        _mouseHook = NativeMethods.SetWindowsHookEx(NativeMethods.WhMouseLl, _mouseDelegate, moduleHandle, 0);
    }

    private void UninstallHooks()
    {
        if (_winEventFocusHook != IntPtr.Zero) NativeMethods.UnhookWinEvent(_winEventFocusHook);
        if (_winEventCreateHook != IntPtr.Zero) NativeMethods.UnhookWinEvent(_winEventCreateHook);
        if (_winEventDestroyHook != IntPtr.Zero) NativeMethods.UnhookWinEvent(_winEventDestroyHook);
        if (_winEventLocationHook != IntPtr.Zero) NativeMethods.UnhookWinEvent(_winEventLocationHook);
        if (_winEventAccessibilityHook != IntPtr.Zero) NativeMethods.UnhookWinEvent(_winEventAccessibilityHook);
        if (_winEventMenuHook != IntPtr.Zero) NativeMethods.UnhookWinEvent(_winEventMenuHook);
        if (_keyboardHook != IntPtr.Zero) NativeMethods.UnhookWindowsHookEx(_keyboardHook);
        if (_mouseHook != IntPtr.Zero) NativeMethods.UnhookWindowsHookEx(_mouseHook);
        _messageWindow?.Dispose();
        _messageWindow = null;
        _fileSystem?.Dispose();
        _browserStorage?.Dispose();
        _developerWorkflow?.Dispose();
        _mailCalendar?.Dispose();
    }

    private void OnWinEvent(IntPtr hook, uint eventType, IntPtr hwnd, int idObject, int idChild, uint eventThread, uint eventTime)
    {
        _ = Task.Run(async () =>
        {
            if (hwnd == IntPtr.Zero)
            {
                return;
            }
            if (eventType == NativeMethods.EventObjectDestroy)
            {
                await _sink.EmitAsync(WindowLifecycleCollector.CreateClosed(hwnd, idObject), CancellationToken.None);
                await EmitAllAsync(_browserForeground.ObserveWindowClosed(hwnd, idObject), CancellationToken.None);
                return;
            }

            var snapshot = WindowSnapshot.FromHandle(hwnd);
            if (snapshot is null)
            {
                return;
            }

            if (eventType == NativeMethods.EventSystemForeground)
            {
                await EmitForegroundContextAsync(snapshot, CancellationToken.None);
                await EmitAllAsync(_fileManagerActivity.ObserveForeground(snapshot), CancellationToken.None);
            }
            else if (eventType == NativeMethods.EventObjectCreate && snapshot.IsVisible)
            {
                await _sink.EmitAsync(WindowLifecycleCollector.Create("window_opened", snapshot), CancellationToken.None);
                await EmitAllAsync(_browserForeground.ObserveWindowOpened(snapshot), CancellationToken.None);
            }
            else if (eventType == NativeMethods.EventObjectLocationChange && _windowLifecycle.MarkGeometryChanged(snapshot))
            {
                await _sink.EmitAsync(WindowLifecycleCollector.Create("window_resized", snapshot), CancellationToken.None);
                await EmitAllAsync(_workspaceActivity.ObserveWindowGeometry(snapshot), CancellationToken.None);
            }
            else
            {
                await EmitAllAsync(_screenUiMetadata.ObserveWinEvent(eventType, snapshot, idObject, idChild), CancellationToken.None);
            }
        });
    }

    private IntPtr OnKeyboardEvent(int nCode, IntPtr wParam, IntPtr lParam)
    {
        if (nCode >= 0 && (wParam.ToInt64() == NativeMethods.WmKeyDown || wParam.ToInt64() == NativeMethods.WmSysKeyDown))
        {
            var data = Marshal.PtrToStructure<NativeMethods.KeyboardHookStruct>(lParam);
            foreach (var keyboardEvent in _inputDevice.ObserveKeyDown(data.VirtualKeyCode).Concat(_pasteboardWorkflow.ObserveKeyDown(data.VirtualKeyCode)).Concat(_fileManagerActivity.ObserveKeyDown(data.VirtualKeyCode)).Concat(_screenUiMetadata.ObserveKeyDown(data.VirtualKeyCode)).Concat(_systemSurfaces.ObserveKeyDown(data.VirtualKeyCode)))
            {
                _ = _sink.EmitAsync(keyboardEvent, CancellationToken.None);
            }
            foreach (var workspaceEvent in _workspaceActivity.ObserveKeyDown(data.VirtualKeyCode))
            {
                _ = _sink.EmitAsync(workspaceEvent, CancellationToken.None);
            }
            foreach (var communicationEvent in _communicationActivity.ObserveKeyDown(data.VirtualKeyCode))
            {
                _ = _sink.EmitAsync(communicationEvent, CancellationToken.None);
            }
            if (_developerWorkflow is not null)
            {
                foreach (var developerEvent in _developerWorkflow.ObserveKeyDown(data.VirtualKeyCode))
                {
                    _ = _sink.EmitAsync(developerEvent, CancellationToken.None);
                }
            }
            if (_mailCalendar is not null)
            {
                foreach (var mailCalendarEvent in _mailCalendar.ObserveKeyDown(data.VirtualKeyCode))
                {
                    _ = _sink.EmitAsync(mailCalendarEvent, CancellationToken.None);
                }
            }
            foreach (var browserEvent in _browserForeground.ObserveKeyDown(data.VirtualKeyCode))
            {
                _ = _sink.EmitAsync(browserEvent, CancellationToken.None);
            }
        }
        return NativeMethods.CallNextHookEx(_keyboardHook, nCode, wParam, lParam);
    }

    private IntPtr OnMouseEvent(int nCode, IntPtr wParam, IntPtr lParam)
    {
        if (nCode >= 0)
        {
            foreach (var mouseEvent in _inputDevice.ObserveMouse(wParam).Concat(_systemSurfaces.ObserveMouse(wParam)))
            {
                _ = _sink.EmitAsync(mouseEvent, CancellationToken.None);
            }
        }
        return NativeMethods.CallNextHookEx(_mouseHook, nCode, wParam, lParam);
    }

    private void OnSystemMessage(NativeMethods.Message message)
    {
        foreach (var systemSurfaceEvent in _systemSurfaces.ObserveMessage(message))
        {
            _ = _sink.EmitAsync(systemSurfaceEvent, CancellationToken.None);
        }
        foreach (var workspaceEvent in _workspaceActivity.ObserveMessage(message))
        {
            _ = _sink.EmitAsync(workspaceEvent, CancellationToken.None);
        }
    }
}
