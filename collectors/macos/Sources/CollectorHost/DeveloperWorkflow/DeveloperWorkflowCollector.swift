import AppKit
import Foundation

final class DeveloperWorkflowCollector {
    private let options: DeveloperWorkflowOptions
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var processSignatures: [String: Set<String>] = [:]
    private var foregroundAppSignature = ""
    private var workspaceSignatures: [String: String] = [:]
    private var serviceSignatures: Set<String> = []

    init(options: DeveloperWorkflowOptions, spool: CollectorSpool, health: HelperHealthReporter) {
        self.options = options
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        sampleForegroundDeveloperApp(emitInitial: emitInitial)
        sampleProcesses(emitInitial: emitInitial)
        sampleLocalServices(emitInitial: emitInitial)
        sampleWorkspaceFiles(emitInitial: emitInitial)
    }

    private func sampleForegroundDeveloperApp(emitInitial: Bool) {
        guard let app = NSWorkspace.shared.frontmostApplication,
              let route = developerAppRoute(app) else {
            return
        }
        let snapshot = developerForegroundMetadata(app: app)
        let signature = [
            route.collector,
            app.bundleIdentifier ?? "",
            snapshot["window_id"] ?? "",
            snapshot["window_title_hash"] ?? "",
        ].joined(separator: "|")
        guard emitInitial || foregroundAppSignature != signature else {
            return
        }
        foregroundAppSignature = signature
        spool.append(
            collector: route.collector,
            source: "activity",
            stimulusType: route.stimulusType,
            text: route.text,
            metadata: snapshot.merging([
                "native_source": "macos_developer_foreground_app_metadata",
                "privacy_level": "redacted",
            ], uniquingKeysWith: { current, _ in current }),
            payload: ["foreground_signature_hash": shortDigest(signature)],
            privacyTier: route.privacyTier
        )
        health.noteEvent()
    }

    private func sampleProcesses(emitInitial: Bool) {
        let grouped = Dictionary(grouping: developerProcessSnapshots(), by: \.collector)
        let collectors = Set(grouped.keys).union(processSignatures.keys)
        for collector in collectors {
            let snapshots = grouped[collector] ?? []
            let current = Set(snapshots.map(\.signature))
            let previous = processSignatures[collector] ?? []
            let route = processRoute(collector: collector)
            for signature in current.subtracting(previous).sorted().prefix(12) {
                guard let snapshot = snapshots.first(where: { $0.signature == signature }) else {
                    continue
                }
                emitProcess(snapshot, stimulusType: route.started, text: route.startedText)
            }
            if !emitInitial {
                for signature in previous.subtracting(current).sorted().prefix(12) {
                    emitProcessStop(collector: collector, signature: signature, route: route)
                }
            }
            processSignatures[collector] = current
        }
    }

    private func emitProcess(_ snapshot: DeveloperProcessSnapshot, stimulusType: String, text: String) {
        spool.append(
            collector: snapshot.collector,
            source: "activity",
            stimulusType: stimulusType,
            text: text,
            metadata: snapshot.metadata,
            payload: snapshot.payload,
            privacyTier: snapshot.privacyTier
        )
        health.noteEvent()
    }

    private func emitProcessStop(collector: String, signature: String, route: ProcessRoute) {
        spool.append(
            collector: collector,
            source: "activity",
            stimulusType: route.completed,
            text: route.completedText,
            metadata: [
                "native_source": "macos_process_name_metadata",
                "source_api": "Process.ps_comm",
                "privacy_level": "redacted",
                "process_signature_hash": shortDigest(signature),
                "command_line_omitted": "true",
                "logs_omitted": "true",
            ],
            payload: ["process_signature_hash": shortDigest(signature)],
            privacyTier: collector == "terminal_activity" || collector == "ide_activity" || collector == "git_activity" || collector == "github_activity" ? "metadata" : "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func sampleLocalServices(emitInitial: Bool) {
        let snapshots = localServiceSnapshots()
        let current = Set(snapshots.map(\.signature))
        for signature in current.subtracting(serviceSignatures).sorted().prefix(12) {
            guard emitInitial || !serviceSignatures.isEmpty,
                  let snapshot = snapshots.first(where: { $0.signature == signature }) else {
                continue
            }
            spool.append(
                collector: "local_service_activity",
                source: "activity",
                stimulusType: "dev_server_started",
                text: "Local service listener metadata changed.",
                metadata: snapshot.metadata,
                payload: snapshot.payload,
                privacyTier: "sensitive_metadata"
            )
            health.noteEvent()
        }
        if !emitInitial {
            for signature in serviceSignatures.subtracting(current).sorted().prefix(12) {
                spool.append(
                    collector: "local_service_activity",
                    source: "activity",
                    stimulusType: "dev_server_stopped",
                    text: "Local service listener stopped.",
                    metadata: [
                        "native_source": "macos_lsof_listener_metadata",
                        "source_api": "Process.lsof",
                        "privacy_level": "redacted",
                        "listener_signature_hash": shortDigest(signature),
                        "endpoint_paths_omitted": "true",
                        "logs_omitted": "true",
                    ],
                    payload: ["listener_signature_hash": shortDigest(signature)],
                    privacyTier: "sensitive_metadata"
                )
                health.noteEvent()
            }
        }
        serviceSignatures = current
    }

    private func sampleWorkspaceFiles(emitInitial: Bool) {
        for snapshot in developerWorkspaceSnapshots(workspace: options.workspace, dataDir: options.dataDir) {
            let previous = workspaceSignatures[snapshot.key]
            guard emitInitial || previous != snapshot.signature else {
                continue
            }
            workspaceSignatures[snapshot.key] = snapshot.signature
            guard emitInitial || previous != nil else {
                continue
            }
            spool.append(
                collector: snapshot.collector,
                source: "activity",
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
