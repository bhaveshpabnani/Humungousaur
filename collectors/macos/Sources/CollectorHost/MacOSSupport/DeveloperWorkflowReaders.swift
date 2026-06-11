import AppKit
import CoreGraphics
import Foundation

struct DeveloperProcessSnapshot {
    let collector: String
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
    let privacyTier: String
}

struct ProcessRoute {
    let started: String
    let completed: String
    let startedText: String
    let completedText: String
}

struct LocalServiceSnapshot {
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
}

struct DeveloperWorkspaceSnapshot {
    let key: String
    let collector: String
    let stimulusType: String
    let text: String
    let signature: String
    let metadata: [String: String]
    let payload: [String: String]
    let privacyTier: String
}

private let terminalBundles = [
    "com.apple.Terminal",
    "com.googlecode.iterm2",
    "dev.warp.Warp-Stable",
    "com.mitchellh.ghostty",
]
private let ideBundleFragments = ["xcode", "vscode", "visual-studio-code", "jetbrains", "intellij", "pycharm", "webstorm", "goland", "rustrover", "zed", "sublime", "atom"]
private let databaseBundleFragments = ["tableplus", "postico", "sequel", "datagrip", "mongodb", "redis", "db-browser"]
private let cloudConsoleBundleFragments = ["aws", "azure", "google cloud", "cloud console", "docker", "kubernetes"]

private let processCollectorByName: [String: String] = [
    "bash": "terminal_activity",
    "zsh": "terminal_activity",
    "fish": "terminal_activity",
    "sh": "terminal_activity",
    "git": "git_activity",
    "gh": "github_activity",
    "hub": "github_activity",
    "npm": "package_manager_activity",
    "yarn": "package_manager_activity",
    "pnpm": "package_manager_activity",
    "pip": "package_manager_activity",
    "pip3": "package_manager_activity",
    "poetry": "package_manager_activity",
    "uv": "package_manager_activity",
    "bundle": "package_manager_activity",
    "bundler": "package_manager_activity",
    "cargo": "package_manager_activity",
    "composer": "package_manager_activity",
    "go": "package_manager_activity",
    "xcodebuild": "build_tool_activity",
    "swift": "build_tool_activity",
    "make": "build_tool_activity",
    "cmake": "build_tool_activity",
    "ninja": "build_tool_activity",
    "gradle": "build_tool_activity",
    "mvn": "build_tool_activity",
    "pytest": "test_runner_activity",
    "jest": "test_runner_activity",
    "vitest": "test_runner_activity",
    "mocha": "test_runner_activity",
    "ctest": "test_runner_activity",
    "xctest": "test_runner_activity",
    "lldb": "debugger_activity",
    "debugserver": "debugger_activity",
    "gdb": "debugger_activity",
    "psql": "database_activity",
    "mysql": "database_activity",
    "sqlite3": "database_activity",
    "redis-cli": "database_activity",
    "mongosh": "database_activity",
    "aws": "cloud_console_activity",
    "gcloud": "cloud_console_activity",
    "az": "cloud_console_activity",
    "kubectl": "cloud_console_activity",
    "terraform": "cloud_console_activity",
    "pulumi": "cloud_console_activity",
    "vercel": "cloud_console_activity",
    "flyctl": "cloud_console_activity",
    "heroku": "cloud_console_activity",
]

func developerAppRoute(_ app: NSRunningApplication) -> (collector: String, stimulusType: String, text: String, privacyTier: String)? {
    let bundle = (app.bundleIdentifier ?? "").lowercased()
    let name = safeAppName(app).lowercased()
    if terminalBundles.contains(app.bundleIdentifier ?? "") || name.contains("terminal") || name.contains("iterm") || name.contains("warp") {
        return ("terminal_activity", "terminal_command_started", "Terminal app metadata observed.", "metadata")
    }
    if ideBundleFragments.contains(where: { bundle.contains($0) || name.contains($0) }) {
        return ("ide_activity", "file_opened_in_ide", "IDE foreground metadata observed.", "metadata")
    }
    if databaseBundleFragments.contains(where: { bundle.contains($0) || name.contains($0) }) {
        return ("database_activity", "database_connected", "Database client metadata observed.", "sensitive_metadata")
    }
    if cloudConsoleBundleFragments.contains(where: { bundle.contains($0) || name.contains($0) }) {
        return ("cloud_console_activity", "cloud_resource_opened", "Cloud console metadata observed.", "sensitive_metadata")
    }
    return nil
}

func developerForegroundMetadata(app: NSRunningApplication) -> [String: String] {
    let snapshot = frontmostWindowSnapshot(for: app)
    return appMetadata(app).merging(snapshot, uniquingKeysWith: { current, _ in current }).merging([
        "source_api": "NSWorkspace+CGWindowList",
        "window_title_omitted": "true",
        "file_paths_omitted": "true",
        "diagnostics_omitted": "true",
        "command_line_omitted": "true",
    ], uniquingKeysWith: { current, _ in current })
}

func developerProcessSnapshots() -> [DeveloperProcessSnapshot] {
    processNames().compactMap { process in
        guard let collector = processCollectorByName[process.name] else {
            return nil
        }
        let category = developerProcessCategory(process.name, collector: collector)
        let signature = "\(collector)|\(process.name)|\(process.pid)"
        let privacyTier = collector == "terminal_activity" || collector == "ide_activity" || collector == "git_activity" || collector == "github_activity" ? "metadata" : "sensitive_metadata"
        let metadata = [
            "native_source": "macos_process_name_metadata",
            "source_api": "Process.ps_comm",
            "privacy_level": "redacted",
            "process_name": process.name,
            "process_category": category,
            "process_identifier_hash": shortDigest(String(process.pid)),
            "command_line_omitted": "true",
            "working_directory_omitted": "true",
            "logs_omitted": "true",
            "paths_omitted": "true",
        ]
        return DeveloperProcessSnapshot(
            collector: collector,
            signature: signature,
            metadata: metadata,
            payload: [
                "process_name": process.name,
                "process_category": category,
                "process_signature_hash": shortDigest(signature),
            ],
            privacyTier: privacyTier
        )
    }
}

func processRoute(collector: String) -> ProcessRoute {
    switch collector {
    case "terminal_activity":
        return ProcessRoute(started: "terminal_command_started", completed: "terminal_command_finished", startedText: "Terminal process metadata observed.", completedText: "Terminal process completed.")
    case "git_activity":
        return ProcessRoute(started: "git_branch_changed", completed: "working_tree_clean", startedText: "Git process metadata observed.", completedText: "Git process completed.")
    case "github_activity":
        return ProcessRoute(started: "merge_ready", completed: "merge_ready", startedText: "GitHub CLI metadata observed.", completedText: "GitHub CLI process completed.")
    case "package_manager_activity":
        return ProcessRoute(started: "dependency_install_started", completed: "dependency_install_completed", startedText: "Package-manager process metadata observed.", completedText: "Package-manager process completed.")
    case "build_tool_activity":
        return ProcessRoute(started: "build_task_started", completed: "build_task_completed", startedText: "Build-tool process metadata observed.", completedText: "Build-tool process completed.")
    case "test_runner_activity":
        return ProcessRoute(started: "test_suite_started", completed: "test_suite_completed", startedText: "Test-runner process metadata observed.", completedText: "Test-runner process completed.")
    case "debugger_activity":
        return ProcessRoute(started: "debugger_attached", completed: "debugger_detached", startedText: "Debugger process metadata observed.", completedText: "Debugger process detached.")
    case "database_activity":
        return ProcessRoute(started: "database_connected", completed: "database_disconnected", startedText: "Database client process metadata observed.", completedText: "Database client process completed.")
    case "cloud_console_activity":
        return ProcessRoute(started: "cloud_resource_changed", completed: "cloud_resource_changed", startedText: "Cloud tool process metadata observed.", completedText: "Cloud tool process completed.")
    default:
        return ProcessRoute(started: "terminal_command_started", completed: "terminal_command_finished", startedText: "Developer process metadata observed.", completedText: "Developer process completed.")
    }
}

func localServiceSnapshots() -> [LocalServiceSnapshot] {
    let output = runProcess("/usr/sbin/lsof", ["-nP", "-iTCP", "-sTCP:LISTEN", "-Fpcn"])
    guard output.status == 0 else {
        return []
    }
    var result: [LocalServiceSnapshot] = []
    var pid = ""
    var command = ""
    for line in output.stdout.split(separator: "\n") {
        if line.hasPrefix("p") {
            pid = String(line.dropFirst())
        } else if line.hasPrefix("c") {
            command = sanitizedProcessName(String(line.dropFirst()))
        } else if line.hasPrefix("n"), !pid.isEmpty, !command.isEmpty {
            let endpoint = String(line.dropFirst())
            guard endpoint.contains("LISTEN") || endpoint.contains(":") else {
                continue
            }
            let portBucket = listenerPortBucket(endpoint)
            let signature = "\(command)|\(pid)|\(portBucket)"
            result.append(
                LocalServiceSnapshot(
                    signature: signature,
                    metadata: [
                        "native_source": "macos_lsof_listener_metadata",
                        "source_api": "Process.lsof",
                        "privacy_level": "redacted",
                        "process_name": command,
                        "process_identifier_hash": shortDigest(pid),
                        "port_bucket": portBucket,
                        "endpoint_paths_omitted": "true",
                        "command_line_omitted": "true",
                        "logs_omitted": "true",
                    ],
                    payload: [
                        "process_name": command,
                        "port_bucket": portBucket,
                        "listener_signature_hash": shortDigest(signature),
                    ]
                )
            )
        }
    }
    return result
}

func developerWorkspaceSnapshots(workspace: URL, dataDir: URL) -> [DeveloperWorkspaceSnapshot] {
    let root = workspace.standardizedFileURL
    let ignored = [dataDir.standardizedFileURL]
    var snapshots: [DeveloperWorkspaceSnapshot] = []
    if !shouldIgnoreFileURL(root, ignoredRoots: ignored) {
        snapshots.append(contentsOf: gitSnapshots(root))
        snapshots.append(contentsOf: packageSnapshots(root))
        snapshots.append(contentsOf: buildSnapshots(root))
        snapshots.append(contentsOf: testSnapshots(root))
        snapshots.append(contentsOf: githubSnapshots(root))
    }
    return snapshots
}

private func gitSnapshots(_ root: URL) -> [DeveloperWorkspaceSnapshot] {
    let git = root.appendingPathComponent(".git", isDirectory: true)
    guard FileManager.default.fileExists(atPath: git.path) else {
        return []
    }
    var snapshots: [DeveloperWorkspaceSnapshot] = []
    snapshots.append(workspaceSnapshot(root: root, observed: [git.appendingPathComponent("HEAD"), git.appendingPathComponent("packed-refs")], key: "git-head", collector: "git_activity", stimulusType: "git_branch_changed", text: "Git reference metadata changed.", privacyTier: "metadata"))
    snapshots.append(workspaceSnapshot(root: root, observed: [git.appendingPathComponent("index")], key: "git-index", collector: "git_activity", stimulusType: "working_tree_dirty", text: "Git index metadata changed.", privacyTier: "metadata"))
    let mergeHead = git.appendingPathComponent("MERGE_HEAD")
    if FileManager.default.fileExists(atPath: mergeHead.path) {
        snapshots.append(workspaceSnapshot(root: root, observed: [mergeHead], key: "git-merge", collector: "git_activity", stimulusType: "merge_conflict_detected", text: "Git merge metadata observed.", privacyTier: "metadata"))
    }
    return snapshots
}

private func packageSnapshots(_ root: URL) -> [DeveloperWorkspaceSnapshot] {
    let files = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "Gemfile.lock", "Cargo.lock", "composer.lock"].map { root.appendingPathComponent($0) }
    guard files.contains(where: { FileManager.default.fileExists(atPath: $0.path) }) else {
        return []
    }
    return [workspaceSnapshot(root: root, observed: files, key: "package-lockfiles", collector: "package_manager_activity", stimulusType: "lockfile_changed", text: "Package lockfile metadata changed.", privacyTier: "sensitive_metadata")]
}

private func buildSnapshots(_ root: URL) -> [DeveloperWorkspaceSnapshot] {
    let files = ["Package.swift", "pyproject.toml", "Makefile", "CMakeLists.txt", "build.gradle", "pom.xml", "webpack.config.js", "vite.config.ts", "next.config.js"].map { root.appendingPathComponent($0) }
    guard files.contains(where: { FileManager.default.fileExists(atPath: $0.path) }) else {
        return []
    }
    return [workspaceSnapshot(root: root, observed: files, key: "build-config", collector: "build_tool_activity", stimulusType: "build_config_changed", text: "Build configuration metadata changed.", privacyTier: "sensitive_metadata")]
}

private func testSnapshots(_ root: URL) -> [DeveloperWorkspaceSnapshot] {
    let files = ["pytest.ini", "vitest.config.ts", "jest.config.js", "coverage", ".coverage", "lcov.info"].map { root.appendingPathComponent($0) }
    guard files.contains(where: { FileManager.default.fileExists(atPath: $0.path) }) else {
        return []
    }
    return [workspaceSnapshot(root: root, observed: files, key: "test-metadata", collector: "test_runner_activity", stimulusType: "coverage_report_generated", text: "Test/coverage metadata changed.", privacyTier: "sensitive_metadata")]
}

private func githubSnapshots(_ root: URL) -> [DeveloperWorkspaceSnapshot] {
    let github = root.appendingPathComponent(".github", isDirectory: true)
    guard FileManager.default.fileExists(atPath: github.path) else {
        return []
    }
    return [workspaceSnapshot(root: root, observed: [github], key: "github-metadata", collector: "github_activity", stimulusType: "ci_passed", text: "GitHub workflow metadata changed.", privacyTier: "metadata")]
}

private func workspaceSnapshot(root: URL, observed: [URL], key: String, collector: String, stimulusType: String, text: String, privacyTier: String) -> DeveloperWorkspaceSnapshot {
    let existing = observed.filter { FileManager.default.fileExists(atPath: $0.path) }
    let parts = existing.map { fileAttributeSignature($0) }.sorted()
    let signature = parts.isEmpty ? "missing" : shortDigest(parts.joined(separator: "|"))
    let metadata = [
        "native_source": "macos_workspace_metadata",
        "source_api": "FileManager",
        "privacy_level": "redacted",
        "workspace_digest": shortDigest(root.path),
        "observed_file_count_bucket": countBucket(existing.count),
        "observed_paths_omitted": "true",
        "filenames_omitted": "true",
        "file_contents_omitted": "true",
        "logs_omitted": "true",
    ]
    return DeveloperWorkspaceSnapshot(
        key: key,
        collector: collector,
        stimulusType: stimulusType,
        text: text,
        signature: signature,
        metadata: metadata,
        payload: [
            "workspace_digest": shortDigest(root.path),
            "workspace_metadata_signature": signature,
            "observed_file_count_bucket": countBucket(existing.count),
        ],
        privacyTier: privacyTier
    )
}

private func fileAttributeSignature(_ url: URL) -> String {
    if let values = try? url.resourceValues(forKeys: [.isDirectoryKey, .contentModificationDateKey, .fileSizeKey]) {
        let modified = Int(values.contentModificationDate?.timeIntervalSince1970 ?? 0)
        let size = values.fileSize ?? 0
        return "\(shortDigest(url.path)):\(values.isDirectory == true ? "dir" : "file"):\(modified):\(size)"
    }
    return "\(shortDigest(url.path)):missing"
}

private func processNames() -> [(pid: String, name: String)] {
    let output = runProcess("/bin/ps", ["-axo", "pid=,comm="])
    guard output.status == 0 else {
        return []
    }
    return output.stdout.split(separator: "\n").compactMap { line in
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let firstSpace = trimmed.firstIndex(where: { $0 == " " || $0 == "\t" }) else {
            return nil
        }
        let pid = String(trimmed[..<firstSpace]).trimmingCharacters(in: .whitespacesAndNewlines)
        let command = String(trimmed[firstSpace...]).trimmingCharacters(in: .whitespacesAndNewlines)
        let name = sanitizedProcessName(URL(fileURLWithPath: command).lastPathComponent)
        guard !pid.isEmpty, !name.isEmpty else {
            return nil
        }
        return (pid, name)
    }
}

private func runProcess(_ executable: String, _ arguments: [String]) -> (status: Int32, stdout: String) {
    let process = Process()
    let pipe = Pipe()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    process.standardOutput = pipe
    process.standardError = Pipe()
    do {
        try process.run()
        process.waitUntilExit()
    } catch {
        return (-1, "")
    }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    return (process.terminationStatus, String(data: data, encoding: .utf8) ?? "")
}

private func sanitizedProcessName(_ raw: String) -> String {
    let cleaned = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    return String(cleaned.filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" || $0 == "." }.prefix(48))
}

private func developerProcessCategory(_ name: String, collector: String) -> String {
    switch collector {
    case "terminal_activity": return "shell"
    case "git_activity": return "git"
    case "github_activity": return "github_cli"
    case "package_manager_activity": return "package_manager"
    case "build_tool_activity": return "build_tool"
    case "test_runner_activity": return "test_runner"
    case "debugger_activity": return "debugger"
    case "database_activity": return "database_client"
    case "cloud_console_activity": return "cloud_tool"
    default: return name
    }
}

private func listenerPortBucket(_ endpoint: String) -> String {
    guard let portText = endpoint.split(separator: ":").last?.split(separator: " ").first,
          let port = Int(portText) else {
        return "unknown"
    }
    switch port {
    case 0..<1024: return "system"
    case 1024..<3000: return "app_low"
    case 3000..<10000: return "dev_common"
    default: return "ephemeral"
    }
}
