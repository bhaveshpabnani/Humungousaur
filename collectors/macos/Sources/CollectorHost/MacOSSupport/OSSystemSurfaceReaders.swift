import AppKit
import AVFoundation
import CoreGraphics
import CoreLocation
import Foundation
import IOKit

func permissionSnapshots() -> [[String: String]] {
    [
        permissionSnapshot(service: "accessibility", status: accessibilityPermissionState() == "accessibility_granted" ? "granted" : "denied", sourceAPI: "AXIsProcessTrusted"),
        permissionSnapshot(service: "screen_recording", status: CGPreflightScreenCaptureAccess() ? "granted" : "denied", sourceAPI: "CGPreflightScreenCaptureAccess"),
        permissionSnapshot(service: "camera", status: avAuthorizationStatus(AVCaptureDevice.authorizationStatus(for: .video)), sourceAPI: "AVCaptureDevice.authorizationStatus"),
        permissionSnapshot(service: "microphone", status: avAuthorizationStatus(AVCaptureDevice.authorizationStatus(for: .audio)), sourceAPI: "AVCaptureDevice.authorizationStatus"),
        permissionSnapshot(service: "location", status: locationAuthorizationBucket(CLLocationManager().authorizationStatus), sourceAPI: "CLLocationManager.authorizationStatus"),
    ]
}

func permissionSnapshot(service: String, status: String, sourceAPI: String) -> [String: String] {
    [
        "permission_service": service,
        "permission_status": status,
        "permission_signature_hash": shortDigest("\(service):\(status)"),
        "source_api": sourceAPI,
    ]
}

func avAuthorizationStatus(_ status: AVAuthorizationStatus) -> String {
    switch status {
    case .authorized: return "granted"
    case .denied, .restricted: return "denied"
    case .notDetermined: return "not_determined"
    @unknown default: return "unknown"
    }
}

func locationAuthorizationBucket(_ status: CLAuthorizationStatus) -> String {
    switch status {
    case .authorizedAlways, .authorizedWhenInUse, .authorized: return "authorized"
    case .denied, .restricted: return "denied"
    case .notDetermined: return "not_determined"
    @unknown default: return "unknown"
    }
}

func locationContextSnapshot() -> [String: String] {
    let timezone = TimeZone.current.identifier
    let region = Locale.current.region?.identifier ?? ""
    return [
        "native_source": "macos_location_region_metadata",
        "source_api": "CoreLocation+FoundationLocale+TimeZone",
        "privacy_level": "redacted",
        "precise_coordinates_omitted": "true",
        "location_authorization_status": locationAuthorizationBucket(CLLocationManager().authorizationStatus),
        "timezone_identifier_hash": shortDigest(timezone),
        "timezone_seconds_from_gmt_bucket": secondsBucket(TimeZone.current.secondsFromGMT()),
        "region_identifier_hash": region.isEmpty ? "" : shortDigest(region),
    ]
}

func resourcePressureSnapshot() -> [String: String] {
    [
        "native_source": "macos_resource_pressure_metadata",
        "source_api": "ProcessInfo",
        "privacy_level": "redacted",
        "thermal_state": thermalStateBucket(ProcessInfo.processInfo.thermalState),
        "processor_count_bucket": countBucket(ProcessInfo.processInfo.processorCount),
        "physical_memory_bucket": byteBucket(Int64(ProcessInfo.processInfo.physicalMemory)),
    ]
}

func thermalStateBucket(_ state: ProcessInfo.ThermalState) -> String {
    switch state {
    case .nominal: return "nominal"
    case .fair: return "fair"
    case .serious: return "serious"
    case .critical: return "critical"
    @unknown default: return "unknown"
    }
}

func rootStorageSnapshot() -> [String: String]? {
    storageSnapshot(for: URL(fileURLWithPath: "/"), role: "root_disk")
}

func mountedVolumeStorageSnapshots() -> [[String: String]] {
    let keys: [URLResourceKey] = [.volumeIdentifierKey, .volumeTotalCapacityKey, .volumeAvailableCapacityForImportantUsageKey, .volumeIsInternalKey, .volumeIsRemovableKey]
    let urls = FileManager.default.mountedVolumeURLs(includingResourceValuesForKeys: keys, options: [.skipHiddenVolumes]) ?? []
    return urls.compactMap { storageSnapshot(for: $0, role: "mounted_volume") }
}

func storageSnapshot(for url: URL, role: String) -> [String: String]? {
    let keys: Set<URLResourceKey> = [.volumeIdentifierKey, .volumeTotalCapacityKey, .volumeAvailableCapacityForImportantUsageKey, .volumeIsInternalKey, .volumeIsRemovableKey]
    guard let values = try? url.resourceValues(forKeys: keys),
          let total = values.volumeTotalCapacity,
          let available = values.volumeAvailableCapacityForImportantUsage else {
        return nil
    }
    let percent = max(0, min(100, Int((Double(available) / Double(max(total, 1))) * 100)))
    let identifier = values.volumeIdentifier.map { String(describing: $0) } ?? url.path
    return [
        "native_source": "macos_storage_metadata",
        "source_api": "FileManager.URLResourceValues",
        "privacy_level": "redacted",
        "path_omitted": "true",
        "storage_role": role,
        "storage_signature_hash": shortDigest("\(role):\(identifier):\(total)"),
        "available_percent_bucket": percentBucket(percent),
        "available_capacity_bucket": byteBucket(Int64(available)),
        "total_capacity_bucket": byteBucket(Int64(total)),
        "storage_low": String(percent <= 10),
        "volume_is_internal": values.volumeIsInternal.map(String.init) ?? "",
        "volume_is_removable": values.volumeIsRemovable.map(String.init) ?? "",
    ]
}

func applicationBundleSignatures() -> [String: String] {
    let roots = [
        URL(fileURLWithPath: "/Applications", isDirectory: true),
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Applications", isDirectory: true),
    ]
    var signatures: [String: String] = [:]
    for root in roots {
        guard let urls = try? FileManager.default.contentsOfDirectory(
            at: root,
            includingPropertiesForKeys: [.contentModificationDateKey, .isDirectoryKey],
            options: [.skipsHiddenFiles]
        ) else {
            continue
        }
        for url in urls where url.pathExtension == "app" {
            let key = Bundle(url: url)?.bundleIdentifier ?? shortDigest(url.path)
            let modified = ((try? url.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate?.timeIntervalSince1970).map { String(Int($0)) } ?? ""
            signatures[key] = shortDigest("\(key):\(modified)")
        }
    }
    return signatures
}

func defaultPrinterSignature() -> String? {
    guard let output = processOutput(executable: "/usr/bin/lpstat", arguments: ["-d"]) else {
        return nil
    }
    let cleaned = output.trimmingCharacters(in: .whitespacesAndNewlines)
    guard cleaned.localizedCaseInsensitiveContains("system default destination") else {
        return nil
    }
    return shortDigest(cleaned)
}

func activePrintJobSignatures() -> Set<String> {
    guard let output = processOutput(executable: "/usr/bin/lpstat", arguments: ["-W", "not-completed", "-o"]) else {
        return []
    }
    return Set(output.split(separator: "\n").map { line in
        let normalized = line.split(separator: " ").prefix(4).joined(separator: " ")
        return shortDigest(String(normalized))
    })
}

func displayPeripheralSnapshot() -> [String: String] {
    let screens = NSScreen.screens
    let parts = screens.compactMap { screen -> String? in
        guard let id = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? CGDirectDisplayID else {
            return nil
        }
        return "\(id):\(Int(screen.frame.width))x\(Int(screen.frame.height)):\(screen.backingScaleFactor)"
    }.sorted()
    return [
        "native_source": "macos_display_peripheral_metadata",
        "source_api": "NSScreen",
        "privacy_level": "redacted",
        "display_names_omitted": "true",
        "display_count": String(screens.count),
        "display_count_bucket": countBucket(screens.count),
        "display_signature_hash": shortDigest(parts.joined(separator: "|")),
    ]
}

func usbDeviceSignatureSet() -> Set<String> {
    var iterator: io_iterator_t = 0
    guard IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching("IOUSBHostDevice"), &iterator) == KERN_SUCCESS else {
        return []
    }
    defer { IOObjectRelease(iterator) }
    var signatures: Set<String> = []
    while true {
        let service = IOIteratorNext(iterator)
        if service == 0 {
            break
        }
        defer { IOObjectRelease(service) }
        var properties: Unmanaged<CFMutableDictionary>?
        guard IORegistryEntryCreateCFProperties(service, &properties, kCFAllocatorDefault, 0) == KERN_SUCCESS,
              let dictionary = properties?.takeRetainedValue() as? [String: Any] else {
            continue
        }
        let vendor = dictionary["idVendor"].map { String(describing: $0) } ?? ""
        let product = dictionary["idProduct"].map { String(describing: $0) } ?? ""
        let deviceClass = dictionary["bDeviceClass"].map { String(describing: $0) } ?? ""
        signatures.insert(shortDigest("\(vendor):\(product):\(deviceClass)"))
    }
    return signatures
}

func mountedVolumeSignatureSet() -> Set<String> {
    Set(mountedVolumeStorageSnapshots().compactMap { $0["storage_signature_hash"] })
}

func peripheralMetadata(kind: String, signature: String) -> [String: String] {
    [
        "native_source": "macos_peripheral_metadata",
        "source_api": kind == "usb" ? "IOKit" : "FileManager.URLResourceValues",
        "privacy_level": "redacted",
        "device_name_omitted": "true",
        "peripheral_kind": kind,
        "device_signature_hash": signature,
    ]
}

func osSystemSurfaceSnapshots() -> [[String: String]] {
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        return []
    }
    return windows.compactMap { window in
        guard let ownerPID = window[kCGWindowOwnerPID as String] as? pid_t,
              let app = NSRunningApplication(processIdentifier: ownerPID),
              let surface = osSurface(for: app, window: window) else {
            return nil
        }
        let title = (window[kCGWindowName as String] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let windowID = window[kCGWindowNumber as String].map { String(describing: $0) } ?? ""
        var snapshot = appMetadata(app)
        snapshot.merge([
            "native_source": "macos_visible_system_surface_metadata",
            "source_api": "CGWindowListCopyWindowInfo",
            "privacy_level": "redacted",
            "screen_pixels_captured": "false",
            "window_title_present": title.isEmpty ? "false" : "true",
            "window_title_hash": title.isEmpty ? "" : sha256(title),
            "window_title_length_bucket": titleLengthBucket(title),
            "window_id": windowID,
            "os_surface": surface,
            "surface_signature_hash": shortDigest("\(surface):\(app.bundleIdentifier ?? ""):\(windowID):\(title)"),
        ], uniquingKeysWith: { current, _ in current })
        if let bounds = window[kCGWindowBounds as String] as? [String: Any] {
            snapshot["window_bounds_bucket"] = boundsBucket(bounds)
        }
        return snapshot
    }
}

func osSurface(for app: NSRunningApplication, window: [String: Any]) -> String? {
    let bundle = (app.bundleIdentifier ?? "").lowercased()
    let name = safeAppName(app).lowercased()
    let title = ((window[kCGWindowName as String] as? String) ?? "").lowercased()
    let joined = [bundle, name, title].joined(separator: " ")
    if joined.contains("notificationcenter") || joined.contains("usernotification") || title.contains("notification") {
        return "notification"
    }
    if joined.contains("spotlight") || title.contains("search") {
        return "spotlight"
    }
    if joined.contains("screen time") || joined.contains("screentime") || joined.contains("familycontrols") {
        return "screen_time"
    }
    if joined.contains("profiles") || joined.contains("managedclient") || joined.contains("device management") {
        return "policy"
    }
    return nil
}

func screenRecordingSurfaceSignature() -> String {
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        return ""
    }
    let matches = windows.compactMap { window -> String? in
        guard let ownerPID = window[kCGWindowOwnerPID as String] as? pid_t,
              let app = NSRunningApplication(processIdentifier: ownerPID) else {
            return nil
        }
        let bundle = (app.bundleIdentifier ?? "").lowercased()
        let appName = safeAppName(app).lowercased()
        let title = ((window[kCGWindowName as String] as? String) ?? "").lowercased()
        let joined = [bundle, appName, title].joined(separator: " ")
        guard joined.contains("screencapture") || joined.contains("screen recording") || joined.contains("screenshot") else {
            return nil
        }
        let windowID = window[kCGWindowNumber as String].map { String(describing: $0) } ?? ""
        return shortDigest("screen_recording:\(bundle):\(windowID):\(title)")
    }
    return matches.isEmpty ? "" : shortDigest(matches.sorted().joined(separator: "|"))
}

func managedProfileSnapshot() -> [String: String]? {
    let output = processOutput(executable: "/usr/bin/profiles", arguments: ["status", "-type", "enrollment"]) ?? ""
    let cleaned = output.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !cleaned.isEmpty else {
        return nil
    }
    return [
        "native_source": "macos_managed_profile_metadata",
        "source_api": "profiles status -type enrollment",
        "privacy_level": "redacted",
        "profile_payloads_omitted": "true",
        "managed_profile_signature_hash": shortDigest(cleaned),
        "managed_enrollment_present": String(cleaned.localizedCaseInsensitiveContains("enrolled")),
    ]
}

func processOutput(executable: String, arguments: [String]) -> String? {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = Pipe()
    do {
        try process.run()
        process.waitUntilExit()
    } catch {
        return nil
    }
    guard process.terminationStatus == 0 else {
        return nil
    }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    return String(data: data, encoding: .utf8)
}

func secondsBucket(_ seconds: Int) -> String {
    let hours = seconds / 3600
    return "\(hours)h"
}

func percentBucket(_ percent: Int) -> String {
    switch percent {
    case ...5: return "0-5"
    case 6...10: return "6-10"
    case 11...25: return "11-25"
    case 26...50: return "26-50"
    default: return "51-100"
    }
}

func byteBucket(_ bytes: Int64) -> String {
    let gib = Double(bytes) / 1_073_741_824.0
    switch gib {
    case ..<8: return "0-8GiB"
    case ..<32: return "8-32GiB"
    case ..<128: return "32-128GiB"
    case ..<512: return "128-512GiB"
    default: return "512GiB+"
    }
}
