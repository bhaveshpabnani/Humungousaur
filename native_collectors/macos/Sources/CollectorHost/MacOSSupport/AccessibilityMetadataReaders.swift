import AppKit
import ApplicationServices
import Foundation

func focusedAccessibilitySnapshot() -> [String: String]? {
    let system = AXUIElementCreateSystemWide()
    var focused: CFTypeRef?
    guard AXUIElementCopyAttributeValue(system, kAXFocusedUIElementAttribute as CFString, &focused) == .success,
          let element = focused else {
        return nil
    }
    let axElement = element as! AXUIElement
    var pid = pid_t(0)
    AXUIElementGetPid(axElement, &pid)
    let app = NSRunningApplication(processIdentifier: pid)
    let role = axString(element, kAXRoleAttribute) ?? ""
    let subrole = axString(element, kAXSubroleAttribute) ?? ""
    var snapshot: [String: String] = [
        "role": role,
        "subrole": subrole,
        "app_name": app.flatMap(safeAppName) ?? "",
        "app_bundle_id": app?.bundleIdentifier ?? "",
        "process_identifier": String(pid),
        "role_path_hash": accessibilityRolePathHash(axElement),
    ]
    if let children = axArray(element, kAXSelectedChildrenAttribute) {
        let roles = children.compactMap { axString($0, kAXRoleAttribute) }
        snapshot["selected_children_count"] = String(children.count)
        snapshot["selected_roles_hash"] = roles.isEmpty ? "" : sha256(roles.sorted().joined(separator: "|"))
    }
    if let selectedTextRange = selectedTextRange(axElement) {
        snapshot["selected_text_length_bucket"] = textLengthBucket(selectedTextRange.length)
    } else {
        snapshot["selected_text_length_bucket"] = "0"
    }
    if role == "AXCheckBox" {
        snapshot["control_state"] = controlStateBucket(axElement)
    }
    return snapshot
}

func accessibilityPayload(_ snapshot: [String: String]) -> [String: String] {
    [
        "role": snapshot["role"] ?? "",
        "subrole": snapshot["subrole"] ?? "",
        "app_bundle_id": snapshot["app_bundle_id"] ?? "",
        "role_path_hash": snapshot["role_path_hash"] ?? "",
        "selected_children_count": snapshot["selected_children_count"] ?? "",
        "selected_text_length_bucket": snapshot["selected_text_length_bucket"] ?? "",
        "selected_roles_hash": snapshot["selected_roles_hash"] ?? "",
    ]
}

func axArray(_ element: CFTypeRef, _ attribute: String) -> [CFTypeRef]? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element as! AXUIElement, attribute as CFString, &value) == .success else {
        return nil
    }
    return value as? [CFTypeRef]
}

func selectedTextRange(_ element: AXUIElement) -> CFRange? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, kAXSelectedTextRangeAttribute as CFString, &value) == .success,
          let rawValue = value,
          CFGetTypeID(rawValue) == AXValueGetTypeID() else {
        return nil
    }
    let axValue = rawValue as! AXValue
    guard
          AXValueGetType(axValue) == .cfRange else {
        return nil
    }
    var range = CFRange()
    guard AXValueGetValue(axValue, .cfRange, &range) else {
        return nil
    }
    return range
}

func controlStateBucket(_ element: AXUIElement) -> String {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, kAXValueAttribute as CFString, &value) == .success else {
        return "unknown"
    }
    if let boolValue = value as? Bool {
        return boolValue ? "on" : "off"
    }
    if let number = value as? NSNumber {
        switch number.intValue {
        case 0: return "off"
        case 1: return "on"
        default: return "mixed"
        }
    }
    return "unknown"
}

func accessibilityRolePathHash(_ element: AXUIElement) -> String {
    var roles: [String] = []
    var current: AXUIElement? = element
    for _ in 0..<4 {
        guard let item = current else {
            break
        }
        if let role = axString(item, kAXRoleAttribute) {
            roles.append(role)
        }
        var parent: CFTypeRef?
        if AXUIElementCopyAttributeValue(item, kAXParentAttribute as CFString, &parent) == .success,
           let parentElement = parent,
           CFGetTypeID(parentElement) == AXUIElementGetTypeID() {
            current = (parentElement as! AXUIElement)
        } else {
            break
        }
    }
    return roles.isEmpty ? "" : sha256(roles.joined(separator: ">"))
}

func textLengthBucket(_ length: Int) -> String {
    switch length {
    case ...0: return "0"
    case 1...20: return "1-20"
    case 21...100: return "21-100"
    default: return "100+"
    }
}
