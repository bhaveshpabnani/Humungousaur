import AppKit
import Foundation

final class MailCalendarWorkflowCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var foregroundSignatures: [String: String] = [:]
    private var processSignatures: [String: Set<String>] = [:]
    private var stateSignatures: [String: String] = [:]

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        sampleForegroundApp(emitInitial: emitInitial)
        sampleProcesses(emitInitial: emitInitial)
        sampleStateSnapshots(emitInitial: emitInitial)
    }

    private func sampleForegroundApp(emitInitial: Bool) {
        guard let app = NSWorkspace.shared.frontmostApplication else {
            return
        }
        for route in mailCalendarAppRoutes(app) {
            let metadata = mailCalendarForegroundMetadata(app: app, surface: route.surface)
            let signature = [
                route.collector,
                app.bundleIdentifier ?? "",
                metadata["window_id"] ?? "",
                metadata["window_title_hash"] ?? "",
            ].joined(separator: "|")
            guard emitInitial || foregroundSignatures[route.collector] != signature else {
                continue
            }
            foregroundSignatures[route.collector] = signature
            spool.append(
                collector: route.collector,
                source: route.source,
                stimulusType: route.stimulusType,
                text: route.text,
                metadata: metadata,
                payload: [
                    "app_surface": route.surface,
                    "foreground_signature_hash": shortDigest(signature),
                ],
                privacyTier: route.privacyTier
            )
            health.noteEvent()
        }
    }

    private func sampleProcesses(emitInitial: Bool) {
        let grouped = Dictionary(grouping: mailCalendarProcessSnapshots(), by: \.collector)
        let collectors = Set(grouped.keys).union(processSignatures.keys)
        for collector in collectors {
            let snapshots = grouped[collector] ?? []
            let current = Set(snapshots.map(\.signature))
            let previous = processSignatures[collector] ?? []
            let route = mailCalendarProcessRoute(collector: collector)
            for signature in current.subtracting(previous).sorted().prefix(12) {
                guard let snapshot = snapshots.first(where: { $0.signature == signature }) else {
                    continue
                }
                spool.append(
                    collector: snapshot.collector,
                    source: route.source,
                    stimulusType: route.started,
                    text: route.startedText,
                    metadata: snapshot.metadata,
                    payload: snapshot.payload,
                    privacyTier: snapshot.privacyTier
                )
                health.noteEvent()
            }
            if !emitInitial {
                for signature in previous.subtracting(current).sorted().prefix(12) {
                    spool.append(
                        collector: collector,
                        source: route.source,
                        stimulusType: route.completed,
                        text: route.completedText,
                        metadata: [
                            "native_source": "macos_mail_calendar_process_metadata",
                            "source_api": "Process.ps_comm",
                            "privacy_level": "redacted",
                            "process_signature_hash": shortDigest(signature),
                            "command_line_omitted": "true",
                            "mail_content_omitted": "true",
                            "calendar_content_omitted": "true",
                        ],
                        payload: ["process_signature_hash": shortDigest(signature)],
                        privacyTier: route.privacyTier
                    )
                    health.noteEvent()
                }
            }
            processSignatures[collector] = current
        }
    }

    private func sampleStateSnapshots(emitInitial: Bool) {
        for snapshot in mailCalendarStateSnapshots() {
            let previous = stateSignatures[snapshot.key]
            guard emitInitial || previous != snapshot.signature else {
                continue
            }
            stateSignatures[snapshot.key] = snapshot.signature
            guard emitInitial || previous != nil else {
                continue
            }
            spool.append(
                collector: snapshot.collector,
                source: snapshot.source,
                stimulusType: snapshot.stimulusType,
                text: snapshot.text,
                metadata: snapshot.metadata,
                payload: snapshot.payload,
                privacyTier: snapshot.privacyTier
            )
            health.noteEvent()
        }
    }
}
