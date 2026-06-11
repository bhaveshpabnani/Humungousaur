import Foundation

typealias NativeObservation = (center: NotificationCenter, token: NSObjectProtocol)

final class OSSystemSurfacesRuntime {
    private let permissionLocation: PermissionLocationCollector
    private let resourceStorage: ResourceStorageCollector
    private let softwareInventory: SoftwareInventoryCollector
    private let printScan: PrintScanCollector
    private let peripherals: PeripheralCollector
    private let systemSurfaces: OSSystemSurfaceCollector
    private let focusTask: FocusTaskCollector
    private let policy: PolicyCollector
    private let pollSeconds: TimeInterval
    private var timer: Timer?
    private var observations: [NativeObservation] = []

    init(spool: CollectorSpool, health: HelperHealthReporter, pollSeconds: TimeInterval) {
        self.permissionLocation = PermissionLocationCollector(spool: spool, health: health)
        self.resourceStorage = ResourceStorageCollector(spool: spool, health: health)
        self.softwareInventory = SoftwareInventoryCollector(spool: spool, health: health)
        self.printScan = PrintScanCollector(spool: spool, health: health)
        self.peripherals = PeripheralCollector(spool: spool, health: health)
        self.systemSurfaces = OSSystemSurfaceCollector(spool: spool, health: health)
        self.focusTask = FocusTaskCollector(spool: spool, health: health)
        self.policy = PolicyCollector(spool: spool, health: health)
        self.pollSeconds = pollSeconds
    }

    func start() {
        observations.append(contentsOf: softwareInventory.installObservers())
        observations.append(contentsOf: peripherals.installObservers())
        observations.append(contentsOf: focusTask.installObservers())
        observations.append(contentsOf: permissionLocation.installObservers())
        sampleAll(emitInitial: true)
        timer = Timer.scheduledTimer(withTimeInterval: pollSeconds, repeats: true) { [weak self] _ in
            self?.sampleAll(emitInitial: false)
        }
    }

    func sampleOnce() {
        sampleAll(emitInitial: true)
    }

    func stop() {
        timer?.invalidate()
        for observation in observations {
            observation.center.removeObserver(observation.token)
        }
        observations.removeAll()
    }

    private func sampleAll(emitInitial: Bool) {
        permissionLocation.sample(emitInitial: emitInitial)
        resourceStorage.sample(emitInitial: emitInitial)
        softwareInventory.sample(emitInitial: emitInitial)
        printScan.sample(emitInitial: emitInitial)
        peripherals.sample(emitInitial: emitInitial)
        systemSurfaces.sample(emitInitial: emitInitial)
        focusTask.sample(emitInitial: emitInitial)
        policy.sample(emitInitial: emitInitial)
    }
}
