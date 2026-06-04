// swift-tools-version: 6.1

import PackageDescription

let package = Package(
    name: "BookMaker",
    platforms: [
        .macOS(.v15)
    ],
    products: [
        .executable(name: "BookMaker", targets: ["BookMaker"])
    ],
    targets: [
        .executableTarget(
            name: "BookMaker",
            resources: [
                .process("Resources")
            ],
            linkerSettings: [
                .linkedLibrary("sqlite3")
            ]
        ),
        .testTarget(
            name: "BookMakerTests",
            dependencies: ["BookMaker"],
            linkerSettings: [
                .linkedLibrary("sqlite3")
            ]
        )
    ]
)
