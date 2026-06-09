import Foundation

struct AppSettings: Codable, Equatable {
    var apiBaseURL = "http://127.0.0.1:8765"
    var workspacePath = defaultWorkspacePath()
    var pythonPath = "python3"
    var port = 8765
    var planner = "model"
    var modelProvider = "openai"
    var modelName = "gpt-5-mini"
    var modelBaseURL = ""
    var ttsProvider = "system"
    var voiceId = ""
    var elevenLabsModel = ""
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
        return FileManager.default.currentDirectoryPath
    }
}

final class SettingsStore {
    private let key = "HumungousaurMac.settings"
    private let defaults = UserDefaults.standard

    func load() -> AppSettings {
        guard let data = defaults.data(forKey: key) else {
            return AppSettings()
        }
        return (try? JSONDecoder().decode(AppSettings.self, from: data)) ?? AppSettings()
    }

    func save(_ settings: AppSettings) {
        if let data = try? JSONEncoder().encode(settings) {
            defaults.set(data, forKey: key)
        }
    }
}
