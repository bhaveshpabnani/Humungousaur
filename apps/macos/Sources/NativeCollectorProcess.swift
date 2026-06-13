import Foundation

@MainActor
final class NativeCollectorProcess: ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var logLines: [String] = []

    private var hostProcess: Process?
    private var loopProcess: Process?
    private var stdoutPipe: Pipe?
    private var stderrPipe: Pipe?
    private var loopStdoutPipe: Pipe?
    private var loopStderrPipe: Pipe?

    func start(settings: AppSettings) throws {
        guard hostProcess == nil || hostProcess?.isRunning == false || loopProcess == nil || loopProcess?.isRunning == false else { return }

        let workspaceURL = URL(fileURLWithPath: settings.workspacePath).standardizedFileURL
        let dataDir = workspaceURL.appendingPathComponent("artifacts", isDirectory: true)
        try FileManager.default.createDirectory(at: dataDir, withIntermediateDirectories: true)

        if hostProcess == nil || hostProcess?.isRunning == false {
            if let launch = Self.launchConfiguration(workspaceURL: workspaceURL) {
                try startHost(launch: launch, workspaceURL: workspaceURL, dataDir: dataDir, apiURL: settings.apiBaseURL)
            } else {
                appendLog("Native collector host is unavailable for workspace \(workspaceURL.path).")
            }
        }
        if loopProcess == nil || loopProcess?.isRunning == false {
            try startLoop(settings: settings, workspaceURL: workspaceURL, dataDir: dataDir)
        }
        isRunning = hostProcess?.isRunning == true || loopProcess?.isRunning == true
    }

    func stop() {
        hostProcess?.terminate()
        loopProcess?.terminate()
        hostProcess = nil
        loopProcess = nil
        isRunning = false
        appendLog("Native collector stop requested.")
    }

    private func startHost(
        launch: (executableURL: URL, arguments: [String]),
        workspaceURL: URL,
        dataDir: URL,
        apiURL: String
    ) throws {
        let proc = Process()
        proc.executableURL = launch.executableURL
        proc.arguments = launch.arguments + [
            "--workspace", workspaceURL.path,
            "--data-dir", dataDir.path,
            "--watch", workspaceURL.path,
            "--api-url", apiURL,
        ]
        proc.currentDirectoryURL = workspaceURL

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
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
                self?.isRunning = self?.loopProcess?.isRunning == true
                self?.appendLog("Native collector host exited.")
            }
        }

        try proc.run()
        hostProcess = proc
        appendLog("Started native collector host.")
    }

    private func startLoop(settings: AppSettings, workspaceURL: URL, dataDir: URL) throws {
        let proc = Process()
        let pythonPath = settings.pythonPath.isEmpty ? "python3" : settings.pythonPath
        if pythonPath.contains("/") {
            proc.executableURL = URL(fileURLWithPath: pythonPath)
            proc.arguments = []
        } else {
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            proc.arguments = [pythonPath]
        }
        proc.currentDirectoryURL = workspaceURL
        proc.arguments?.append(contentsOf: [
            "-m", "humungousaur",
            "collectors-loop",
            "--workspace", workspaceURL.path,
            "--data-dir", dataDir.path,
            "--force",
            "--no-consumers",
        ])

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        proc.environment = environment

        let output = Pipe()
        let error = Pipe()
        loopStdoutPipe = output
        loopStderrPipe = error
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
                self?.isRunning = self?.hostProcess?.isRunning == true
                self?.appendLog("Collector ingestion loop exited.")
            }
        }

        try proc.run()
        loopProcess = proc
        appendLog("Started collector ingestion loop.")
    }

    private func appendLog(_ text: String) {
        for line in text.components(separatedBy: .newlines).filter({ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) {
            logLines.append("\(Date.now.formatted(date: .omitted, time: .standard))  \(line)")
        }
        if logLines.count > 120 {
            logLines.removeFirst(logLines.count - 120)
        }
    }

    private static func launchConfiguration(workspaceURL: URL) -> (executableURL: URL, arguments: [String])? {
        let bundled = Bundle.main.bundleURL
            .appendingPathComponent("Contents")
            .appendingPathComponent("MacOS")
            .appendingPathComponent("HumungousaurMacCollectorHost")
        if FileManager.default.isExecutableFile(atPath: bundled.path) {
            return (bundled, [])
        }

        let script = workspaceURL.appendingPathComponent("script").appendingPathComponent("run_macos_file_events.sh")
        if FileManager.default.fileExists(atPath: script.path) {
            if FileManager.default.isExecutableFile(atPath: script.path) {
                return (script, [])
            }
            return (URL(fileURLWithPath: "/bin/bash"), [script.path])
        }

        let package = workspaceURL.appendingPathComponent("collectors").appendingPathComponent("macos")
        if FileManager.default.fileExists(atPath: package.appendingPathComponent("Package.swift").path) {
            return (URL(fileURLWithPath: "/usr/bin/env"), ["swift", "run", "--package-path", package.path, "HumungousaurMacCollectorHost"])
        }

        return nil
    }
}
