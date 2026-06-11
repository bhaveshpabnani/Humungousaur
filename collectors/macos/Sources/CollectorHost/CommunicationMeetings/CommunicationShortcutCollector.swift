import AppKit
import Foundation

final class CommunicationShortcutCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installEventMonitors() -> [Any] {
        guard let monitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown, handler: { [weak self] event in
            self?.handleKeyDown(event)
        }) else {
            return []
        }
        return [monitor]
    }

    private func handleKeyDown(_ event: NSEvent) {
        guard let app = NSWorkspace.shared.frontmostApplication,
              let category = communicationAppCategory(app) else {
            return
        }
        let modifiers = normalizedModifiers(event.modifierFlags)
        guard modifiers.contains("command") || modifiers.contains("control") || modifiers.contains("option") else {
            return
        }
        let metadata = communicationShortcutMetadata(app: app, category: category, event: event, modifiers: modifiers)

        if modifiers.contains("command"), event.keyCode == 36 {
            emitChatSend(metadata)
            return
        }
        if modifiers.contains("command"), event.keyCode == 40 {
            emitChat(collector: "chat_composition_activity", stimulusType: "emoji_picker_opened", text: "Chat emoji picker shortcut metadata observed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), event.keyCode == 8 || (modifiers.contains("command") && event.keyCode == 3) {
            emitChat(collector: "chat_channel_navigation_activity", stimulusType: "chat_channel_search_performed", text: "Chat search/navigation shortcut metadata observed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), modifiers.contains("shift"), event.keyCode == 32 {
            emitChat(collector: "chat_composition_activity", stimulusType: "chat_attachment_added", text: "Chat attachment shortcut metadata observed.", metadata: metadata)
            return
        }

        guard category.contains("meeting") || category.contains("voice") else {
            return
        }
        if modifiers.contains("command"), modifiers.contains("shift"), [46, 0].contains(Int(event.keyCode)) {
            emitCallControl(stimulusType: "microphone_muted", text: "Meeting microphone shortcut metadata observed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), modifiers.contains("shift"), [9, 31].contains(Int(event.keyCode)) {
            emitCallControl(stimulusType: "camera_disabled", text: "Meeting camera shortcut metadata observed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), modifiers.contains("shift"), [1, 14].contains(Int(event.keyCode)) {
            emitMeetingPresentation(stimulusType: "screen_share_started", text: "Meeting share shortcut metadata observed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), modifiers.contains("shift"), [4, 16].contains(Int(event.keyCode)) {
            emitCallControl(stimulusType: "hand_raised", text: "Meeting reaction/hand shortcut metadata observed.", metadata: metadata)
            return
        }
        if modifiers.contains("command"), modifiers.contains("shift"), event.keyCode == 35 {
            emitCallControl(stimulusType: "meeting_chat_opened", text: "Meeting chat shortcut metadata observed.", metadata: metadata)
        }
    }

    private func emitChatSend(_ metadata: [String: String]) {
        for collector in ["chat_composition_activity", "communication_activity", "channel_activity"] {
            let stimulus = collector == "chat_composition_activity" ? "chat_message_sent" : "message_sent"
            emitChat(collector: collector, stimulusType: stimulus, text: "Chat send shortcut metadata observed.", metadata: metadata)
        }
    }

    private func emitChat(collector: String, stimulusType: String, text: String, metadata: [String: String]) {
        spool.append(
            collector: collector,
            source: "channel_message",
            stimulusType: stimulusType,
            text: text,
            metadata: metadata,
            payload: communicationShortcutPayload(metadata),
            privacyTier: collector == "channel_activity" || collector == "communication_activity" ? "metadata" : "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitCallControl(stimulusType: String, text: String, metadata: [String: String]) {
        spool.append(
            collector: "call_control_activity",
            source: "activity",
            stimulusType: stimulusType,
            text: text,
            metadata: metadata,
            payload: communicationShortcutPayload(metadata),
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitMeetingPresentation(stimulusType: String, text: String, metadata: [String: String]) {
        spool.append(
            collector: "meeting_presentation_activity",
            source: "activity",
            stimulusType: stimulusType,
            text: text,
            metadata: metadata,
            payload: communicationShortcutPayload(metadata),
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
