import AppKit
import CoreGraphics
import Foundation

private let windowWorkspaceKey = "kCGWindowWorkspace"

func displayLayoutSnapshot() -> [String: String] {
    let screens = NSScreen.screens
    guard !screens.isEmpty else {
        return [:]
    }
    let parts = screens.compactMap(displayPart).sorted()
    let resolutionParts = screens.compactMap { screen -> String? in
        guard let id = displayID(screen) else {
            return nil
        }
        return "\(id):\(Int(screen.frame.width))x\(Int(screen.frame.height))"
    }.sorted()
    let scalingParts = screens.compactMap { screen -> String? in
        guard let id = displayID(screen) else {
            return nil
        }
        return "\(id):\(screen.backingScaleFactor)"
    }.sorted()
    let rotationParts = screens.compactMap { screen -> String? in
        guard let id = displayID(screen) else {
            return nil
        }
        return "\(id):\(Int(CGDisplayRotation(id)))"
    }.sorted()
    let primaryID = NSScreen.main.flatMap(displayID)
    return [
        "display_count": String(screens.count),
        "display_count_bucket": countBucket(screens.count),
        "display_arrangement_signature": shortDigest(parts.joined(separator: "|")),
        "display_resolution_signature": shortDigest(resolutionParts.joined(separator: "|")),
        "display_scaling_signature": shortDigest(scalingParts.joined(separator: "|")),
        "display_rotation_signature": shortDigest(rotationParts.joined(separator: "|")),
        "primary_display_id_hash": primaryID.map { shortDigest(String($0)) } ?? "",
        "mirroring_state": mirroringState(screens),
    ]
}

func workspaceLayoutSnapshot() -> [String: String] {
    var snapshot = [
        "native_source": "macos_workspace_layout_metadata",
        "source_api": "CGWindowList+UserDefaults",
        "privacy_level": "redacted",
        "workspace_names_omitted": "true",
        "visible_contents_omitted": "true",
        "desktop_space_id_hash": activeDesktopSpaceHash() ?? "",
        "stage_manager_enabled": stageManagerEnabled().map { $0 ? "true" : "false" } ?? "",
    ]
    if let app = NSWorkspace.shared.frontmostApplication {
        snapshot.merge(appMetadata(app), uniquingKeysWith: { current, _ in current })
    }
    return snapshot
}

func frontmostWindowLayoutSnapshot() -> [String: String]? {
    guard let app = NSWorkspace.shared.frontmostApplication,
          let window = frontmostWindowInfo(for: app) else {
        return nil
    }
    let windowID = window[kCGWindowNumber as String].map { String(describing: $0) } ?? ""
    let title = (window[kCGWindowName as String] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    let bounds = window[kCGWindowBounds as String] as? [String: Any] ?? [:]
    let display = displayForBounds(bounds)
    let workspaceID = window[windowWorkspaceKey].map { String(describing: $0) } ?? ""
    var snapshot = appMetadata(app)
    snapshot.merge([
        "native_source": "macos_window_arrangement_metadata",
        "source_api": "CGWindowList",
        "privacy_level": "redacted",
        "window_id": windowID,
        "window_title_present": title.isEmpty ? "false" : "true",
        "window_title_hash": title.isEmpty ? "" : sha256(title),
        "window_title_length_bucket": titleLengthBucket(title),
        "window_bounds_bucket": boundsBucket(bounds),
        "display_id_hash": display.map { shortDigest(String($0)) } ?? "",
        "desktop_space_id_hash": workspaceID.isEmpty ? "" : shortDigest(workspaceID),
        "fullscreen_bucket": fullscreenBucket(bounds: bounds, display: display),
        "window_signature_hash": shortDigest("\(app.bundleIdentifier ?? "")|\(windowID)|\(boundsBucket(bounds))|\(workspaceID)"),
        "visible_contents_omitted": "true",
    ], uniquingKeysWith: { current, _ in current })
    return snapshot
}

func appWorkspaceSnapshot() -> [String: String]? {
    guard let app = NSWorkspace.shared.frontmostApplication else {
        return nil
    }
    let window = frontmostWindowInfo(for: app)
    let workspaceID = window?[windowWorkspaceKey].map { String(describing: $0) } ?? ""
    let bounds = (window?[kCGWindowBounds as String] as? [String: Any]) ?? [:]
    let display = displayForBounds(bounds)
    let signature = [
        app.bundleIdentifier ?? "",
        workspaceID,
        display.map { String($0) } ?? "",
        boundsBucket(bounds),
    ].joined(separator: "|")
    var snapshot = appMetadata(app)
    snapshot.merge([
        "native_source": "macos_app_workspace_metadata",
        "source_api": "NSWorkspace+CGWindowList",
        "privacy_level": "redacted",
        "workspace_names_omitted": "true",
        "project_names_omitted": "true",
        "restored_contents_omitted": "true",
        "desktop_space_id_hash": workspaceID.isEmpty ? "" : shortDigest(workspaceID),
        "display_id_hash": display.map { shortDigest(String($0)) } ?? "",
        "layout_bounds_bucket": boundsBucket(bounds),
        "app_workspace_signature": shortDigest(signature),
    ], uniquingKeysWith: { current, _ in current })
    return snapshot
}

private func frontmostWindowInfo(for app: NSRunningApplication) -> [String: Any]? {
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        return nil
    }
    return windows.first { window in
        let ownerPID = window[kCGWindowOwnerPID as String] as? pid_t
        let layer = window[kCGWindowLayer as String] as? Int
        return ownerPID == app.processIdentifier && layer == 0
    }
}

private func displayPart(_ screen: NSScreen) -> String? {
    guard let id = displayID(screen) else {
        return nil
    }
    let frame = screen.frame
    let visible = screen.visibleFrame
    return [
        String(id),
        "\(Int(frame.origin.x)),\(Int(frame.origin.y)),\(Int(frame.width)),\(Int(frame.height))",
        "\(Int(visible.origin.x)),\(Int(visible.origin.y)),\(Int(visible.width)),\(Int(visible.height))",
        "\(screen.backingScaleFactor)",
        "\(Int(CGDisplayRotation(id)))",
    ].joined(separator: ":")
}

private func displayID(_ screen: NSScreen) -> CGDirectDisplayID? {
    screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? CGDirectDisplayID
}

private func displayForBounds(_ bounds: [String: Any]) -> CGDirectDisplayID? {
    let center = CGPoint(x: CGFloat(intValue(bounds["X"])) + CGFloat(intValue(bounds["Width"])) / 2, y: CGFloat(intValue(bounds["Y"])) + CGFloat(intValue(bounds["Height"])) / 2)
    return NSScreen.screens.first { screen in
        screen.frame.contains(center)
    }.flatMap(displayID)
}

private func fullscreenBucket(bounds: [String: Any], display: CGDirectDisplayID?) -> String {
    guard let display,
          let screen = NSScreen.screens.first(where: { displayID($0) == display }) else {
        return "unknown"
    }
    let width = CGFloat(intValue(bounds["Width"]))
    let height = CGFloat(intValue(bounds["Height"]))
    let frame = screen.frame
    if abs(width - frame.width) <= 12 && abs(height - frame.height) <= 12 {
        return "fullscreen_like"
    }
    return "windowed"
}

private func activeDesktopSpaceHash() -> String? {
    guard let app = NSWorkspace.shared.frontmostApplication,
          let window = frontmostWindowInfo(for: app),
          let workspace = window[windowWorkspaceKey] else {
        return nil
    }
    return shortDigest(String(describing: workspace))
}

private func stageManagerEnabled() -> Bool? {
    let defaults = UserDefaults(suiteName: "com.apple.WindowManager")
    if let value = defaults?.object(forKey: "GloballyEnabled") as? Bool {
        return value
    }
    if let value = defaults?.object(forKey: "StageManagerGloballyEnabled") as? Bool {
        return value
    }
    return nil
}

private func mirroringState(_ screens: [NSScreen]) -> String {
    let frameSet = Set(screens.map { "\(Int($0.frame.origin.x)),\(Int($0.frame.origin.y)),\(Int($0.frame.width)),\(Int($0.frame.height))" })
    return screens.count > 1 && frameSet.count == 1 ? "mirrored_possible" : "extended_or_single"
}
