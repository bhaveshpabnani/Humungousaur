import Foundation
import IOKit.ps
import SystemConfiguration

func powerSnapshot() -> [String: String] {
    var result = ["low_power_mode": String(ProcessInfo.processInfo.isLowPowerModeEnabled)]
    guard let info = IOPSCopyPowerSourcesInfo()?.takeRetainedValue(),
          let sources = IOPSCopyPowerSourcesList(info)?.takeRetainedValue() as? [CFTypeRef] else {
        return result
    }
    for source in sources {
        guard let description = IOPSGetPowerSourceDescription(info, source)?.takeUnretainedValue() as? [String: Any] else {
            continue
        }
        let current = description[kIOPSCurrentCapacityKey] as? Int ?? 0
        let max = max(1, description[kIOPSMaxCapacityKey] as? Int ?? 1)
        let percent = Int((Double(current) / Double(max)) * 100)
        result["power_source_state"] = description[kIOPSPowerSourceStateKey] as? String ?? ""
        result["battery_percent_bucket"] = batteryBucket(percent)
        result["battery_low"] = String(percent <= 20)
        break
    }
    result["source_api"] = "IOKitPowerSources"
    return result
}

func networkSnapshot() -> [String: String] {
    var address = sockaddr()
    address.sa_len = UInt8(MemoryLayout<sockaddr>.size)
    address.sa_family = sa_family_t(AF_INET)
    guard let reachability = withUnsafePointer(to: &address, { pointer in
        pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            SCNetworkReachabilityCreateWithAddress(nil, $0)
        }
    }) else {
        return [:]
    }
    var flags = SCNetworkReachabilityFlags()
    guard SCNetworkReachabilityGetFlags(reachability, &flags) else {
        return [:]
    }
    return [
        "reachable": String(flags.contains(.reachable)),
        "connection_required": String(flags.contains(.connectionRequired)),
        "transient_connection": String(flags.contains(.transientConnection)),
        "source_api": "SystemConfigurationReachability",
    ]
}

func idleSeconds() -> Double? {
    let service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOHIDSystem"))
    guard service != 0 else {
        return nil
    }
    defer { IOObjectRelease(service) }
    var properties: Unmanaged<CFMutableDictionary>?
    guard IORegistryEntryCreateCFProperties(service, &properties, kCFAllocatorDefault, 0) == KERN_SUCCESS,
          let dictionary = properties?.takeRetainedValue() as? [String: Any],
          let idle = dictionary["HIDIdleTime"] as? UInt64 else {
        return nil
    }
    return Double(idle) / 1_000_000_000
}
