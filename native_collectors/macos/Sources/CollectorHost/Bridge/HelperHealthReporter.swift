import Foundation

final class HelperHealthReporter {
    private let apiURL: URL?
    private let spool: CollectorSpool
    private var lastEventAt = ""

    init(apiURL: URL?, spool: CollectorSpool) {
        self.apiURL = apiURL
        self.spool = spool
    }

    func noteEvent() {
        lastEventAt = isoNow()
    }

    func report(status: String, permissionState: String, message: String = "", metadata: [String: String] = [:]) {
        let healthMetadata = metadata.merging([
            "collector_count": String(supportedCollectors.count),
            "collectors": supportedCollectors.joined(separator: ","),
        ], uniquingKeysWith: { current, _ in current })

        for collector in supportedCollectors {
            let collectorNeedsAccessibility = [
                "text_input_surface_activity",
                "accessibility_context",
                "selection_activity",
            ].contains(collector)
            let collectorStatus = collectorNeedsAccessibility && permissionState != "accessibility_granted"
                ? "permission_denied"
                : status
            let collectorMessage = collectorStatus == "permission_denied"
                ? "Accessibility permission is required for focused text-entry and UI metadata."
                : message
            postHealth(
                collector: collector,
                status: collectorStatus,
                permissionState: permissionState,
                message: collectorMessage,
                metadata: healthMetadata
            )
        }

        spool.append(
            collector: "agent_runtime",
            source: "system",
            stimulusType: "autonomous_cycle_started",
            text: "macOS core OS context helper health: \(status).",
            metadata: healthMetadata.merging([
                "helper_health_status": status,
                "permission_state": permissionState,
                "message": message,
            ], uniquingKeysWith: { current, _ in current }),
            payload: [:]
        )
    }

    private func postHealth(
        collector: String,
        status: String,
        permissionState: String,
        message: String,
        metadata: [String: String]
    ) {
        guard let apiURL else {
            return
        }
        let endpoint = apiURL.appendingPathComponent("collectors/helper-health")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 2
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "helper_id": "\(helperID)-\(collector)",
            "collector": collector,
            "platform": "Darwin",
            "status": status,
            "pid": Int(ProcessInfo.processInfo.processIdentifier),
            "version": helperVersion,
            "permission_state": permissionState,
            "last_event_at": lastEventAt,
            "restart_count": 0,
            "message": message,
            "metadata": metadata,
        ])

        let semaphore = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: request) { _, _, error in
            if let error {
                fputs("HumungousaurMacCollectorHost helper health post failed for \(collector): \(error)\n", stderr)
            }
            semaphore.signal()
        }.resume()
        _ = semaphore.wait(timeout: .now() + 2)
    }
}
