import Foundation

struct AppSettings: Codable, Equatable {
    var apiBaseURL = "http://127.0.0.1:8765"
    var workspacePath = defaultWorkspacePath()
    var pythonPath = defaultPythonPath()
    var port = 8765
    var planner = "model"
    var modelProvider = "openai"
    var modelName = "gpt-5-mini"
    var modelBaseURL = ""
    var janusModelProvider = "same-as-main"
    var janusModelName = ""
    var janusModelBaseURL = ""
    var ttsProvider = "system"
    var voiceId = ""
    var elevenLabsModel = ""
    var voiceWakeEnabled = false
    var voiceWakePhrases = "hey humungousaur"
    var voiceStopPhrases = "stop humungousaur"
    var voiceContinuousAfterWake = true
    var approveHighRisk = false
    var allowInitiative = false
    var maxCycles = 1
    var channels: [ChannelSetup] = []

    static func defaultWorkspacePath() -> String {
        var directory = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        while directory.path != "/" {
            if FileManager.default.fileExists(atPath: directory.appending(path: "pyproject.toml").path) {
                return directory.path
            }
            directory.deleteLastPathComponent()
        }
        let fileManager = FileManager.default
        let home = fileManager.homeDirectoryForCurrentUser
        var candidates: [URL] = []
        if let configured = ProcessInfo.processInfo.environment["HUMUNGOUSAUR_WORKSPACE"], !configured.isEmpty {
            candidates.append(URL(fileURLWithPath: configured).standardizedFileURL)
        }
        candidates.append(contentsOf: [
            home.appendingPathComponent("Documents").appendingPathComponent("Humungousaur"),
            home.appendingPathComponent("Developer").appendingPathComponent("Humungousaur"),
            home.appendingPathComponent("Projects").appendingPathComponent("Humungousaur"),
        ])
        for candidate in candidates {
            if fileManager.fileExists(atPath: candidate.appending(path: "pyproject.toml").path) {
                return candidate.path
            }
        }
        if installedRuntimePythonPath() != nil {
            return home.path
        }
        return home.path
    }

    static func defaultPythonPath() -> String {
        installedRuntimePythonPath() ?? "python3"
    }

    private static func installedRuntimePythonPath() -> String? {
        let candidates = [
            "/Library/Application Support/Humungousaur/runtime/.venv/bin/python",
            FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library")
                .appendingPathComponent("Application Support")
                .appendingPathComponent("Humungousaur")
                .appendingPathComponent("runtime")
                .appendingPathComponent(".venv")
                .appendingPathComponent("bin")
                .appendingPathComponent("python")
                .path,
        ]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
    }
}

final class SettingsStore {
    private let key = "HumungousaurMac.settings"
    private let defaults = UserDefaults.standard

    func load() -> AppSettings {
        guard let data = defaults.data(forKey: key) else {
            return AppSettings()
        }
        var settings = (try? JSONDecoder().decode(AppSettings.self, from: data)) ?? AppSettings()
        var shouldSave = false
        if settings.workspacePath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || settings.workspacePath == "/" {
            settings.workspacePath = AppSettings.defaultWorkspacePath()
            shouldSave = true
        }
        if settings.pythonPath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || settings.pythonPath == "python3" {
            let defaultPython = AppSettings.defaultPythonPath()
            if defaultPython != settings.pythonPath {
                settings.pythonPath = defaultPython
                shouldSave = true
            }
        }
        let wakePhrases = settings.voiceWakePhrases
            .split(separator: ",")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
            .filter { !$0.isEmpty }
        if settings.voiceWakePhrases.localizedCaseInsensitiveContains("jarvis")
            || wakePhrases == ["humungousaur", "hey humungousaur"] {
            settings.voiceWakePhrases = "hey humungousaur"
            shouldSave = true
        }
        if settings.voiceStopPhrases.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || settings.voiceStopPhrases.localizedCaseInsensitiveContains("jarvis") {
            settings.voiceStopPhrases = "stop humungousaur"
            shouldSave = true
        }
        if settings.janusModelProvider.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            settings.janusModelProvider = "same-as-main"
            shouldSave = true
        }
        if shouldSave {
            save(settings)
        }
        return settings
    }

    func save(_ settings: AppSettings) {
        if let data = try? JSONEncoder().encode(settings) {
            defaults.set(data, forKey: key)
            defaults.synchronize()
        }
    }
}
