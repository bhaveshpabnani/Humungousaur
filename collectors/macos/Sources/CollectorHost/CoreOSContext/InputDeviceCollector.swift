import AppKit
import Foundation

final class InputDeviceCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private let pasteboardWorkflow: PasteboardWorkflowCollector
    private var dragInProgress = false
    private var lastScrollAt = Date.distantPast

    init(spool: CollectorSpool, health: HelperHealthReporter, pasteboardWorkflow: PasteboardWorkflowCollector) {
        self.spool = spool
        self.health = health
        self.pasteboardWorkflow = pasteboardWorkflow
    }

    func installEventMonitors() -> [Any] {
        var monitors: [Any] = []
        let mouseMask: NSEvent.EventTypeMask = [.leftMouseDown, .rightMouseDown, .otherMouseDown, .leftMouseDragged, .rightMouseDragged, .otherMouseDragged]
        if let monitor = NSEvent.addGlobalMonitorForEvents(matching: mouseMask, handler: { [weak self] event in
            self?.handleMouseEvent(event)
        }) {
            monitors.append(monitor)
        }
        if let monitor = NSEvent.addGlobalMonitorForEvents(matching: .scrollWheel, handler: { [weak self] _ in
            self?.handleScrollEvent()
        }) {
            monitors.append(monitor)
        }
        if let monitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown, handler: { [weak self] event in
            self?.handleKeyDown(event)
        }) {
            monitors.append(monitor)
        }
        return monitors
    }

    private func handleMouseEvent(_ event: NSEvent) {
        let stimulusType: String
        switch event.type {
        case .rightMouseDown:
            stimulusType = "mouse_right_clicked"
        case .otherMouseDown where event.buttonNumber == 3:
            stimulusType = "mouse_back"
        case .otherMouseDown where event.buttonNumber == 4:
            stimulusType = "mouse_forward"
        case .leftMouseDragged, .rightMouseDragged, .otherMouseDragged:
            guard !dragInProgress else {
                return
            }
            dragInProgress = true
            stimulusType = "mouse_drag_started"
        default:
            dragInProgress = false
            stimulusType = event.clickCount >= 2 ? "mouse_double_clicked" : "mouse_clicked"
        }
        spool.append(
            collector: "input_device",
            source: "activity",
            stimulusType: stimulusType,
            text: "Input device event: \(stimulusType.replacingOccurrences(of: "_", with: " ")).",
            metadata: [
                "button_number": String(event.buttonNumber),
                "click_count": String(event.clickCount),
                "source_api": "NSEventGlobalMonitor",
            ],
            payload: [:]
        )
        health.noteEvent()
    }

    private func handleScrollEvent() {
        let now = Date()
        guard now.timeIntervalSince(lastScrollAt) > 1.0 else {
            return
        }
        lastScrollAt = now
        spool.append(
            collector: "input_device",
            source: "activity",
            stimulusType: "mouse_scroll_burst",
            text: "Scroll input burst observed.",
            metadata: ["source_api": "NSEventGlobalMonitor"],
            payload: [:]
        )
        health.noteEvent()
    }

    private func handleKeyDown(_ event: NSEvent) {
        let modifiers = normalizedModifiers(event.modifierFlags)
        guard modifiers.contains("command") || modifiers.contains("control") || modifiers.contains("option") else {
            return
        }
        if modifiers.contains("command"), event.keyCode == 9 {
            pasteboardWorkflow.emitPasteCommand(matchStyle: modifiers.contains("shift") && modifiers.contains("option"))
            return
        }
        spool.append(
            collector: "input_device",
            source: "activity",
            stimulusType: "keyboard_shortcut_pressed",
            text: "Keyboard shortcut pressed.",
            metadata: [
                "key_code": String(event.keyCode),
                "modifiers": modifiers.joined(separator: "+"),
                "source_api": "NSEventGlobalMonitor",
            ],
            payload: [:]
        )
        health.noteEvent()
    }
}
