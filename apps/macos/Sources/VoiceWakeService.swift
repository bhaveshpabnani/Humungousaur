import AppKit
import AVFoundation
import Foundation
import Speech

enum VoiceWakeServiceError: LocalizedError {
    case microphoneDenied
    case recognizerUnavailable
    case recordingUnavailable
    case recordingFailed
    case speechRecognitionDenied
    case speechRecognitionFailed(String)

    var errorDescription: String? {
        switch self {
        case .microphoneDenied:
            "Microphone permission is required for voice wake-up."
        case .recognizerUnavailable:
            "macOS speech command recognition is not available."
        case .recordingUnavailable:
            "macOS audio recording is not available."
        case .recordingFailed:
            "Voice follow-up recording failed."
        case .speechRecognitionDenied:
            "Speech recognition permission is required to understand your spoken task."
        case .speechRecognitionFailed(let message):
            "macOS speech recognition failed: \(message)"
        }
    }
}

struct VoiceRecognitionUpdate {
    var transcript: String
    var isFinal: Bool
}

struct VoiceActivityConfig {
    var speechThreshold: Float = 0.010
    var silenceDuration: TimeInterval = 1.4
    var speechStartTimeout: TimeInterval = 12.0
    var maxDuration: TimeInterval = 45.0
    var minSpeechDuration: TimeInterval = 0.25
    var dipTolerance: TimeInterval = 0.30
    var finalizationDelay: TimeInterval = 0.85
}

@MainActor
final class VoiceWakeService: NSObject, NSSpeechRecognizerDelegate {
    var onUpdate: ((VoiceRecognitionUpdate) -> Void)?
    var onFailure: ((Error) -> Void)?

    private var recognizer: NSSpeechRecognizer?
    private var taskRecorder: AVAudioRecorder?
    private var liveDictationSession: LiveDictationSession?
    private var isRunning = false

    func start(commands: [String]) async throws {
        let microphoneGranted = await Self.requestMicrophoneAccess()
        guard microphoneGranted else {
            throw VoiceWakeServiceError.microphoneDenied
        }
        let speechGranted = await Self.requestSpeechRecognitionAccess()
        guard speechGranted else {
            throw VoiceWakeServiceError.speechRecognitionDenied
        }
        let cleanCommands = commands
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        guard !cleanCommands.isEmpty else {
            throw VoiceWakeServiceError.recognizerUnavailable
        }

        stop()
        guard let recognizer = NSSpeechRecognizer() else {
            throw VoiceWakeServiceError.recognizerUnavailable
        }
        recognizer.commands = cleanCommands
        recognizer.delegate = self
        recognizer.blocksOtherRecognizers = false
        recognizer.listensInForegroundOnly = false
        recognizer.startListening()
        self.recognizer = recognizer
        isRunning = true
    }

    func stop() {
        stopWakeRecognition()
        taskRecorder?.stop()
        taskRecorder = nil
        liveDictationSession?.cancel()
        liveDictationSession = nil
    }

    func stopWakeRecognition() {
        isRunning = false
        recognizer?.stopListening()
        recognizer?.delegate = nil
        recognizer = nil
    }

    func recordTaskAudio(
        activity: VoiceActivityConfig = VoiceActivityConfig(),
        outputDirectory: URL? = nil
    ) async throws -> URL {
        let microphoneGranted = await Self.requestMicrophoneAccess()
        guard microphoneGranted else {
            throw VoiceWakeServiceError.microphoneDenied
        }

        let directory = outputDirectory ?? FileManager.default.temporaryDirectory
            .appendingPathComponent("humungousaur-voice-captures", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let audioURL = directory.appendingPathComponent("voice-task-\(UUID().uuidString).m4a")
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 44_100,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
        ]
        let recorder = try AVAudioRecorder(url: audioURL, settings: settings)
        recorder.isMeteringEnabled = true
        recorder.prepareToRecord()
        guard recorder.record() else {
            throw VoiceWakeServiceError.recordingUnavailable
        }
        taskRecorder = recorder
        try await waitForRecordedVoiceActivity(recorder, activity: activity)
        recorder.stop()
        taskRecorder = nil
        let attributes = try FileManager.default.attributesOfItem(atPath: audioURL.path)
        let fileSize = (attributes[.size] as? NSNumber)?.intValue ?? 0
        guard fileSize > 0 else {
            throw VoiceWakeServiceError.recordingFailed
        }
        return audioURL
    }

    private func waitForRecordedVoiceActivity(
        _ recorder: AVAudioRecorder,
        activity: VoiceActivityConfig
    ) async throws {
        let startedAt = ProcessInfo.processInfo.systemUptime
        var speechStart = 0.0
        var hasSpoken = false
        var dipStart = 0.0
        var silenceStart = 0.0
        var resumeStart = 0.0
        var resumeDipStart = 0.0

        while !Task.isCancelled {
            try await Task.sleep(nanoseconds: 50_000_000)
            recorder.updateMeters()
            let rms = Self.rms(fromAveragePower: recorder.averagePower(forChannel: 0))
            let now = ProcessInfo.processInfo.systemUptime
            let elapsed = now - startedAt

            if rms > activity.speechThreshold {
                dipStart = 0.0
                if speechStart == 0.0 {
                    speechStart = now
                } else if !hasSpoken, now - speechStart >= activity.minSpeechDuration {
                    hasSpoken = true
                }

                if !hasSpoken {
                    silenceStart = 0.0
                } else {
                    resumeDipStart = 0.0
                    if resumeStart == 0.0 {
                        resumeStart = now
                    } else if now - resumeStart >= activity.minSpeechDuration {
                        silenceStart = 0.0
                        resumeStart = 0.0
                    }
                }
            } else if hasSpoken {
                if resumeStart > 0 {
                    if resumeDipStart == 0.0 {
                        resumeDipStart = now
                    } else if now - resumeDipStart >= activity.dipTolerance {
                        resumeStart = 0.0
                        resumeDipStart = 0.0
                    }
                }
            } else if speechStart > 0 {
                if dipStart == 0.0 {
                    dipStart = now
                } else if now - dipStart >= activity.dipTolerance {
                    speechStart = 0.0
                    dipStart = 0.0
                }
            }

            if hasSpoken, rms <= activity.speechThreshold {
                if silenceStart == 0.0 {
                    silenceStart = now
                } else if now - silenceStart >= activity.silenceDuration {
                    return
                }
            } else if !hasSpoken, elapsed >= activity.speechStartTimeout {
                throw VoiceWakeServiceError.speechRecognitionFailed("No speech was detected.")
            }
            if elapsed >= activity.maxDuration {
                return
            }
        }
        throw CancellationError()
    }

    func transcribeRecordedAudio(_ audioURL: URL) async throws -> String {
        let speechGranted = await Self.requestSpeechRecognitionAccess()
        guard speechGranted else {
            throw VoiceWakeServiceError.speechRecognitionDenied
        }
        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en_US")), recognizer.isAvailable else {
            throw VoiceWakeServiceError.speechRecognitionFailed("Recognizer is not available.")
        }
        let request = SFSpeechURLRecognitionRequest(url: audioURL)
        request.shouldReportPartialResults = false
        if #available(macOS 13.0, *) {
            request.addsPunctuation = true
        }
        return try await withCheckedThrowingContinuation { continuation in
            var didResume = false
            let task = recognizer.recognitionTask(with: request) { result, error in
                if let result, result.isFinal {
                    let transcript = result.bestTranscription.formattedString.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !didResume {
                        didResume = true
                        continuation.resume(returning: transcript)
                    }
                    return
                }
                if let error {
                    if !didResume {
                        didResume = true
                        continuation.resume(throwing: VoiceWakeServiceError.speechRecognitionFailed(error.localizedDescription))
                    }
                    return
                }
            }
            Task {
                try? await Task.sleep(nanoseconds: 15_000_000_000)
                if !didResume {
                    didResume = true
                    task.cancel()
                    continuation.resume(throwing: VoiceWakeServiceError.speechRecognitionFailed("Timed out waiting for a transcript."))
                }
            }
        }
    }

    func transcribeLiveAudio(
        activity: VoiceActivityConfig = VoiceActivityConfig(),
        onPartial: @escaping @MainActor @Sendable (String) -> Void
    ) async throws -> String {
        let microphoneGranted = await Self.requestMicrophoneAccess()
        guard microphoneGranted else {
            throw VoiceWakeServiceError.microphoneDenied
        }
        let speechGranted = await Self.requestSpeechRecognitionAccess()
        guard speechGranted else {
            throw VoiceWakeServiceError.speechRecognitionDenied
        }
        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en_US")), recognizer.isAvailable else {
            throw VoiceWakeServiceError.speechRecognitionFailed("Recognizer is not available.")
        }

        let session = LiveDictationSession(recognizer: recognizer)
        let partialHandler = MainActorTranscriptHandler(onPartial: onPartial)
        liveDictationSession = session
        defer {
            if liveDictationSession === session {
                liveDictationSession = nil
            }
        }
        return try await session.transcribe(activity: activity, partialHandler: partialHandler)
    }

    nonisolated private static func requestMicrophoneAccess() async -> Bool {
        await withCheckedContinuation { continuation in
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                continuation.resume(returning: granted)
            }
        }
    }

    nonisolated private static func requestSpeechRecognitionAccess() async -> Bool {
        await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
    }

    nonisolated private static func rms(fromAveragePower averagePower: Float) -> Float {
        guard averagePower.isFinite else { return 0 }
        return pow(10.0, averagePower / 20.0)
    }

    nonisolated func speechRecognizer(_ sender: NSSpeechRecognizer, didRecognizeCommand command: String) {
        Task { @MainActor [weak self] in
            guard let self, self.isRunning else { return }
            self.onUpdate?(VoiceRecognitionUpdate(transcript: command, isFinal: true))
        }
    }
}

private final class MainActorTranscriptHandler: @unchecked Sendable {
    private let onPartial: @MainActor @Sendable (String) -> Void

    init(onPartial: @escaping @MainActor @Sendable (String) -> Void) {
        self.onPartial = onPartial
    }

    func emit(_ transcript: String) {
        Task { @MainActor in
            onPartial(transcript)
        }
    }
}

private final class LiveDictationSession: @unchecked Sendable {
    private let recognizer: SFSpeechRecognizer
    private let lock = NSLock()
    private var audioEngine: AVAudioEngine?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var continuation: CheckedContinuation<String, Error>?
    private var finished = false
    private var inputEnded = false
    private var bestTranscript = ""
    private var startedAt = ProcessInfo.processInfo.systemUptime
    private var speechStart = 0.0
    private var hasSpoken = false
    private var dipStart = 0.0
    private var silenceStart = 0.0
    private var resumeStart = 0.0
    private var resumeDipStart = 0.0

    init(recognizer: SFSpeechRecognizer) {
        self.recognizer = recognizer
    }

    func transcribe(activity: VoiceActivityConfig, partialHandler: MainActorTranscriptHandler) async throws -> String {
        let engine = AVAudioEngine()
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        if #available(macOS 13.0, *) {
            request.addsPunctuation = true
        }
        audioEngine = engine
        self.request = request

        return try await withCheckedThrowingContinuation { continuation in
            lock.lock()
            self.continuation = continuation
            startedAt = ProcessInfo.processInfo.systemUptime
            lock.unlock()
            recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
                guard let self else { return }
                if let result {
                    let transcript = result.bestTranscription.formattedString
                    self.lock.lock()
                    self.bestTranscript = transcript
                    self.lock.unlock()
                    let trimmed = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !trimmed.isEmpty {
                        partialHandler.emit(trimmed)
                    }
                    if result.isFinal {
                        self.finish()
                    }
                }
                if let error {
                    self.finish(error: error)
                }
            }

            let inputNode = engine.inputNode
            let format = inputNode.outputFormat(forBus: 0)
            inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
                request.append(buffer)
                self?.observeVoiceActivity(buffer, activity: activity)
            }
            engine.prepare()
            do {
                try engine.start()
            } catch {
                finish(error: error)
                return
            }
        }
    }

    func cancel() {
        lock.lock()
        guard !finished else {
            lock.unlock()
            return
        }
        finished = true
        let continuation = continuation
        self.continuation = nil
        lock.unlock()
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        recognitionTask?.cancel()
        continuation?.resume(throwing: CancellationError())
    }

    private func observeVoiceActivity(_ buffer: AVAudioPCMBuffer, activity: VoiceActivityConfig) {
        let rms = Self.rms(buffer)
        let now = ProcessInfo.processInfo.systemUptime
        var shouldEndForSilence = false
        var shouldEndForNoSpeech = false
        var shouldEndForMaxDuration = false

        lock.lock()
        guard !finished, !inputEnded else {
            lock.unlock()
            return
        }
        let elapsed = now - startedAt
        if rms > activity.speechThreshold {
            dipStart = 0.0
            if speechStart == 0.0 {
                speechStart = now
            } else if !hasSpoken, now - speechStart >= activity.minSpeechDuration {
                hasSpoken = true
            }

            if !hasSpoken {
                silenceStart = 0.0
            } else {
                resumeDipStart = 0.0
                if resumeStart == 0.0 {
                    resumeStart = now
                } else if now - resumeStart >= activity.minSpeechDuration {
                    silenceStart = 0.0
                    resumeStart = 0.0
                }
            }
        } else if hasSpoken {
            if resumeStart > 0 {
                if resumeDipStart == 0.0 {
                    resumeDipStart = now
                } else if now - resumeDipStart >= activity.dipTolerance {
                    resumeStart = 0.0
                    resumeDipStart = 0.0
                }
            }
        } else if speechStart > 0 {
            if dipStart == 0.0 {
                dipStart = now
            } else if now - dipStart >= activity.dipTolerance {
                speechStart = 0.0
                dipStart = 0.0
            }
        }

        if hasSpoken, rms <= activity.speechThreshold {
            if silenceStart == 0.0 {
                silenceStart = now
            } else if now - silenceStart >= activity.silenceDuration {
                shouldEndForSilence = true
            }
        } else if !hasSpoken, elapsed >= activity.speechStartTimeout {
            shouldEndForNoSpeech = true
        }
        if elapsed >= activity.maxDuration {
            shouldEndForMaxDuration = true
        }
        lock.unlock()

        if shouldEndForNoSpeech {
            Task {
                self.finish(error: VoiceWakeServiceError.speechRecognitionFailed("No speech was detected."))
            }
        } else if shouldEndForSilence || shouldEndForMaxDuration {
            Task {
                self.endInputAndFinalize(after: activity.finalizationDelay)
            }
        }
    }

    private func endInputAndFinalize(after delay: TimeInterval) {
        lock.lock()
        guard !finished, !inputEnded else {
            lock.unlock()
            return
        }
        inputEnded = true
        lock.unlock()

        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        Task {
            try? await Task.sleep(nanoseconds: UInt64(max(0.1, delay) * 1_000_000_000))
            self.finish()
        }
    }

    private func finish(error: Error? = nil) {
        lock.lock()
        guard !finished else {
            lock.unlock()
            return
        }
        finished = true
        let transcript = bestTranscript.trimmingCharacters(in: .whitespacesAndNewlines)
        let continuation = continuation
        self.continuation = nil
        lock.unlock()

        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        recognitionTask?.cancel()

        guard let continuation else { return }
        if let error, transcript.isEmpty {
            continuation.resume(throwing: error)
        } else if transcript.isEmpty {
            continuation.resume(throwing: VoiceWakeServiceError.speechRecognitionFailed("No speech was recognized."))
        } else {
            continuation.resume(returning: transcript)
        }
    }

    private static func rms(_ buffer: AVAudioPCMBuffer) -> Float {
        guard let channelData = buffer.floatChannelData else { return 0 }
        let frameLength = Int(buffer.frameLength)
        let channelCount = Int(buffer.format.channelCount)
        guard frameLength > 0, channelCount > 0 else { return 0 }
        var sum: Float = 0
        var sampleCount = 0
        for channel in 0..<channelCount {
            let samples = channelData[channel]
            for frame in 0..<frameLength {
                let sample = samples[frame]
                sum += sample * sample
            }
            sampleCount += frameLength
        }
        guard sampleCount > 0 else { return 0 }
        return sqrt(sum / Float(sampleCount))
    }

    private static func rms(fromAveragePower averagePower: Float) -> Float {
        guard averagePower.isFinite else { return 0 }
        return pow(10.0, averagePower / 20.0)
    }
}
