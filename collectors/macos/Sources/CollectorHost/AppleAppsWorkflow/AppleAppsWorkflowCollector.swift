import AppKit
import Foundation

final class AppleAppsWorkflowCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var foregroundSignatures: [String: String] = [:]
    private var stateSignatures: [String: String] = [:]

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func sample(emitInitial: Bool) {
        sampleForegroundAppleApp(emitInitial: emitInitial)
        sampleStateSnapshots(emitInitial: emitInitial)
    }

    private func sampleForegroundAppleApp(emitInitial: Bool) {
        guard let app = NSWorkspace.shared.frontmostApplication else {
            return
        }
        let routes = appleAppForegroundRoutes(app)
        guard !routes.isEmpty else {
            return
        }
        let metadata = appleAppForegroundMetadata(app: app)
        let signature = [
            app.bundleIdentifier ?? "",
            metadata["window_id"] ?? "",
            metadata["window_title_hash"] ?? "",
        ].joined(separator: "|")

        for route in routes {
            let routeSignature = "\(route.collector)|\(route.stimulusType)|\(signature)"
            guard emitInitial || foregroundSignatures[route.key] != routeSignature else {
                continue
            }
            foregroundSignatures[route.key] = routeSignature
            spool.append(
                collector: route.collector,
                source: route.source,
                stimulusType: route.stimulusType,
                text: route.text,
                metadata: metadata.merging(route.metadata, uniquingKeysWith: { current, _ in current }),
                payload: [
                    "foreground_signature_hash": shortDigest(routeSignature),
                    "apple_app_family": route.appFamily,
                ],
                privacyTier: route.privacyTier
            )
            health.noteEvent()
        }
    }

    private func sampleStateSnapshots(emitInitial: Bool) {
        for snapshot in appleAppStateSnapshots() {
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
