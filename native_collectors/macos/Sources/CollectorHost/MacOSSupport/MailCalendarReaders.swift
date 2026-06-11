import AppKit
import CoreGraphics
import EventKit
import Foundation

struct MailCalendarAppRoute {
    let collector: String
    let source: String
    let stimulusType: String
    let text: String
    let privacyTier: String
    let surface: String
}

struct MailCalendarProcessSnapshot {
    let collector: String
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
    let privacyTier: String
}

struct MailCalendarProcessRoute {
    let source: String
    let started: String
    let completed: String
    let startedText: String
    let completedText: String
    let privacyTier: String
}

struct MailCalendarStateSnapshot {
    let key: String
    let collector: String
    let source: String
    let stimulusType: String
    let text: String
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
    let privacyTier: String
}

private let mailCalendarProcessCollectors: [String: String] = [
    "mail": "mail_activity",
    "calendar": "calendar_activity",
    "calendaragent": "calendar_activity",
    "reminders": "reminder_todo_activity",
    "remindersd": "reminder_todo_activity",
    "remindd": "reminder_todo_activity",
]

func mailCalendarAppRoutes(_ app: NSRunningApplication) -> [MailCalendarAppRoute] {
    let bundle = (app.bundleIdentifier ?? "").lowercased()
    let name = safeAppName(app).lowercased()
    if bundle == "com.apple.mail" || name == "mail" {
        return [
            MailCalendarAppRoute(collector: "mail_activity", source: "activity", stimulusType: "email_opened", text: "Mail app foreground metadata observed.", privacyTier: "metadata", surface: "mail"),
            MailCalendarAppRoute(collector: "mail_composition_activity", source: "activity", stimulusType: "email_draft_started", text: "Mail compose surface metadata observed.", privacyTier: "sensitive_metadata", surface: "mail_compose"),
            MailCalendarAppRoute(collector: "mail_organization_activity", source: "activity", stimulusType: "mailbox_filter_changed", text: "Mail organization surface metadata observed.", privacyTier: "sensitive_metadata", surface: "mail_organization"),
        ]
    }
    if bundle == "com.apple.ical" || name == "calendar" {
        return [
            MailCalendarAppRoute(collector: "calendar_scheduling_activity", source: "system", stimulusType: "calendar_availability_checked", text: "Calendar app foreground metadata observed.", privacyTier: "sensitive_metadata", surface: "calendar"),
        ]
    }
    if bundle == "com.apple.reminders" || name == "reminders" {
        return [
            MailCalendarAppRoute(collector: "reminder_todo_activity", source: "system", stimulusType: "todo_list_changed", text: "Reminders app foreground metadata observed.", privacyTier: "sensitive_metadata", surface: "reminders"),
        ]
    }
    return []
}

func mailCalendarForegroundMetadata(app: NSRunningApplication, surface: String) -> [String: String] {
    appMetadata(app).merging(frontmostWindowSnapshot(for: app), uniquingKeysWith: { current, _ in current }).merging([
        "native_source": "macos_mail_calendar_foreground_metadata",
        "source_api": "NSWorkspace+CGWindowList",
        "privacy_level": "redacted",
        "app_surface": surface,
        "window_title_omitted": "true",
        "message_subject_omitted": "true",
        "message_body_omitted": "true",
        "recipient_names_omitted": "true",
        "calendar_title_omitted": "true",
        "attendees_omitted": "true",
        "reminder_title_omitted": "true",
    ], uniquingKeysWith: { current, _ in current })
}

func mailCalendarProcessSnapshots() -> [MailCalendarProcessSnapshot] {
    mailCalendarProcessNames().compactMap { process in
        guard let collector = mailCalendarProcessCollectors[process.name] else {
            return nil
        }
        let category = mailCalendarProcessCategory(process.name)
        let signature = "\(collector)|\(process.name)|\(process.pid)"
        let privacyTier = collector == "mail_activity" || collector == "calendar_activity" ? "metadata" : "sensitive_metadata"
        return MailCalendarProcessSnapshot(
            collector: collector,
            signature: signature,
            metadata: [
                "native_source": "macos_mail_calendar_process_metadata",
                "source_api": "Process.ps_comm",
                "privacy_level": "redacted",
                "process_name": process.name,
                "process_category": category,
                "process_identifier_hash": shortDigest(process.pid),
                "command_line_omitted": "true",
                "window_titles_omitted": "true",
                "mail_content_omitted": "true",
                "calendar_content_omitted": "true",
                "reminder_content_omitted": "true",
            ],
            payload: [
                "process_name": process.name,
                "process_category": category,
                "process_signature_hash": shortDigest(signature),
            ],
            privacyTier: privacyTier
        )
    }
}

func mailCalendarProcessRoute(collector: String) -> MailCalendarProcessRoute {
    switch collector {
    case "mail_activity":
        return MailCalendarProcessRoute(source: "activity", started: "email_opened", completed: "email_opened", startedText: "Mail process metadata observed.", completedText: "Mail process metadata changed.", privacyTier: "metadata")
    case "calendar_activity":
        return MailCalendarProcessRoute(source: "system", started: "deadline_near", completed: "deadline_near", startedText: "Calendar process metadata observed.", completedText: "Calendar process metadata changed.", privacyTier: "metadata")
    case "reminder_todo_activity":
        return MailCalendarProcessRoute(source: "system", started: "todo_list_changed", completed: "todo_list_changed", startedText: "Reminder process metadata observed.", completedText: "Reminder process metadata changed.", privacyTier: "sensitive_metadata")
    default:
        return MailCalendarProcessRoute(source: "activity", started: "email_opened", completed: "email_opened", startedText: "Mail/calendar process metadata observed.", completedText: "Mail/calendar process metadata changed.", privacyTier: "metadata")
    }
}

func mailCalendarStateSnapshots() -> [MailCalendarStateSnapshot] {
    var snapshots: [MailCalendarStateSnapshot] = []
    snapshots.append(contentsOf: calendarEventSnapshots())
    snapshots.append(contentsOf: reminderSnapshots())
    snapshots.append(contentsOf: mailStoreSnapshots())
    return snapshots
}

private func calendarEventSnapshots() -> [MailCalendarStateSnapshot] {
    let status = eventKitAuthorizationBucket(for: .event)
    guard eventKitCanRead(for: .event) else {
        return []
    }
    let store = EKEventStore()
    let now = Date()
    let nextHour = Calendar.current.date(byAdding: .hour, value: 1, to: now) ?? now
    let nextDay = Calendar.current.date(byAdding: .day, value: 1, to: now) ?? now
    let nextWeek = Calendar.current.date(byAdding: .day, value: 7, to: now) ?? now
    let predicate = store.predicateForEvents(withStart: now, end: nextWeek, calendars: nil)
    let events = store.events(matching: predicate)
    let hourCount = events.filter { $0.startDate <= nextHour }.count
    let dayCount = events.filter { $0.startDate <= nextDay }.count
    let signatureParts = events.prefix(64).map { event in
        "\(Int(event.startDate.timeIntervalSince1970 / 300)):\(Int(event.endDate.timeIntervalSince1970 / 300)):\(event.calendar.calendarIdentifier):\(event.isAllDay)"
    }.sorted()
    let signature = shortDigest(signatureParts.joined(separator: "|"))
    let metadata = [
        "native_source": "macos_eventkit_calendar_metadata",
        "source_api": "EventKit.EKEventStore",
        "privacy_level": "redacted",
        "eventkit_authorization_status": status,
        "calendar_event_count_bucket": countBucket(events.count),
        "events_next_hour_bucket": countBucket(hourCount),
        "events_next_day_bucket": countBucket(dayCount),
        "calendar_count_bucket": countBucket(store.calendars(for: .event).count),
        "event_titles_omitted": "true",
        "attendees_omitted": "true",
        "locations_omitted": "true",
        "notes_omitted": "true",
    ]
    let payload = [
        "calendar_metadata_signature": signature,
        "calendar_event_count_bucket": countBucket(events.count),
        "events_next_hour_bucket": countBucket(hourCount),
    ]
    return [
        MailCalendarStateSnapshot(key: "calendar-upcoming", collector: "calendar_activity", source: "system", stimulusType: hourCount > 0 ? "meeting_starting" : "deadline_near", text: "Calendar upcoming event metadata changed.", signature: signature, metadata: metadata, payload: payload, privacyTier: "metadata"),
        MailCalendarStateSnapshot(key: "calendar-scheduling", collector: "calendar_scheduling_activity", source: "system", stimulusType: "calendar_event_updated", text: "Calendar scheduling metadata changed.", signature: signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
    ]
}

private func reminderSnapshots() -> [MailCalendarStateSnapshot] {
    let status = eventKitAuthorizationBucket(for: .reminder)
    guard eventKitCanRead(for: .reminder) else {
        return []
    }
    let store = EKEventStore()
    let calendars = store.calendars(for: .reminder)
    let predicate = store.predicateForReminders(in: calendars)
    let reminders = fetchReminders(store: store, predicate: predicate)
    let now = Date()
    let nextDay = Calendar.current.date(byAdding: .day, value: 1, to: now) ?? now
    let dueSoon = reminders.filter { reminder in
        guard !reminder.isCompleted,
              let due = reminder.dueDateComponents?.date else {
            return false
        }
        return due <= nextDay
    }.count
    let incomplete = reminders.filter { !$0.isCompleted }.count
    let signatureParts = reminders.prefix(128).map { reminder in
        let due = reminder.dueDateComponents?.date.map { Int($0.timeIntervalSince1970 / 3600) } ?? 0
        let completed = reminder.isCompleted ? "done" : "open"
        return "\(reminder.calendar.calendarIdentifier):\(completed):\(due)"
    }.sorted()
    let signature = shortDigest(signatureParts.joined(separator: "|"))
    let metadata = [
        "native_source": "macos_eventkit_reminder_metadata",
        "source_api": "EventKit.EKEventStore",
        "privacy_level": "redacted",
        "eventkit_authorization_status": status,
        "reminder_count_bucket": countBucket(reminders.count),
        "incomplete_reminder_count_bucket": countBucket(incomplete),
        "due_soon_count_bucket": countBucket(dueSoon),
        "reminder_list_count_bucket": countBucket(calendars.count),
        "reminder_titles_omitted": "true",
        "notes_omitted": "true",
        "list_names_omitted": "true",
    ]
    let payload = [
        "reminder_metadata_signature": signature,
        "due_soon_count_bucket": countBucket(dueSoon),
        "incomplete_reminder_count_bucket": countBucket(incomplete),
    ]
    return [
        MailCalendarStateSnapshot(key: "wakeups-reminders", collector: "wakeups", source: "system", stimulusType: dueSoon > 0 ? "followup_due" : "scheduled_wakeup_due", text: "Reminder due metadata changed.", signature: signature, metadata: metadata, payload: payload, privacyTier: "metadata"),
        MailCalendarStateSnapshot(key: "reminders", collector: "reminder_todo_activity", source: "system", stimulusType: "todo_due_date_changed", text: "Reminder/to-do metadata changed.", signature: signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
    ]
}

private func mailStoreSnapshots() -> [MailCalendarStateSnapshot] {
    let root = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Mail", isDirectory: true)
    guard FileManager.default.fileExists(atPath: root.path) else {
        return []
    }
    let versionDirs = (try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: [.contentModificationDateKey, .isDirectoryKey], options: [.skipsHiddenFiles])) ?? []
    let existing = versionDirs.filter { (($0.pathExtension.isEmpty && $0.lastPathComponent.hasPrefix("V")) || $0.lastPathComponent == "PersistenceInfo.plist") }
    let parts = existing.map { mailCalendarFileSignature($0) }.sorted()
    let signature = shortDigest(parts.joined(separator: "|"))
    let metadata = [
        "native_source": "macos_mail_store_metadata",
        "source_api": "FileManager",
        "privacy_level": "redacted",
        "mail_store_signature_hash": signature,
        "mail_store_item_count_bucket": countBucket(existing.count),
        "mail_paths_omitted": "true",
        "mailbox_names_omitted": "true",
        "message_subjects_omitted": "true",
        "message_bodies_omitted": "true",
        "sender_recipient_names_omitted": "true",
    ]
    let payload = [
        "mail_store_signature_hash": signature,
        "mail_store_item_count_bucket": countBucket(existing.count),
    ]
    return [
        MailCalendarStateSnapshot(key: "mail-store", collector: "mail_activity", source: "activity", stimulusType: "email_received", text: "Mail store metadata changed.", signature: signature, metadata: metadata, payload: payload, privacyTier: "metadata"),
        MailCalendarStateSnapshot(key: "mail-organization", collector: "mail_organization_activity", source: "activity", stimulusType: "mailbox_filter_changed", text: "Mail organization metadata changed.", signature: signature, metadata: metadata, payload: payload, privacyTier: "sensitive_metadata"),
    ]
}

private func eventKitCanRead(for entity: EKEntityType) -> Bool {
    switch EKEventStore.authorizationStatus(for: entity) {
    case .authorized, .fullAccess:
        return true
    case .notDetermined, .restricted, .denied, .writeOnly:
        return false
    @unknown default:
        return false
    }
}

private func eventKitAuthorizationBucket(for entity: EKEntityType) -> String {
    switch EKEventStore.authorizationStatus(for: entity) {
    case .notDetermined: return "not_determined"
    case .restricted: return "restricted"
    case .denied: return "denied"
    case .authorized: return "authorized"
    case .fullAccess: return "full_access"
    case .writeOnly: return "write_only"
    @unknown default: return "unknown"
    }
}

private func fetchReminders(store: EKEventStore, predicate: NSPredicate) -> [EKReminder] {
    let semaphore = DispatchSemaphore(value: 0)
    var reminders: [EKReminder] = []
    store.fetchReminders(matching: predicate) { fetched in
        reminders = fetched ?? []
        semaphore.signal()
    }
    _ = semaphore.wait(timeout: .now() + 2.0)
    return reminders
}

private func mailCalendarProcessNames() -> [(pid: String, name: String)] {
    guard let output = processOutput(executable: "/bin/ps", arguments: ["-axo", "pid=,comm="]) else {
        return []
    }
    return output.split(separator: "\n").compactMap { line in
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let firstSpace = trimmed.firstIndex(where: { $0 == " " || $0 == "\t" }) else {
            return nil
        }
        let pid = String(trimmed[..<firstSpace]).trimmingCharacters(in: .whitespacesAndNewlines)
        let command = String(trimmed[firstSpace...]).trimmingCharacters(in: .whitespacesAndNewlines)
        let name = sanitizedMailCalendarProcessName(URL(fileURLWithPath: command).lastPathComponent)
        guard !pid.isEmpty, !name.isEmpty else {
            return nil
        }
        return (pid, name)
    }
}

private func sanitizedMailCalendarProcessName(_ raw: String) -> String {
    let cleaned = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    return String(cleaned.filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" || $0 == "." }.prefix(48))
}

private func mailCalendarProcessCategory(_ name: String) -> String {
    switch name {
    case "mail": return "mail_app"
    case "calendar", "calendaragent": return "calendar_agent"
    case "reminders", "remindersd", "remindd": return "reminder_agent"
    default: return "mail_calendar"
    }
}

private func mailCalendarFileSignature(_ url: URL) -> String {
    if let values = try? url.resourceValues(forKeys: [.isDirectoryKey, .contentModificationDateKey, .fileSizeKey]) {
        let modified = Int(values.contentModificationDate?.timeIntervalSince1970 ?? 0)
        let size = values.fileSize ?? 0
        return "\(shortDigest(url.path)):\(values.isDirectory == true ? "dir" : "file"):\(modified):\(size)"
    }
    return "\(shortDigest(url.path)):missing"
}
