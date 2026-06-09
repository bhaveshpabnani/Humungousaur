import SwiftUI

struct VoiceView: View {
    @EnvironmentObject private var model: AppViewModel
    @State private var testPhrase = "I am online and ready to help."

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                SectionHeader(eyebrow: "Voice", title: "Voice", subtitle: "Set up listening and spoken replies for hands-free work.")
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    MetricTile(title: "Listening", value: model.secrets.deepgramAPIKey.isEmpty ? "Needs key" : "Ready", symbol: "waveform.badge.mic")
                    MetricTile(title: "Speaking", value: model.secrets.elevenLabsAPIKey.isEmpty ? "System voice" : "ElevenLabs", symbol: "speaker.wave.2")
                    MetricTile(title: "Voice engine", value: model.settings.ttsProvider.humanizedIdentifier, symbol: "slider.horizontal.3")
                }
                Form {
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
                            model.saveSettings()
                            Task { await model.refreshVoice() }
                        }
                        Button("Test Voice") {
                            Task { await model.send(testPhrase, source: "voice_transcript", responseMode: "voice_speak") }
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
                            Text("Groq").tag("groq")
                            Text("Grok").tag("grok")
                            Text("Ollama").tag("ollama")
                            Text("Local OpenAI").tag("local-openai")
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
