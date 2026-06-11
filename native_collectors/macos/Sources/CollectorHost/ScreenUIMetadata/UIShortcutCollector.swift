import AppKit
import Foundation

final class UIShortcutCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installEventMonitors() -> [Any] {
        var monitors: [Any] = []
        if let monitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown, handler: { [weak self] event in
            self?.handleKeyDown(event)
        }) {
            monitors.append(monitor)
        }
        if let monitor = NSEvent.addGlobalMonitorForEvents(matching: [.rightMouseDown, .otherMouseDown], handler: { [weak self] event in
            self?.handleMouse(event)
        }) {
            monitors.append(monitor)
        }
        return monitors
    }

    private func handleMouse(_ event: NSEvent) {
        guard event.type == .rightMouseDown else {
            return
        }
        appendCommand(
            collector: "command_activity",
            stimulusType: "context_menu_opened",
            text: "Context menu opened.",
            metadata: ["button_number": String(event.buttonNumber), "source_api": "NSEventGlobalMonitor"]
        )
    }

    private func handleKeyDown(_ event: NSEvent) {
        let modifiers = normalizedModifiers(event.modifierFlags)
        guard modifiers.contains("command") || modifiers.contains("control") || modifiers.contains("option") else {
            return
        }
        let metadata = shortcutMetadata(event: event, modifiers: modifiers)
        if modifiers.contains("command"), event.keyCode == 6 {
            appendCommand(collector: "edit_history_activity", stimulusType: modifiers.contains("shift") ? "redo_performed" : "undo_performed", text: "Edit history shortcut performed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), event.keyCode == 1 {
            appendCommand(collector: "edit_history_activity", stimulusType: "manual_save_completed", text: "Manual save shortcut performed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), event.keyCode == 35, modifiers.contains("shift") {
            appendCommand(collector: "command_activity", stimulusType: "command_palette_opened", text: "Command palette shortcut performed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), event.keyCode == 33 {
            appendCommand(collector: "navigation_activity", stimulusType: "in_app_back", text: "In-app back shortcut performed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), event.keyCode == 30 {
            appendCommand(collector: "navigation_activity", stimulusType: "in_app_forward", text: "In-app forward shortcut performed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), (18...26).contains(Int(event.keyCode)) {
            appendCommand(collector: "navigation_activity", stimulusType: "in_app_tab_switched", text: "In-app tab shortcut performed.", metadata: metadata)
            return
        }
        appendCommand(collector: "command_activity", stimulusType: "shortcut_action_triggered", text: "Keyboard shortcut action triggered.", metadata: metadata)
    }

    private func appendCommand(collector: String, stimulusType: String, text: String, metadata: [String: String]) {
        spool.append(
            collector: collector,
            source: "accessibility",
            stimulusType: stimulusType,
            text: text,
            metadata: metadata.merging(["native_source": "macos_nsevent", "privacy_level": "redacted"], uniquingKeysWith: { current, _ in current }),
            payload: metadata,
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func shortcutMetadata(event: NSEvent, modifiers: [String]) -> [String: String] {
        [
            "key_code": String(event.keyCode),
            "modifiers": modifiers.joined(separator: "+"),
            "source_api": "NSEventGlobalMonitor",
        ]
    }
}
