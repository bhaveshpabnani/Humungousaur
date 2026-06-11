import Foundation

final class AccessibilityContextCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var focusedControlSignature = ""
    private var selectionSignature = ""
    private var checkboxSignature = ""

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        guard accessibilityPermissionState() == "accessibility_granted" else {
            return
        }
        guard let snapshot = focusedAccessibilitySnapshot() else {
            return
        }
        emitFocusedControl(snapshot, emitInitial: emitInitial)
        emitSelection(snapshot, emitInitial: emitInitial)
        emitCheckbox(snapshot, emitInitial: emitInitial)
    }

    private func emitFocusedControl(_ snapshot: [String: String], emitInitial: Bool) {
        let signature = [
            snapshot["app_bundle_id"] ?? "",
            snapshot["role"] ?? "",
            snapshot["subrole"] ?? "",
            snapshot["role_path_hash"] ?? "",
        ].joined(separator: "|")
        guard emitInitial || signature != focusedControlSignature else {
            return
        }
        focusedControlSignature = signature
        let role = snapshot["role"] ?? ""
        let subrole = snapshot["subrole"] ?? ""
        let stimulusType: String
        if ["AXTextField", "AXTextArea", "AXComboBox"].contains(role) || subrole == "AXSearchField" {
            stimulusType = "form_field_focused"
        } else if role == "AXButton" {
            stimulusType = "button_available"
        } else if role == "AXMenu" || role == "AXMenuItem" || role == "AXMenuButton" {
            stimulusType = "menu_opened"
        } else {
            stimulusType = "focused_control_changed"
        }
        spool.append(
            collector: "accessibility_context",
            source: "accessibility",
            stimulusType: stimulusType,
            text: "Focused accessibility control changed.",
            metadata: snapshot.merging(["native_source": "macos_accessibility", "privacy_level": "redacted"], uniquingKeysWith: { current, _ in current }),
            payload: accessibilityPayload(snapshot),
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitSelection(_ snapshot: [String: String], emitInitial: Bool) {
        let selectedChildrenCount = Int(snapshot["selected_children_count"] ?? "0") ?? 0
        let selectedTextBucket = snapshot["selected_text_length_bucket"] ?? "0"
        let selectedRolesHash = snapshot["selected_roles_hash"] ?? ""
        guard selectedChildrenCount > 0 || (selectedTextBucket != "0" && !selectedTextBucket.isEmpty) || !selectedRolesHash.isEmpty else {
            return
        }
        let signature = [
            snapshot["app_bundle_id"] ?? "",
            String(selectedChildrenCount),
            selectedTextBucket,
            selectedRolesHash,
        ].joined(separator: "|")
        guard emitInitial || signature != selectionSignature else {
            return
        }
        selectionSignature = signature
        let stimulusType: String
        let role = snapshot["role"] ?? ""
        if selectedTextBucket != "0" && !selectedTextBucket.isEmpty {
            stimulusType = "text_selection_changed"
        } else if role == "AXTable" {
            stimulusType = "table_row_selected"
        } else if role == "AXList" || role == "AXOutline" {
            stimulusType = "list_row_selected"
        } else if selectedChildrenCount > 1 {
            stimulusType = "multi_selection_changed"
        } else {
            stimulusType = "item_selected"
        }
        spool.append(
            collector: "selection_activity",
            source: "accessibility",
            stimulusType: stimulusType,
            text: "Selection metadata changed.",
            metadata: snapshot.merging(["native_source": "macos_accessibility", "privacy_level": "redacted"], uniquingKeysWith: { current, _ in current }),
            payload: accessibilityPayload(snapshot),
            privacyTier: "sensitive_metadata"
        )
        if stimulusType == "text_selection_changed" {
            spool.append(
                collector: "accessibility_context",
                source: "accessibility",
                stimulusType: "selected_text_changed",
                text: "Selected text range changed.",
                metadata: snapshot.merging(["native_source": "macos_accessibility", "privacy_level": "redacted"], uniquingKeysWith: { current, _ in current }),
                payload: accessibilityPayload(snapshot),
                privacyTier: "sensitive_metadata"
            )
        }
        health.noteEvent()
    }

    private func emitCheckbox(_ snapshot: [String: String], emitInitial: Bool) {
        guard snapshot["role"] == "AXCheckBox", let value = snapshot["control_state"] else {
            return
        }
        let signature = "\(snapshot["app_bundle_id"] ?? "")|\(snapshot["role_path_hash"] ?? "")|\(value)"
        guard emitInitial || signature != checkboxSignature else {
            return
        }
        checkboxSignature = signature
        spool.append(
            collector: "accessibility_context",
            source: "accessibility",
            stimulusType: "checkbox_toggled",
            text: "Checkbox state changed.",
            metadata: snapshot.merging(["native_source": "macos_accessibility", "privacy_level": "redacted"], uniquingKeysWith: { current, _ in current }),
            payload: accessibilityPayload(snapshot),
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
