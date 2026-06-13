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
                    MetricTile(title: "Listening", value: model.settings.sttProvider.humanizedIdentifier, symbol: "ear")
                    MetricTile(title: "Speaking", value: model.settings.ttsProvider.humanizedIdentifier, symbol: "speaker.wave.2")
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
                        Picker("Listening engine", selection: $model.settings.sttProvider) {
                            Text("System speech").tag("system")
                            Text("Deepgram").tag("deepgram")
                        }
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
                                Task { await model.testVoiceOutput(testPhrase) }
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
                    Section("Main agent model") {
                        Picker("Reasoning mode", selection: $model.settings.planner) {
                            Text("Model").tag("model")
                            Text("Explicit").tag("explicit")
                        }
                        Picker("Provider", selection: $model.settings.modelProvider) {
                            ForEach(model.modelProviderOptions) { provider in
                                Text(provider.label).tag(provider.providerId)
                            }
                        }
                        TextField("Model name", text: $model.settings.modelName)
                        TextField("Provider URL", text: $model.settings.modelBaseURL)
                        SecureField("API key", text: $model.secrets.modelAPIKey)
                        Toggle("Allow protected actions without asking", isOn: $model.settings.approveHighRisk)
                    }
                    Section("Janus interpretation model") {
                        Picker("Provider", selection: $model.settings.janusModelProvider) {
                            Text("Same as main agent").tag("same-as-main")
                            ForEach(model.modelProviderOptions) { provider in
                                Text(provider.label).tag(provider.providerId)
                            }
                        }
                        TextField(
                            "Model name",
                            text: $model.settings.janusModelName,
                            prompt: Text(model.settings.janusModelProvider == "same-as-main" ? model.settings.modelName : model.defaultModelName(for: model.settings.janusModelProvider))
                        )
                        TextField(
                            "Provider URL",
                            text: $model.settings.janusModelBaseURL,
                            prompt: Text(model.settings.janusModelProvider == "same-as-main" ? model.settings.modelBaseURL : model.defaultBaseURL(for: model.settings.janusModelProvider))
                        )
                        SecureField("API key", text: $model.secrets.janusModelAPIKey)
                            .disabled(model.settings.janusModelProvider == "same-as-main")
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
