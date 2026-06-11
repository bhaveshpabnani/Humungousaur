import AppKit
import CoreGraphics
import Foundation

func safeAppName(_ app: NSRunningApplication) -> String {
    let name = app.localizedName?.trimmingCharacters(in: .whitespacesAndNewlines)
    return name?.isEmpty == false ? name! : "unknown app"
}

func appMetadata(_ app: NSRunningApplication) -> [String: String] {
    [
        "app_name": safeAppName(app),
        "bundle_id": app.bundleIdentifier ?? "",
        "process_identifier": String(app.processIdentifier),
        "activation_policy": String(app.activationPolicy.rawValue),
    ]
}

func frontmostWindowSnapshot(for app: NSRunningApplication) -> [String: String] {
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        return ["window_visible": "false"]
    }
    for window in windows {
        let ownerPID = window[kCGWindowOwnerPID as String] as? pid_t
        let layer = window[kCGWindowLayer as String] as? Int
        guard ownerPID == app.processIdentifier, layer == 0 else {
            continue
        }
        let windowID = window[kCGWindowNumber as String].map { String(describing: $0) } ?? ""
        let title = (window[kCGWindowName as String] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        var snapshot = [
            "window_visible": "true",
            "window_id": windowID,
            "window_title_present": title.isEmpty ? "false" : "true",
            "window_title_hash": title.isEmpty ? "" : sha256(title),
            "window_title_length_bucket": titleLengthBucket(title),
        ]
        if let bounds = window[kCGWindowBounds as String] as? [String: Any] {
            snapshot["window_bounds_bucket"] = boundsBucket(bounds)
        }
        return snapshot
    }
    return ["window_visible": "false"]
}
