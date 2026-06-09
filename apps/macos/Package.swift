// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "HumungousaurMac",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "HumungousaurMac", targets: ["HumungousaurMac"])
    ],
    targets: [
        .executableTarget(
            name: "HumungousaurMac",
            path: "Sources",
            resources: [
                .process("Resources")
            ]
        )
    ]
)
