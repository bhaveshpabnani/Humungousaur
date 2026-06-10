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
        case "openrouter": "OPENROUTER_API_KEY"
        case "nous": "NOUS_API_KEY"
        case "novita": "NOVITA_API_KEY"
        case "lmstudio": "LM_API_KEY"
        case "anthropic": "ANTHROPIC_API_KEY"
        case "alibaba": "DASHSCOPE_API_KEY"
        case "groq": "GROQ_API_KEY"
        case "grok", "xai": "XAI_API_KEY"
        case "gemini": "GOOGLE_API_KEY"
        case "deepseek": "DEEPSEEK_API_KEY"
        case "mistral": "MISTRAL_API_KEY"
        case "cerebras": "CEREBRAS_API_KEY"
        case "ollama": "OLLAMA_API_KEY"
        case "ollama-cloud": "OLLAMA_API_KEY"
        case "local-openai": "LOCAL_LLM_API_KEY"
        case "vercel": "AI_GATEWAY_API_KEY"
        case "litellm": "LITELLM_API_KEY"
        case "nvidia": "NVIDIA_API_KEY"
        case "huggingface": "HF_TOKEN"
        case "zai": "GLM_API_KEY"
        case "kimi-coding": "KIMI_API_KEY"
        case "kimi-coding-cn": "KIMI_CN_API_KEY"
        case "stepfun": "STEPFUN_API_KEY"
        case "minimax": "MINIMAX_API_KEY"
        case "minimax-cn": "MINIMAX_CN_API_KEY"
        case "arcee": "ARCEEAI_API_KEY"
        case "gmi": "GMI_API_KEY"
        case "xiaomi": "XIAOMI_API_KEY"
        case "tencent-tokenhub": "TOKENHUB_API_KEY"
        case "opencode-zen": "OPENCODE_ZEN_API_KEY"
        case "opencode-go": "OPENCODE_GO_API_KEY"
        case "kilocode": "KILOCODE_API_KEY"
        case "azure-openai": "AZURE_OPENAI_API_KEY"
        case "azure-foundry": "AZURE_FOUNDRY_API_KEY"
        case "copilot", "copilot-acp": "GITHUB_TOKEN"
        case "bedrock": "AWS_ACCESS_KEY_ID"
        case "browser-use-cloud": "BROWSER_USE_API_KEY"
        default: "OPENAI_API_KEY"
        }
    }
}
