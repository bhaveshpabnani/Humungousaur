// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "HumungousaurMacCollectors",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "HumungousaurMacCollectorHost", targets: ["CollectorHost"]),
        .library(name: "HumungousaurMacEventWriter", targets: ["EventWriter"])
    ],
    targets: [
        .target(name: "EventWriter", path: "Sources/EventWriter"),
        .executableTarget(
            name: "CollectorHost",
            dependencies: ["EventWriter"],
            path: "Sources/CollectorHost",
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("ApplicationServices"),
                .linkedFramework("Carbon"),
                .linkedFramework("CoreServices"),
                .linkedFramework("CoreGraphics"),
                .linkedFramework("AVFoundation"),
                .linkedFramework("CoreLocation"),
                .linkedFramework("EventKit"),
                .linkedFramework("IOKit"),
                .linkedFramework("SystemConfiguration")
            ]
        )
    ]
)
