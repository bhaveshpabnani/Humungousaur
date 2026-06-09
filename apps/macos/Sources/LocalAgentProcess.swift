import Foundation

@MainActor
final class LocalAgentProcess: ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var logLines: [String] = []

    private var process: Process?
    private var stdoutPipe: Pipe?
    private var stderrPipe: Pipe?

    func start(settings: AppSettings, secrets: RuntimeSecrets) throws {
        guard process == nil || process?.isRunning == false else { return }

        let proc = Process()
        let pythonPath = settings.pythonPath.isEmpty ? "python3" : settings.pythonPath
        if pythonPath.contains("/") {
            proc.executableURL = URL(fileURLWithPath: pythonPath)
            proc.arguments = []
        } else {
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            proc.arguments = [pythonPath]
        }
        proc.currentDirectoryURL = URL(fileURLWithPath: settings.workspacePath)
        proc.arguments?.append(contentsOf: [
            "-m", "humungousaur",
            "serve",
            "--workspace", settings.workspacePath,
            "--port", String(settings.port),
            "--planner", settings.planner,
            "--model-provider", settings.modelProvider == "openai" ? "openai-responses" : settings.modelProvider,
            "--model", settings.modelName,
            "--model-api-key-env", modelKeyName(settings.modelProvider)
        ])
        if !settings.modelBaseURL.isEmpty {
            proc.arguments?.append(contentsOf: ["--model-base-url", settings.modelBaseURL])
        }

        var environment = ProcessInfo.processInfo.environment
        addSecret(&environment, name: modelKeyName(settings.modelProvider), value: secrets.modelAPIKey)
        addSecret(&environment, name: "DEEPGRAM_API_KEY", value: secrets.deepgramAPIKey)
        addSecret(&environment, name: "ELEVENLABS_API_KEY", value: secrets.elevenLabsAPIKey)
        addSecret(&environment, name: "ELEVENLABS_VOICE_ID", value: settings.voiceId)
        addSecret(&environment, name: "ELEVENLABS_MODEL_ID", value: settings.elevenLabsModel)
        for channel in settings.channels {
            addSecret(&environment, name: channel.secretName, value: channel.secretValue)
            for item in channel.secretValues {
                addSecret(&environment, name: item.key, value: item.value)
            }
        }
        proc.environment = environment

        let output = Pipe()
        let error = Pipe()
        stdoutPipe = output
        stderrPipe = error
        proc.standardOutput = output
        proc.standardError = error

        output.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in self?.appendLog(text) }
        }
        error.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in self?.appendLog(text) }
        }
        proc.terminationHandler = { [weak self] _ in
            Task { @MainActor in
                self?.isRunning = false
                self?.appendLog("Agent process exited.")
            }
        }

        try proc.run()
        process = proc
        isRunning = true
        appendLog("Started local Humungousaur daemon on port \(settings.port).")
    }

    func stop() {
        guard let process else { return }
        process.terminate()
        self.process = nil
        isRunning = false
        appendLog("Stop requested.")
    }

    private func appendLog(_ text: String) {
        for line in text.components(separatedBy: .newlines).filter({ !$0.trimmingCharacters(in: CharacterSet.whitespacesAndNewlines).isEmpty }) {
            logLines.append("\(Date.now.formatted(date: .omitted, time: .standard))  \(line)")
        }
        if logLines.count > 120 {
            logLines.removeFirst(logLines.count - 120)
        }
    }

    private func addSecret(_ environment: inout [String: String], name: String, value: String) {
        if !name.isEmpty, !value.isEmpty {
            environment[name] = value
        }
    }

    private func modelKeyName(_ provider: String) -> String {
        switch provider {
        case "groq": "GROQ_API_KEY"
        case "grok": "XAI_API_KEY"
        case "ollama": "OLLAMA_API_KEY"
        case "local-openai": "LOCAL_LLM_API_KEY"
        default: "OPENAI_API_KEY"
        }
    }
}
