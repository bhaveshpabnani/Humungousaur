import AppKit
import CoreGraphics
import Foundation

func visibleSystemSurfaceSnapshots() -> [[String: String]] {
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        return []
    }
    return windows.compactMap { window in
        guard let ownerPID = window[kCGWindowOwnerPID as String] as? pid_t,
              let app = NSRunningApplication(processIdentifier: ownerPID),
              let surface = systemSurface(for: app) else {
            return nil
        }
        let title = (window[kCGWindowName as String] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        var snapshot = appMetadata(app)
        snapshot["system_surface"] = surface
        snapshot["window_id"] = window[kCGWindowNumber as String].map { String(describing: $0) } ?? ""
        snapshot["window_title_present"] = title.isEmpty ? "false" : "true"
        snapshot["window_title_hash"] = title.isEmpty ? "" : sha256(title)
        snapshot["window_title_length_bucket"] = titleLengthBucket(title)
        if let bounds = window[kCGWindowBounds as String] as? [String: Any] {
            snapshot["window_bounds_bucket"] = boundsBucket(bounds)
        }
        return snapshot
    }
}

func systemSurface(for app: NSRunningApplication) -> String? {
    let bundle = (app.bundleIdentifier ?? "").lowercased()
    let name = safeAppName(app).lowercased()
    if bundle == "com.apple.dock" || name == "dock" {
        return "dock"
    }
    if bundle.contains("controlcenter") || name.contains("control center") {
        return "control_center"
    }
    if bundle.contains("systemuiserver") || name.contains("systemuiserver") {
        return "menu_bar"
    }
    if bundle.contains("notificationcenter") || name.contains("notification center") || name.contains("widgets") {
        return "notification_center"
    }
    return nil
}
