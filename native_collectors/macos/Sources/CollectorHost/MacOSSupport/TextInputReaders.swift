import AppKit
import ApplicationServices
import Carbon
import Foundation

func focusedTextSurface() -> [String: String]? {
    let system = AXUIElementCreateSystemWide()
    var focused: CFTypeRef?
    guard AXUIElementCopyAttributeValue(system, kAXFocusedUIElementAttribute as CFString, &focused) == .success,
          let element = focused else {
        return nil
    }
    let role = axString(element, kAXRoleAttribute) ?? ""
    let subrole = axString(element, kAXSubroleAttribute) ?? ""
    guard ["AXTextField", "AXTextArea", "AXComboBox"].contains(role) || subrole == "AXSearchField" else {
        return nil
    }

    var pid = pid_t(0)
    AXUIElementGetPid(element as! AXUIElement, &pid)
    let app = NSRunningApplication(processIdentifier: pid)
    return [
        "role": role,
        "subrole": subrole,
        "is_secure": (role == "AXTextField" && subrole == "AXSecureTextField") ? "true" : "false",
        "app_name": app.flatMap(safeAppName) ?? "",
        "app_bundle_id": app?.bundleIdentifier ?? "",
        "process_identifier": String(pid),
    ]
}

func axString(_ element: CFTypeRef, _ attribute: String) -> String? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element as! AXUIElement, attribute as CFString, &value) == .success else {
        return nil
    }
    return value as? String
}

func currentInputSource() -> [String: String] {
    guard let source = TISCopyCurrentKeyboardInputSource()?.takeRetainedValue() else {
        return [:]
    }
    let sourceID = tisString(source, kTISPropertyInputSourceID) ?? ""
    let localizedName = tisString(source, kTISPropertyLocalizedName) ?? ""
    let category = tisString(source, kTISPropertyInputSourceCategory) ?? ""
    let kind = sourceID.localizedCaseInsensitiveContains("inputmethod") || category.localizedCaseInsensitiveContains("inputmethod") ? "ime" : "keyboard"
    return [
        "input_source_id": sourceID,
        "input_source_name": localizedName,
        "input_source_category": category,
        "input_source_kind": kind,
    ]
}

func tisString(_ source: TISInputSource, _ key: CFString) -> String? {
    guard let raw = TISGetInputSourceProperty(source, key) else {
        return nil
    }
    return Unmanaged<CFString>.fromOpaque(raw).takeUnretainedValue() as String
}

func accessibilityPermissionState() -> String {
    AXIsProcessTrusted() ? "accessibility_granted" : "accessibility_not_granted"
}
