import Foundation

final class CollectorHostRuntime {
    private let coreOSContext: CoreOSContextRuntime
    private let communicationMeetings: CommunicationMeetingsRuntime
    private let osSystemSurfaces: OSSystemSurfacesRuntime
    private let fileSystemContext: FileSystemContextRuntime
    private let browserContext: BrowserContextRuntime
    private let screenUIMetadata: ScreenUIMetadataRuntime
    private let developerWorkflow: DeveloperWorkflowRuntime
    private let mailCalendarWorkflow: MailCalendarWorkflowRuntime
    private let appleAppsWorkflow: AppleAppsWorkflowRuntime

    init(options: CollectorHostOptions, spool: CollectorSpool, health: HelperHealthReporter) {
        self.coreOSContext = CoreOSContextRuntime(spool: spool, health: health, pollSeconds: options.pollSeconds)
        self.communicationMeetings = CommunicationMeetingsRuntime(spool: spool, health: health, pollSeconds: options.pollSeconds)
        self.osSystemSurfaces = OSSystemSurfacesRuntime(spool: spool, health: health, pollSeconds: options.pollSeconds)
        self.browserContext = BrowserContextRuntime(spool: spool, health: health, pollSeconds: options.pollSeconds)
        self.screenUIMetadata = ScreenUIMetadataRuntime(spool: spool, health: health, pollSeconds: options.pollSeconds)
        self.mailCalendarWorkflow = MailCalendarWorkflowRuntime(spool: spool, health: health, pollSeconds: options.pollSeconds)
        self.appleAppsWorkflow = AppleAppsWorkflowRuntime(spool: spool, health: health, pollSeconds: options.pollSeconds)
        self.developerWorkflow = DeveloperWorkflowRuntime(
            options: DeveloperWorkflowOptions(workspace: options.workspace, dataDir: options.dataDir, pollSeconds: options.pollSeconds),
            spool: spool,
            health: health
        )
        self.fileSystemContext = FileSystemContextRuntime(
            options: FileSystemContextOptions(
                workspace: options.workspace,
                dataDir: options.dataDir,
                watchRoots: options.watchRoots,
                latency: options.fileEventLatency,
                pollSeconds: options.pollSeconds
            ),
            spool: spool,
            health: health
        )
    }

    func start() {
        coreOSContext.start()
        communicationMeetings.start()
        osSystemSurfaces.start()
        browserContext.start()
        screenUIMetadata.start()
        mailCalendarWorkflow.start()
        appleAppsWorkflow.start()
        developerWorkflow.start()
        fileSystemContext.start()
    }

    func sampleOnce() {
        coreOSContext.sampleOnce()
        communicationMeetings.sampleOnce()
        osSystemSurfaces.sampleOnce()
        browserContext.sampleOnce()
        screenUIMetadata.sampleOnce()
        mailCalendarWorkflow.sampleOnce()
        appleAppsWorkflow.sampleOnce()
        developerWorkflow.sampleOnce()
        fileSystemContext.sampleOnce()
    }

    func stop() {
        coreOSContext.stop()
        communicationMeetings.stop()
        osSystemSurfaces.stop()
        browserContext.stop()
        screenUIMetadata.stop()
        mailCalendarWorkflow.stop()
        appleAppsWorkflow.stop()
        developerWorkflow.stop()
        fileSystemContext.stop()
    }
}
