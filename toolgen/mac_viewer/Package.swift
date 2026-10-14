// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "ToolGenViewer",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "ToolGenViewer", targets: ["ToolGenViewerApp"])
    ],
    targets: [
        .executableTarget(
            name: "ToolGenViewerApp",
            path: "Sources/ToolGenViewerApp"
        )
    ]
)
