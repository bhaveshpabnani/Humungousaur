import AppKit
import CoreGraphics
import Foundation

struct CommunicationMeetingSurface {
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
    let isSharingSurface: Bool
    let isRecordingSurface: Bool
}

struct CommunicationProcessSnapshot {
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
}

struct CommunicationForegroundSnapshot {
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
    let category: String
    let isMeeting: Bool
}

struct CommunicationForegroundRoute {
    let collector: String
    let source: String
    let stimulusType: String
    let text: String
    let privacyTier: String
}

private let communicationBundleHints: [String: String] = [
    "us.zoom.xos": "meeting",
    "com.cisco.webexmeetingsapp": "meeting",
    "com.webex.meetingmanager": "meeting",
    "com.microsoft.teams": "meeting_chat",
    "com.microsoft.teams2": "meeting_chat",
    "com.tinyspeck.slackmacgap": "chat",
    "com.hnc.discord": "meeting_chat",
    "com.skype.skype": "meeting_chat",
    "com.ringcentral": "meeting_chat",
    "com.apple.facetime": "voice_meeting",
    "com.apple.MobileSMS": "chat",
    "net.whatsapp.WhatsApp": "chat",
    "org.whispersystems.signal-desktop": "chat",
    "ru.keepcoder.Telegram": "chat",
    "com.microsoft.Outlook": "mail_chat",
    "com.apple.mail": "mail_chat",
]

private let communicationNameHints: [(String, String)] = [
    ("zoom", "meeting"),
    ("webex", "meeting"),
    ("teams", "meeting_chat"),
    ("slack", "chat"),
    ("discord", "meeting_chat"),
    ("skype", "meeting_chat"),
    ("ringcentral", "meeting_chat"),
    ("facetime", "voice_meeting"),
    ("messages", "chat"),
    ("whatsapp", "chat"),
    ("signal", "chat"),
    ("telegram", "chat"),
    ("outlook", "mail_chat"),
]

func communicationAppCategory(_ app: NSRunningApplication) -> String? {
    let bundle = (app.bundleIdentifier ?? "").lowercased()
    for (hint, category) in communicationBundleHints where bundle == hint.lowercased() || bundle.contains(hint.lowercased()) {
        return category
    }
    let name = safeAppName(app).lowercased()
    return communicationNameHints.first { name.contains($0.0) }?.1
}

func communicationAppProcessSnapshots() -> [CommunicationProcessSnapshot] {
    NSWorkspace.shared.runningApplications.compactMap { app in
        guard let category = communicationAppCategory(app) else {
            return nil
        }
        let signature = [
            app.bundleIdentifier ?? "",
            safeAppName(app),
            String(app.processIdentifier),
        ].joined(separator: "|")
        let metadata = appMetadata(app).merging(communicationRedactedMetadata(sourceAPI: "NSWorkspace.runningApplications"), uniquingKeysWith: { current, _ in current }).merging([
            "communication_app_category": category,
            "process_identifier_hash": shortDigest(String(app.processIdentifier)),
        ], uniquingKeysWith: { current, _ in current })
        return CommunicationProcessSnapshot(
            signature: signature,
            metadata: metadata,
            payload: [
                "app_signature_hash": shortDigest(signature),
                "communication_app_category": category,
            ]
        )
    }
}

func communicationMeetingSurfaces() -> [CommunicationMeetingSurface] {
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        return []
    }
    return windows.compactMap { window in
        guard let ownerPID = window[kCGWindowOwnerPID as String] as? pid_t,
              let app = NSRunningApplication(processIdentifier: ownerPID),
              let category = communicationAppCategory(app),
              category.contains("meeting") || category.contains("voice") else {
            return nil
        }
        let layer = window[kCGWindowLayer as String] as? Int
        guard layer == 0 else {
            return nil
        }
        return communicationMeetingSurface(app: app, window: window, category: category)
    }
}

func frontmostCommunicationAppSnapshot() -> CommunicationForegroundSnapshot? {
    guard let app = NSWorkspace.shared.frontmostApplication,
          let category = communicationAppCategory(app) else {
        return nil
    }
    let window = frontmostCommunicationWindow(for: app)
    let windowMetadata = communicationWindowMetadata(window)
    let signature = [
        app.bundleIdentifier ?? "",
        windowMetadata["window_id"] ?? "",
        windowMetadata["window_title_hash"] ?? "",
        category,
    ].joined(separator: "|")
    let isMeeting = category.contains("meeting") || category.contains("voice") || communicationTitleHints(window).contains("meeting")
    let metadata = appMetadata(app).merging(windowMetadata, uniquingKeysWith: { current, _ in current }).merging(communicationRedactedMetadata(sourceAPI: "NSWorkspace+CGWindowList"), uniquingKeysWith: { current, _ in current }).merging([
        "communication_app_category": category,
        "meeting_surface_detected": String(isMeeting),
    ], uniquingKeysWith: { current, _ in current })
    return CommunicationForegroundSnapshot(
        signature: signature,
        metadata: metadata,
        payload: [
            "foreground_signature_hash": shortDigest(signature),
            "communication_app_category": category,
            "meeting_surface_detected": String(isMeeting),
        ],
        category: category,
        isMeeting: isMeeting
    )
}

func communicationForegroundRoutes(_ snapshot: CommunicationForegroundSnapshot) -> [CommunicationForegroundRoute] {
    var routes = [
        CommunicationForegroundRoute(collector: "communication_activity", source: "channel_message", stimulusType: "channel_unread_changed", text: "Communication app foreground metadata changed.", privacyTier: "metadata"),
        CommunicationForegroundRoute(collector: "channel_activity", source: "channel_message", stimulusType: "channel_unread_changed", text: "Channel app foreground metadata changed.", privacyTier: "metadata"),
        CommunicationForegroundRoute(collector: "chat_channel_navigation_activity", source: "channel_message", stimulusType: "chat_channel_opened", text: "Chat channel surface metadata changed.", privacyTier: "sensitive_metadata"),
        CommunicationForegroundRoute(collector: "chat_thread_activity", source: "channel_message", stimulusType: "thread_opened", text: "Chat thread/surface metadata changed.", privacyTier: "sensitive_metadata"),
        CommunicationForegroundRoute(collector: "chat_presence_activity", source: "channel_message", stimulusType: "presence_changed", text: "Chat presence app metadata changed.", privacyTier: "sensitive_metadata"),
    ]
    if snapshot.isMeeting {
        routes.append(CommunicationForegroundRoute(collector: "meeting_app_activity", source: "activity", stimulusType: "meeting_joined", text: "Meeting app foreground metadata changed.", privacyTier: "sensitive_metadata"))
        routes.append(CommunicationForegroundRoute(collector: "meeting_audio", source: "audio_transcript", stimulusType: "call_started", text: "Meeting audio/call foreground metadata changed.", privacyTier: "sensitive_metadata"))
    }
    if snapshot.category.contains("voice") {
        routes.append(CommunicationForegroundRoute(collector: "voice_wakeup", source: "voice_transcript", stimulusType: "wake_word_detected", text: "Voice app foreground metadata changed.", privacyTier: "sensitive_metadata"))
    }
    return routes
}

func communicationMeetingSurface(app: NSRunningApplication, window: [String: Any], category: String) -> CommunicationMeetingSurface {
    let windowMetadata = communicationWindowMetadata(window)
    let hints = communicationTitleHints(window)
    let signature = [
        app.bundleIdentifier ?? "",
        String(app.processIdentifier),
        windowMetadata["window_id"] ?? "",
        windowMetadata["window_title_hash"] ?? "",
        category,
    ].joined(separator: "|")
    let sharing = hints.contains("share") || hints.contains("present")
    let recording = hints.contains("record")
    let metadata = appMetadata(app).merging(windowMetadata, uniquingKeysWith: { current, _ in current }).merging(communicationRedactedMetadata(sourceAPI: "CGWindowListCopyWindowInfo"), uniquingKeysWith: { current, _ in current }).merging([
        "communication_app_category": category,
        "meeting_surface_hint": hints.sorted().joined(separator: "+"),
        "surface_signature_hash": shortDigest(signature),
    ], uniquingKeysWith: { current, _ in current })
    return CommunicationMeetingSurface(
        signature: signature,
        metadata: metadata,
        payload: [
            "surface_signature_hash": shortDigest(signature),
            "communication_app_category": category,
            "meeting_surface_hint": hints.sorted().joined(separator: "+"),
        ],
        isSharingSurface: sharing,
        isRecordingSurface: recording
    )
}

func frontmostCommunicationWindow(for app: NSRunningApplication) -> [String: Any]? {
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        return nil
    }
    return windows.first { window in
        let ownerPID = window[kCGWindowOwnerPID as String] as? pid_t
        let layer = window[kCGWindowLayer as String] as? Int
        return ownerPID == app.processIdentifier && layer == 0
    }
}

func communicationWindowMetadata(_ window: [String: Any]?) -> [String: String] {
    guard let window else {
        return [
            "window_visible": "false",
            "window_title_omitted": "true",
        ]
    }
    let title = (window[kCGWindowName as String] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    var metadata = [
        "window_visible": "true",
        "window_id": window[kCGWindowNumber as String].map { String(describing: $0) } ?? "",
        "window_title_present": title.isEmpty ? "false" : "true",
        "window_title_hash": title.isEmpty ? "" : sha256(title),
        "window_title_length_bucket": titleLengthBucket(title),
        "window_title_omitted": "true",
    ]
    if let bounds = window[kCGWindowBounds as String] as? [String: Any] {
        metadata["window_bounds_bucket"] = boundsBucket(bounds)
    }
    return metadata
}

func communicationTitleHints(_ window: [String: Any]?) -> Set<String> {
    let title = ((window?[kCGWindowName as String] as? String) ?? "").lowercased()
    var hints: Set<String> = []
    if title.contains("meeting") || title.contains("call") || title.contains("huddle") || title.contains("webinar") {
        hints.insert("meeting")
    }
    if title.contains("share") || title.contains("sharing") {
        hints.insert("share")
    }
    if title.contains("present") || title.contains("presentation") {
        hints.insert("present")
    }
    if title.contains("record") || title.contains("recording") {
        hints.insert("record")
    }
    if title.contains("thread") {
        hints.insert("thread")
    }
    return hints
}

func communicationRedactedMetadata(sourceAPI: String) -> [String: String] {
    [
        "native_source": "macos_communication_meeting_metadata",
        "source_api": sourceAPI,
        "privacy_level": "redacted",
        "raw_audio_captured": "false",
        "transcript_text_omitted": "true",
        "message_body_omitted": "true",
        "participant_names_omitted": "true",
        "meeting_title_omitted": "true",
        "channel_names_omitted": "true",
        "workspace_names_omitted": "true",
        "thread_titles_omitted": "true",
        "custom_status_text_omitted": "true",
        "notification_content_omitted": "true",
    ]
}

func communicationShortcutMetadata(app: NSRunningApplication, category: String, event: NSEvent, modifiers: [String]) -> [String: String] {
    appMetadata(app).merging(communicationRedactedMetadata(sourceAPI: "NSEventGlobalMonitor"), uniquingKeysWith: { current, _ in current }).merging([
        "communication_app_category": category,
        "key_code": String(event.keyCode),
        "modifiers": modifiers.joined(separator: "+"),
        "shortcut_signature_hash": shortDigest("\(app.bundleIdentifier ?? ""):\(event.keyCode):\(modifiers.joined(separator: "+"))"),
    ], uniquingKeysWith: { current, _ in current })
}

func communicationShortcutPayload(_ metadata: [String: String]) -> [String: String] {
    [
        "communication_app_category": metadata["communication_app_category"] ?? "",
        "shortcut_signature_hash": metadata["shortcut_signature_hash"] ?? "",
        "key_code": metadata["key_code"] ?? "",
        "modifiers": metadata["modifiers"] ?? "",
    ]
}
