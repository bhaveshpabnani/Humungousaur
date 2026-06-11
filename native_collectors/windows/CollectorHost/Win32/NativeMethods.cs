using System.Runtime.InteropServices;
using System.Text;

namespace Humungousaur.Collectors.Windows.Win32;

internal static class NativeMethods
{
    public const uint EventSystemForeground = 0x0003;
    public const uint EventObjectCreate = 0x8000;
    public const uint EventObjectDestroy = 0x8001;
    public const uint EventObjectFocus = 0x8005;
    public const uint EventObjectSelection = 0x8006;
    public const uint EventObjectSelectionAdd = 0x8007;
    public const uint EventObjectSelectionRemove = 0x8008;
    public const uint EventObjectSelectionWithin = 0x8009;
    public const uint EventObjectLocationChange = 0x800B;
    public const uint EventObjectValueChange = 0x800E;
    public const uint EventObjectInvoked = 0x8013;
    public const uint EventSystemMenuStart = 0x0004;
    public const uint EventSystemMenuEnd = 0x0005;
    public const uint EventSystemMenuPopupStart = 0x0006;
    public const uint EventSystemMenuPopupEnd = 0x0007;
    public const uint WineventOutOfContext = 0;
    public const uint WineventSkipOwnProcess = 0x0002;
    public const int WhKeyboardLl = 13;
    public const int WhMouseLl = 14;
    public const int WmKeyDown = 0x0100;
    public const int WmSysKeyDown = 0x0104;
    public const int WmQuit = 0x0012;
    public const int WmSettingChange = 0x001A;
    public const int WmDisplayChange = 0x007E;
    public const int WmPowerBroadcast = 0x0218;
    public const int WmLButtonDown = 0x0201;
    public const int WmLButtonDblClk = 0x0203;
    public const int WmRButtonDown = 0x0204;
    public const int WmMouseWheel = 0x020A;
    public const int WmDeviceChange = 0x0219;
    public const int WmWtsSessionChange = 0x02B1;
    public const int MonitorDefaultToNearest = 0x00000002;
    public const int SmXVirtualScreen = 76;
    public const int SmYVirtualScreen = 77;
    public const int SmCxVirtualScreen = 78;
    public const int SmCyVirtualScreen = 79;
    public const int SmCMonitors = 80;
    public const int PbtApmSuspend = 0x0004;
    public const int PbtApmPowerStatusChange = 0x000A;
    public const int PbtApmResumeAutomatic = 0x0012;
    public const int DbtDeviceArrival = 0x8000;
    public const int DbtDeviceRemoveComplete = 0x8004;
    public const int DbtDevnodesChanged = 0x0007;
    public const int WtsSessionLock = 0x7;
    public const int WtsSessionUnlock = 0x8;
    public const int NotifyForThisSession = 0;
    public const int VkTab = 0x09;
    public const int VkEnter = 0x0D;
    public const int VkShift = 0x10;
    public const int VkControl = 0x11;
    public const int VkMenu = 0x12;
    public const int VkCapital = 0x14;
    public const int VkLeft = 0x25;
    public const int VkUp = 0x26;
    public const int VkRight = 0x27;
    public const int VkDown = 0x28;
    public const int VkD0 = 0x30;
    public const int VkA = 0x41;
    public const int VkB = 0x42;
    public const int VkC = 0x43;
    public const int VkD = 0x44;
    public const int VkE = 0x45;
    public const int VkF = 0x46;
    public const int VkG = 0x47;
    public const int VkH = 0x48;
    public const int VkK = 0x4B;
    public const int VkL = 0x4C;
    public const int VkM = 0x4D;
    public const int VkN = 0x4E;
    public const int VkO = 0x4F;
    public const int VkQ = 0x51;
    public const int VkR = 0x52;
    public const int VkS = 0x53;
    public const int VkT = 0x54;
    public const int VkU = 0x55;
    public const int VkV = 0x56;
    public const int VkY = 0x59;
    public const int VkF5 = 0x74;
    public const int VkF9 = 0x78;
    public const int VkDelete = 0x2E;
    public const int VkLwin = 0x5B;
    public const int VkRwin = 0x5C;
    public const int VkVolumeMute = 0xAD;
    public const int VkVolumeDown = 0xAE;
    public const int VkVolumeUp = 0xAF;
    public const int VkMediaNextTrack = 0xB0;
    public const int VkMediaPreviousTrack = 0xB1;
    public const int VkMediaStop = 0xB2;
    public const int VkMediaPlayPause = 0xB3;
    public const int VkOemPlus = 0xBB;
    public const int VkOemMinus = 0xBD;
    public const int VkOem2 = 0xBF;
    public const int VkOem3 = 0xC0;
    public const int GwlStyle = -16;
    public const int EsMultiline = 0x0004;
    public const int EsPassword = 0x0020;
    public const uint PmRemove = 0x0001;

    public delegate void WinEventDelegate(IntPtr hWinEventHook, uint eventType, IntPtr hwnd, int idObject, int idChild, uint dwEventThread, uint dwmsEventTime);
    public delegate IntPtr LowLevelKeyboardProc(int nCode, IntPtr wParam, IntPtr lParam);
    public delegate IntPtr LowLevelMouseProc(int nCode, IntPtr wParam, IntPtr lParam);
    public delegate IntPtr WindowProc(IntPtr hwnd, uint message, UIntPtr wParam, IntPtr lParam);
    public delegate bool MonitorEnumProc(IntPtr monitor, IntPtr hdc, ref Rect rect, IntPtr data);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct WindowClassEx
    {
        public uint CbSize;
        public uint Style;
        public WindowProc LpfnWndProc;
        public int CbClsExtra;
        public int CbWndExtra;
        public IntPtr HInstance;
        public IntPtr HIcon;
        public IntPtr HCursor;
        public IntPtr HbrBackground;
        public string? LpszMenuName;
        public string LpszClassName;
        public IntPtr HIconSm;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KeyboardHookStruct
    {
        public uint VirtualKeyCode;
        public uint ScanCode;
        public uint Flags;
        public uint Time;
        public IntPtr ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct MonitorInfoEx
    {
        public uint CbSize;
        public Rect RcMonitor;
        public Rect RcWork;
        public uint DwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string SzDevice;

        public static MonitorInfoEx Create() => new() { CbSize = (uint)Marshal.SizeOf<MonitorInfoEx>(), SzDevice = "" };
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct Point
    {
        public int X;
        public int Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct Message
    {
        public IntPtr Hwnd;
        public uint Msg;
        public UIntPtr WParam;
        public IntPtr LParam;
        public uint Time;
        public Point Point;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct LastInputInfo
    {
        public uint CbSize;
        public uint DwTime;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct SystemPowerStatus
    {
        public byte AcLineStatus;
        public byte BatteryFlag;
        public byte BatteryLifePercent;
        public byte SystemStatusFlag;
        public uint BatteryLifeTime;
        public uint BatteryFullLifeTime;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    public struct MemoryStatusEx
    {
        public uint DwLength;
        public uint DwMemoryLoad;
        public ulong UllTotalPhys;
        public ulong UllAvailPhys;
        public ulong UllTotalPageFile;
        public ulong UllAvailPageFile;
        public ulong UllTotalVirtual;
        public ulong UllAvailVirtual;
        public ulong UllAvailExtendedVirtual;

        public static MemoryStatusEx Create() => new() { DwLength = (uint)Marshal.SizeOf<MemoryStatusEx>() };
    }

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(IntPtr hWnd, StringBuilder className, int maxCount);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out Rect rect);

    [DllImport("user32.dll")]
    public static extern int GetWindowLong(IntPtr hWnd, int index);

    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int index);

    [DllImport("user32.dll")]
    public static extern IntPtr MonitorFromWindow(IntPtr hwnd, int flags);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern bool GetMonitorInfo(IntPtr hMonitor, ref MonitorInfoEx monitorInfo);

    [DllImport("user32.dll")]
    public static extern bool EnumDisplayMonitors(IntPtr hdc, IntPtr clip, MonitorEnumProc callback, IntPtr data);

    [DllImport("user32.dll")]
    public static extern IntPtr SetWinEventHook(uint eventMin, uint eventMax, IntPtr hmodWinEventProc, WinEventDelegate lpfnWinEventProc, uint idProcess, uint idThread, uint dwFlags);

    [DllImport("user32.dll")]
    public static extern bool UnhookWinEvent(IntPtr hWinEventHook);

    [DllImport("user32.dll")]
    public static extern IntPtr SetWindowsHookEx(int idHook, LowLevelKeyboardProc lpfn, IntPtr hMod, uint dwThreadId);

    [DllImport("user32.dll")]
    public static extern IntPtr SetWindowsHookEx(int idHook, LowLevelMouseProc lpfn, IntPtr hMod, uint dwThreadId);

    [DllImport("user32.dll")]
    public static extern bool UnhookWindowsHookEx(IntPtr hhk);

    [DllImport("user32.dll")]
    public static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern short GetKeyState(int virtualKey);

    [DllImport("user32.dll")]
    private static extern bool GetKeyboardLayoutName(StringBuilder name);

    [DllImport("user32.dll")]
    private static extern IntPtr GetKeyboardLayout(uint threadId);

    [DllImport("imm32.dll")]
    private static extern IntPtr ImmGetContext(IntPtr hWnd);

    [DllImport("imm32.dll")]
    private static extern bool ImmReleaseContext(IntPtr hWnd, IntPtr hImc);

    [DllImport("imm32.dll")]
    private static extern bool ImmGetOpenStatus(IntPtr hImc);

    [DllImport("kernel32.dll")]
    public static extern IntPtr GetModuleHandle(string? lpModuleName);

    [DllImport("kernel32.dll")]
    private static extern uint GetTickCount();

    [DllImport("user32.dll")]
    private static extern bool GetLastInputInfo(ref LastInputInfo info);

    [DllImport("kernel32.dll")]
    public static extern bool GetSystemPowerStatus(out SystemPowerStatus status);

    [DllImport("user32.dll")]
    public static extern bool PeekMessage(out Message lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax, uint wRemoveMsg);

    [DllImport("user32.dll")]
    public static extern bool TranslateMessage(ref Message lpMsg);

    [DllImport("user32.dll")]
    public static extern IntPtr DispatchMessage(ref Message lpMsg);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern ushort RegisterClassEx(ref WindowClassEx windowClass);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool UnregisterClass(string className, IntPtr instance);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr CreateWindowEx(
        int exStyle,
        string className,
        string windowName,
        uint style,
        int x,
        int y,
        int width,
        int height,
        IntPtr parent,
        IntPtr menu,
        IntPtr instance,
        IntPtr param
    );

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool DestroyWindow(IntPtr hwnd);

    [DllImport("user32.dll")]
    public static extern IntPtr DefWindowProc(IntPtr hwnd, uint message, UIntPtr wParam, IntPtr lParam);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    public static extern bool WTSRegisterSessionNotification(IntPtr hwnd, int flags);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    public static extern bool WTSUnRegisterSessionNotification(IntPtr hwnd);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GlobalMemoryStatusEx(ref MemoryStatusEx status);

    public static string WindowTitle(IntPtr handle)
    {
        var length = GetWindowTextLength(handle);
        if (length <= 0)
        {
            return "";
        }
        var builder = new StringBuilder(length + 1);
        return GetWindowText(handle, builder, builder.Capacity) > 0 ? builder.ToString() : "";
    }

    public static string ClassName(IntPtr handle)
    {
        var builder = new StringBuilder(256);
        return GetClassName(handle, builder, builder.Capacity) > 0 ? builder.ToString() : "";
    }

    public static bool IsKeyDown(int virtualKey) => (GetKeyState(virtualKey) & 0x8000) != 0;

    public static bool IsKeyToggled(int virtualKey) => (GetKeyState(virtualKey) & 0x0001) != 0;

    public static string KeyboardLayoutName()
    {
        var builder = new StringBuilder(16);
        return GetKeyboardLayoutName(builder) ? builder.ToString() : "";
    }

    public static string KeyboardLayoutNameForWindow(IntPtr hwnd)
    {
        var threadId = GetWindowThreadProcessId(hwnd, out _);
        var layout = GetKeyboardLayout(threadId).ToInt64();
        return layout == 0 ? "" : $"0x{layout:x}";
    }

    public static bool? ImeOpen(IntPtr hwnd)
    {
        var context = ImmGetContext(hwnd);
        if (context == IntPtr.Zero)
        {
            return null;
        }
        try
        {
            return ImmGetOpenStatus(context);
        }
        finally
        {
            ImmReleaseContext(hwnd, context);
        }
    }

    public static uint IdleSeconds()
    {
        var info = new LastInputInfo { CbSize = (uint)Marshal.SizeOf<LastInputInfo>() };
        if (!GetLastInputInfo(ref info))
        {
            return 0;
        }
        var elapsedMs = GetTickCount() - info.DwTime;
        return elapsedMs / 1000;
    }

    public static MemoryStatusEx? MemoryStatus()
    {
        var status = MemoryStatusEx.Create();
        return GlobalMemoryStatusEx(ref status) ? status : null;
    }
}
