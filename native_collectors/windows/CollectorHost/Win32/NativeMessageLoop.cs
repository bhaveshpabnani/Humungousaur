namespace Humungousaur.Collectors.Windows.Win32;

internal static class NativeMessageLoop
{
    public static IDisposable CreateMessageWindow(Action<NativeMethods.Message> observer) => new NativeMessageWindow(observer);

    public static void Run(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            while (NativeMethods.PeekMessage(out var message, IntPtr.Zero, 0, 0, NativeMethods.PmRemove))
            {
                if (message.Msg == NativeMethods.WmQuit)
                {
                    return;
                }
                NativeMethods.TranslateMessage(ref message);
                NativeMethods.DispatchMessage(ref message);
            }
            Thread.Sleep(50);
        }
    }

    private sealed class NativeMessageWindow : IDisposable
    {
        private readonly string _className = $"HumungousaurCollectorHost_{Environment.ProcessId}_{Guid.NewGuid():N}";
        private readonly IntPtr _instance;
        private readonly NativeMethods.WindowProc _windowProc;
        private readonly Action<NativeMethods.Message> _observer;
        private readonly bool _sessionRegistered;
        private IntPtr _hwnd;

        public NativeMessageWindow(Action<NativeMethods.Message> observer)
        {
            _observer = observer;
            _instance = NativeMethods.GetModuleHandle(null);
            _windowProc = WindowProc;
            var windowClass = new NativeMethods.WindowClassEx
            {
                CbSize = (uint)System.Runtime.InteropServices.Marshal.SizeOf<NativeMethods.WindowClassEx>(),
                HInstance = _instance,
                LpfnWndProc = _windowProc,
                LpszClassName = _className,
            };
            if (NativeMethods.RegisterClassEx(ref windowClass) == 0)
            {
                return;
            }
            _hwnd = NativeMethods.CreateWindowEx(0, _className, "Humungousaur Collector Host", 0, 0, 0, 0, 0, IntPtr.Zero, IntPtr.Zero, _instance, IntPtr.Zero);
            if (_hwnd != IntPtr.Zero)
            {
                _sessionRegistered = NativeMethods.WTSRegisterSessionNotification(_hwnd, NativeMethods.NotifyForThisSession);
            }
        }

        public void Dispose()
        {
            if (_hwnd != IntPtr.Zero)
            {
                if (_sessionRegistered)
                {
                    NativeMethods.WTSUnRegisterSessionNotification(_hwnd);
                }
                NativeMethods.DestroyWindow(_hwnd);
                _hwnd = IntPtr.Zero;
            }
            NativeMethods.UnregisterClass(_className, _instance);
        }

        private IntPtr WindowProc(IntPtr hwnd, uint message, UIntPtr wParam, IntPtr lParam)
        {
            _observer(new NativeMethods.Message { Hwnd = hwnd, Msg = message, WParam = wParam, LParam = lParam });
            return NativeMethods.DefWindowProc(hwnd, message, wParam, lParam);
        }
    }
}
