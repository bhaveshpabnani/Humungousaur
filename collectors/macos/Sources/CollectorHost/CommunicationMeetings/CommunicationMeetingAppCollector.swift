import AppKit
import Foundation

final class CommunicationMeetingAppCollector {
    private let spool: CollectorSpool
    private let health: HelperHealthReporter
    private var activeMeetingSurfaces: Set<String> = []
    private var communicationProcesses: Set<String> = []
    private var foregroundSignatures: [String: String] = [:]
    private var recordingSignatures: Set<String> = []
    private var sharingSignatures: Set<String> = []

    init(spool: CollectorSpool, health: HelperHealthReporter) {
        self.spool = spool
        self.health = health
    }

    func installObservers() -> [NativeObservation] {
        let center = NSWorkspace.shared.notificationCenter
        let launch = center.addObserver(forName: NSWorkspace.didLaunchApplicationNotification, object: nil, queue: .main) { [weak self] _ in
            self?.sample(emitInitial: false)
        }
        let terminate = center.addObserver(forName: NSWorkspace.didTerminateApplicationNotification, object: nil, queue: .main) { [weak self] _ in
            self?.sample(emitInitial: false)
        }
        let activate = center.addObserver(forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: .main) { [weak self] _ in
            self?.sample(emitInitial: false)
        }
        return [(center, launch), (center, terminate), (center, activate)]
    }

    func sample(emitInitial: Bool) {
        sampleMeetingSurfaces(emitInitial: emitInitial)
        sampleCommunicationProcesses(emitInitial: emitInitial)
        sampleForegroundCommunicationSurface(emitInitial: emitInitial)
    }

    private func sampleMeetingSurfaces(emitInitial: Bool) {
        let surfaces = communicationMeetingSurfaces()
        let current = Set(surfaces.map(\.signature))
        let sharing = Set(surfaces.filter(\.isSharingSurface).map(\.signature))
        let recording = Set(surfaces.filter(\.isRecordingSurface).map(\.signature))

        for signature in current.subtracting(activeMeetingSurfaces).sorted().prefix(12) {
            guard let surface = surfaces.first(where: { $0.signature == signature }) else {
                continue
            }
            emitMeeting(surface, collector: "meeting_app_activity", source: "activity", stimulusType: "meeting_joined", text: "Meeting app surface metadata appeared.")
            emitMeeting(surface, collector: "meeting_audio", source: "audio_transcript", stimulusType: "call_started", text: "Meeting call metadata started.")
        }
        if !emitInitial {
            for signature in activeMeetingSurfaces.subtracting(current).sorted().prefix(12) {
                emitEnded(signature: signature, collector: "meeting_app_activity", source: "activity", stimulusType: "meeting_left", text: "Meeting app surface metadata disappeared.")
                emitEnded(signature: signature, collector: "meeting_audio", source: "audio_transcript", stimulusType: "call_ended", text: "Meeting call metadata ended.")
            }
        }

        for signature in sharing.subtracting(sharingSignatures).sorted().prefix(8) {
            guard let surface = surfaces.first(where: { $0.signature == signature }) else {
                continue
            }
            emitMeeting(surface, collector: "meeting_presentation_activity", source: "activity", stimulusType: "screen_share_started", text: "Meeting screen-share surface metadata appeared.")
        }
        if !emitInitial {
            for signature in sharingSignatures.subtracting(sharing).sorted().prefix(8) {
                emitEnded(signature: signature, collector: "meeting_presentation_activity", source: "activity", stimulusType: "screen_share_stopped", text: "Meeting screen-share surface metadata disappeared.")
            }
        }

        for signature in recording.subtracting(recordingSignatures).sorted().prefix(8) {
            guard let surface = surfaces.first(where: { $0.signature == signature }) else {
                continue
            }
            emitMeeting(surface, collector: "meeting_app_activity", source: "activity", stimulusType: "meeting_recording_started", text: "Meeting recording surface metadata appeared.")
        }
        if !emitInitial {
            for signature in recordingSignatures.subtracting(recording).sorted().prefix(8) {
                emitEnded(signature: signature, collector: "meeting_app_activity", source: "activity", stimulusType: "meeting_recording_stopped", text: "Meeting recording surface metadata disappeared.")
                emitEnded(signature: signature, collector: "meeting_artifact_activity", source: "activity", stimulusType: "meeting_recording_available", text: "Meeting recording metadata changed.")
            }
        }

        activeMeetingSurfaces = current
        sharingSignatures = sharing
        recordingSignatures = recording
    }

    private func sampleCommunicationProcesses(emitInitial: Bool) {
        let snapshots = communicationAppProcessSnapshots()
        let current = Set(snapshots.map(\.signature))
        for signature in current.subtracting(communicationProcesses).sorted().prefix(16) {
            guard let snapshot = snapshots.first(where: { $0.signature == signature }) else {
                continue
            }
            emitCommunicationProcess(snapshot, stimulusType: "presence_changed", text: "Communication app process metadata appeared.")
        }
        if !emitInitial {
            for signature in communicationProcesses.subtracting(current).sorted().prefix(16) {
                emitCommunicationEnded(signature: signature)
            }
        }
        communicationProcesses = current
    }

    private func sampleForegroundCommunicationSurface(emitInitial: Bool) {
        guard let snapshot = frontmostCommunicationAppSnapshot() else {
            return
        }
        let signature = snapshot.signature
        for route in communicationForegroundRoutes(snapshot) {
            let previous = foregroundSignatures[route.collector]
            guard emitInitial || previous != signature else {
                continue
            }
            foregroundSignatures[route.collector] = signature
            spool.append(
                collector: route.collector,
                source: route.source,
                stimulusType: route.stimulusType,
                text: route.text,
                metadata: snapshot.metadata,
                payload: snapshot.payload,
                privacyTier: route.privacyTier
            )
            health.noteEvent()
        }
    }

    private func emitMeeting(_ surface: CommunicationMeetingSurface, collector: String, source: String, stimulusType: String, text: String) {
        spool.append(
            collector: collector,
            source: source,
            stimulusType: stimulusType,
            text: text,
            metadata: surface.metadata,
            payload: surface.payload,
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitEnded(signature: String, collector: String, source: String, stimulusType: String, text: String) {
        let signatureHash = shortDigest(signature)
        spool.append(
            collector: collector,
            source: source,
            stimulusType: stimulusType,
            text: text,
            metadata: communicationRedactedMetadata(sourceAPI: "NSWorkspace+CGWindowList").merging([
                "surface_signature_hash": signatureHash,
            ], uniquingKeysWith: { current, _ in current }),
            payload: ["surface_signature_hash": signatureHash],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitCommunicationProcess(_ snapshot: CommunicationProcessSnapshot, stimulusType: String, text: String) {
        spool.append(
            collector: "chat_presence_activity",
            source: "channel_message",
            stimulusType: stimulusType,
            text: text,
            metadata: snapshot.metadata,
            payload: snapshot.payload,
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }

    private func emitCommunicationEnded(signature: String) {
        let signatureHash = shortDigest(signature)
        spool.append(
            collector: "chat_presence_activity",
            source: "channel_message",
            stimulusType: "presence_changed",
            text: "Communication app process metadata disappeared.",
            metadata: communicationRedactedMetadata(sourceAPI: "NSWorkspace.runningApplications").merging([
                "process_signature_hash": signatureHash,
            ], uniquingKeysWith: { current, _ in current }),
            payload: ["process_signature_hash": signatureHash],
            privacyTier: "sensitive_metadata"
        )
        health.noteEvent()
    }
}
