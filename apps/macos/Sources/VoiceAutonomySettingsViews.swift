import SwiftUI

struct VoiceView: View {
    @EnvironmentObject private var model: AppViewModel
    @State private var testPhrase = "I am online and ready to help."

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                SectionHeader(eyebrow: "Voice", title: "Voice", subtitle: "Set up listening and spoken replies for hands-free work.")
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    MetricTile(title: "Wake-up", value: model.settings.voiceWakeEnabled ? (model.voiceWakeIsAwake ? "Awake" : "Listening") : "Off", symbol: "waveform.badge.mic")
                    MetricTile(title: "Speaking", value: model.secrets.elevenLabsAPIKey.isEmpty ? "System voice" : "ElevenLabs", symbol: "speaker.wave.2")
                    MetricTile(title: "Voice engine", value: model.settings.ttsProvider.humanizedIdentifier, symbol: "slider.horizontal.3")
                }
                Form {
                    Section("Wake-up") {
                        Toggle(
                            "Listen for wake phrase",
                            isOn: Binding(
                                get: { model.settings.voiceWakeEnabled },
                                set: { enabled in
                                    Task { await model.setVoiceWakeEnabled(enabled) }
                                }
                            )
                        )
                        .toggleStyle(.switch)
                        TextField("Wake phrases", text: $model.settings.voiceWakePhrases)
                        TextField("Stop phrases", text: $model.settings.voiceStopPhrases)
                        Toggle("Keep accepting voice tasks after wake-up", isOn: $model.settings.voiceContinuousAfterWake)
                            .toggleStyle(.switch)
                        Text(model.voiceWakeStatusText)
                            .foregroundStyle(.secondary)
                        if !model.voiceWakeLastTranscript.isEmpty {
                            Text(model.voiceWakeLastTranscript)
                                .font(.callout)
                                .textSelection(.enabled)
                        }
                    }
                    Section("Speech") {
                    Picker("Speaking voice", selection: $model.settings.ttsProvider) {
                        Text("System voice").tag("system")
                        Text("ElevenLabs").tag("elevenlabs")
                    }
                    TextField("Voice ID", text: $model.settings.voiceId)
                    SecureField("Listening API key", text: $model.secrets.deepgramAPIKey)
                    SecureField("Speaking API key", text: $model.secrets.elevenLabsAPIKey)
                    TextField("ElevenLabs model", text: $model.settings.elevenLabsModel)
                    TextField("Test phrase", text: $testPhrase)
                    HStack {
                        Button("Save") {
                            Task { await model.saveVoiceSettings() }
                        }
                        Button("Test Voice") {
                            Task { await model.send(testPhrase, source: "voice_transcript", responseMode: "voice_speak") }
                        }
                    }
                    }
                }
                .formStyle(.grouped)
                .scrollContentBackground(.hidden)
                UserTechnicalDetails(title: "Technical voice status") {
                    JSONTextView(value: model.voiceStatus)
                        .frame(minHeight: 180)
                }
            }
            .padding(28)
        }
    }
}

struct AutonomyView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                SectionHeader(eyebrow: "Automation", title: "Autonomy", subtitle: "Choose how much initiative Humungousaur can take between your messages.")
                HStack(spacing: 12) {
                    Toggle("Allow initiative", isOn: $model.settings.allowInitiative)
                        .toggleStyle(.switch)
                    Stepper("Work steps \(model.settings.maxCycles)", value: $model.settings.maxCycles, in: 1...20)
                    Spacer()
                    Button {
                        Task { await model.runAutonomyCycle() }
                    } label: {
                        Label("Run Once", systemImage: "play.circle.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(DS.accent)
                }
                .glassPanel()
                UserTechnicalDetails(title: "Technical autonomy status") {
                    JSONTextView(value: model.autonomousStatus)
                        .frame(minHeight: 320)
                }
            }
            .padding(28)
        }
    }
}

struct SettingsView: View {
    @EnvironmentObject private var model: AppViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                SectionHeader(eyebrow: "Preferences", title: "Settings", subtitle: "Connection, project folder, model, and private keys.")
                Form {
                    Section("Connection") {
                        TextField("Server address", text: $model.settings.apiBaseURL)
                        TextField("Project folder", text: $model.settings.workspacePath)
                        TextField("Python path", text: $model.settings.pythonPath)
                        Stepper("Local port \(model.settings.port)", value: $model.settings.port, in: 1...65535)
                    }
                    Section("AI model") {
                        Picker("Reasoning mode", selection: $model.settings.planner) {
                            Text("Model").tag("model")
                            Text("Explicit").tag("explicit")
                        }
                        Picker("Provider", selection: $model.settings.modelProvider) {
                            Text("OpenAI").tag("openai")
                            Text("OpenAI Chat").tag("openai-chat")
                            Text("OpenRouter").tag("openrouter")
                            Text("Nous Portal").tag("nous")
                            Text("NovitaAI").tag("novita")
                            Text("LM Studio").tag("lmstudio")
                            Text("Anthropic").tag("anthropic")
                            Text("Qwen Cloud").tag("alibaba")
                            Text("Groq").tag("groq")
                            Text("xAI Grok").tag("xai")
                            Text("Google Gemini").tag("gemini")
                            Text("DeepSeek").tag("deepseek")
                            Text("Mistral").tag("mistral")
                            Text("Cerebras").tag("cerebras")
                            Text("Ollama").tag("ollama")
                            Text("Ollama Cloud").tag("ollama-cloud")
                            Text("Local OpenAI").tag("local-openai")
                            Text("Vercel AI Gateway").tag("vercel")
                            Text("LiteLLM").tag("litellm")
                            Text("NVIDIA NIM").tag("nvidia")
                            Text("Hugging Face").tag("huggingface")
                            Text("Z.AI / GLM").tag("zai")
                            Text("Kimi / Moonshot").tag("kimi-coding")
                            Text("Kimi China").tag("kimi-coding-cn")
                            Text("StepFun").tag("stepfun")
                            Text("MiniMax").tag("minimax")
                            Text("MiniMax China").tag("minimax-cn")
                            Text("Arcee AI").tag("arcee")
                            Text("GMI Cloud").tag("gmi")
                            Text("Xiaomi MiMo").tag("xiaomi")
                            Text("Tencent TokenHub").tag("tencent-tokenhub")
                            Text("OpenCode Zen").tag("opencode-zen")
                            Text("OpenCode Go").tag("opencode-go")
                            Text("Kilo Code").tag("kilocode")
                            Text("Azure OpenAI").tag("azure-openai")
                            Text("Azure Foundry").tag("azure-foundry")
                            Text("GitHub Copilot").tag("copilot")
                            Text("AWS Bedrock").tag("bedrock")
                            Text("Browser Use Cloud").tag("browser-use-cloud")
                        }
                        TextField("Model name", text: $model.settings.modelName)
                        TextField("Provider URL", text: $model.settings.modelBaseURL)
                        SecureField("API key", text: $model.secrets.modelAPIKey)
                        Toggle("Allow protected actions without asking", isOn: $model.settings.approveHighRisk)
                    }
                    Section("App updates") {
                        Text(model.updateStatusText)
                        HStack {
                            Button("Check for Updates") {
                                Task { await model.checkForUpdates() }
                            }
                            if let downloadURL = model.updateInfo?.downloadURL {
                                Link("Open Download", destination: downloadURL)
                            }
                        }
                    }
                    Section {
                        HStack {
                            Button("Save Settings") {
                                model.saveSettings()
                            }
                            Button(model.agentProcess.isRunning ? "Stop Agent" : "Start Agent") {
                                Task { await model.toggleAgentProcess() }
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(DS.accent)
                        }
                    }
                }
                .formStyle(.grouped)
                .scrollContentBackground(.hidden)
            }
            .padding(28)
        }
    }
}
