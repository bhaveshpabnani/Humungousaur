# OS API References For Native Collectors

Use this as a starting index, then refresh with web search before implementing an OS-specific collector. Prefer official docs and man pages over blog posts or examples.

## macOS

- Apple Developer: NSWorkspace, app lifecycle, workspace, sleep/wake, and activation notifications.
  - https://developer.apple.com/documentation/AppKit/NSWorkspace
  - https://developer.apple.com/documentation/appkit/nsworkspace/didlaunchapplicationnotification
  - https://developer.apple.com/documentation/appkit/nsworkspace/didactivateapplicationnotification
  - https://developer.apple.com/documentation/appkit/nsworkspace/didterminateapplicationnotification
- Apple Developer: CoreGraphics window metadata.
  - https://developer.apple.com/documentation/coregraphics/cgwindowlistcopywindowinfo%28_%3A_%3A%29
  - https://developer.apple.com/documentation/coregraphics/cgpreflightscreencaptureaccess%28%29
- Apple Developer: AVFoundation/Core Audio references for media permission and
  audio-device metadata. Prefer permission/device state; do not capture raw
  audio unless a rich opt-in collector explicitly requires it.
  - https://developer.apple.com/documentation/avfoundation/requesting-authorization-to-capture-and-save-media
  - https://developer.apple.com/documentation/avfoundation/avcapturedevice/authorizationstatus%28for%3A%29
  - https://developer.apple.com/documentation/coreaudio
  - https://developer.apple.com/documentation/coreaudio/audioobjectgetpropertydata%28_%3A_%3A_%3A_%3A_%3A_%3A%29
- Apple Developer: User notifications, AVFoundation media permissions, Core
  Location authorization, and time-zone notifications for OS-system surfaces.
  - https://developer.apple.com/documentation/usernotifications/unusernotificationcenter
  - https://developer.apple.com/documentation/avfoundation/avcapturedevice/authorizationstatus%28for%3A%29
  - https://developer.apple.com/documentation/corelocation/clauthorizationstatus
  - https://developer.apple.com/documentation/foundation/nsnotification/name-swift.struct/nssystemtimezonedidchange
- Apple Developer: ProcessInfo and AppKit display/Space/mount notifications for
  resource, storage, peripheral, and focus-task context.
  - https://developer.apple.com/documentation/foundation/processinfo
  - https://developer.apple.com/documentation/foundation/processinfo/thermalstate-swift.enum
  - https://developer.apple.com/documentation/appkit/nsworkspace/didmountnotification
  - https://developer.apple.com/documentation/appkit/nsapplication/didchangescreenparametersnotification
  - https://developer.apple.com/documentation/appkit/nsworkspace/activespacedidchangenotification
- Apple/open-source CUPS documentation for print-system metadata.
  - https://www.cups.org/
- Apple Developer: Accessibility objects for focused controls and UI metadata.
  - https://developer.apple.com/documentation/applicationservices/axuielement
  - https://developer.apple.com/documentation/applicationservices/axuielement_h
  - https://developer.apple.com/documentation/applicationservices/carbon_accessibility/attributes
- Apple Developer: AppKit event monitors and status-bar surfaces for shortcut,
  context-menu, menu bar, and tray-style metadata.
  - https://developer.apple.com/documentation/appkit/nsevent
  - https://developer.apple.com/documentation/appkit/nsevent/addglobalmonitorforevents%28matching%3Ahandler%3A%29
  - https://developer.apple.com/documentation/appkit/nsstatusbar
- Apple Developer: Control Center and Notification Center/widget surfaces.
  - https://developer.apple.com/documentation/widgetkit/controlcenter
  - https://developer.apple.com/documentation/notificationcenter
- Apple Developer: Text Input Sources for keyboard layout and IME source changes.
  - https://developer.apple.com/documentation/appkit/nstextinputcontext
  - Local SDK headers: `Carbon.framework/.../HIToolbox.framework/.../TextInputSources.h`
- Apple Developer: pasteboard metadata. Use change counts and type categories; do not read values.
  - https://developer.apple.com/documentation/appkit/nspasteboard
- Apple Developer: File System Events for filesystem and file-manager metadata collectors.
  - https://developer.apple.com/documentation/coreservices/file_system_events
  - https://developer.apple.com/documentation/coreservices/1455361-fseventstreamcreate
- Apple Developer: FileManager search directories for Downloads and user-scoped filesystem locations.
  - https://developer.apple.com/documentation/foundation/filemanager
- Apple Developer: IOKit power and HID idle state.
  - https://developer.apple.com/documentation/iokit
  - https://developer.apple.com/library/archive/documentation/DeviceDrivers/Conceptual/USBBook/USBDeviceInterfaces/USBDevInterfaces.html

## Windows

- Microsoft Learn: WinEvents and `SetWinEventHook` for focus/window/accessibility events.
  - https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook
  - https://learn.microsoft.com/en-us/windows/win32/winauto/winevents-overview
  - https://learn.microsoft.com/en-us/windows/win32/winauto/event-constants
- Microsoft Learn: UI Automation for focused elements and metadata-only control observations.
  - https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32
  - https://learn.microsoft.com/en-us/windows/win32/api/_winauto/
- Microsoft Learn: WMI process lifecycle.
  - https://learn.microsoft.com/en-us/previous-versions/windows/desktop/krnlprov/win32-processstarttrace
  - https://learn.microsoft.com/en-us/previous-versions/windows/desktop/krnlprov/win32-processstoptrace
  - https://learn.microsoft.com/en-us/windows/win32/wmisdk/wmi-architecture
- Microsoft Learn: ETW, power, session, and device notifications when richer OS telemetry is required.
  - https://learn.microsoft.com/en-us/windows/win32/etw/event-tracing-portal
  - https://learn.microsoft.com/en-us/windows/win32/power/power-management-portal

## Linux

- Linux man pages: inotify for filesystem events.
  - https://man7.org/linux/man-pages/man7/inotify.7.html
- freedesktop: D-Bus specification and API design.
  - https://dbus.freedesktop.org/doc/dbus-specification.html
  - https://dbus.freedesktop.org/doc/dbus-api-design.html
- systemd/freedesktop: udev device events and permissions.
  - https://www.freedesktop.org/software/systemd/man/udev.html
- GNOME/freedesktop: AT-SPI accessibility stack for focused UI metadata.
  - https://www.freedesktop.org/wiki/Accessibility/AT-SPI2/
  - https://gnome.pages.gitlab.gnome.org/at-spi2-core/devel-docs/architecture.html
- Linux kernel/man pages: fanotify only for privileged opt-in access semantics.
  - https://man7.org/linux/man-pages/man7/fanotify.7.html

## Selection Checklist

- Does the API emit events rather than requiring high-frequency polling?
- Does it require accessibility, input monitoring, admin, full disk, or root capability?
- Can it provide privacy-safe metadata without raw content?
- Is the API stable and documented by the OS vendor or desktop project?
- Can helper health report degraded or permission-denied status when unavailable?
