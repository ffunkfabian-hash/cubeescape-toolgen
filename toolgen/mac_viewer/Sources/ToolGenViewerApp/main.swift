import AppKit
import Foundation
import SceneKit
import UniformTypeIdentifiers

@MainActor
final class ModelPreviewView: NSView {
    private let sceneView = SCNView()

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        sceneView.frame = bounds
        sceneView.autoresizingMask = [.width, .height]
        sceneView.backgroundColor = NSColor(calibratedRed: 0.08, green: 0.1, blue: 0.13, alpha: 1)
        sceneView.allowsCameraControl = true
        sceneView.autoenablesDefaultLighting = true
        sceneView.antialiasingMode = .multisampling4X
        addSubview(sceneView)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func loadModel(from url: URL) throws {
        let scene = try SCNScene(url: url, options: nil)
        let camera = SCNNode()
        camera.camera = SCNCamera()
        camera.camera?.zFar = 100
        camera.position = SCNVector3(1.4, 1.1, 1.4)
        camera.look(at: SCNVector3(0, 0, 0))
        scene.rootNode.addChildNode(camera)
        sceneView.scene = scene
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var preview: ModelPreviewView!
    private var infoText: NSTextView!
    private var statusText: NSTextField!
    private var outputRoot = URL(fileURLWithPath: NSHomeDirectory())
        .appendingPathComponent("Documents/CubeEscapeToolgen", isDirectory: true)
    private var generatorProcess: Process?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let frame = NSRect(x: 0, y: 0, width: 1200, height: 780)
        window = NSWindow(
            contentRect: frame,
            styleMask: [.titled, .closable, .resizable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Cube Escape ToolGen"
        window.center()
        window.isReleasedWhenClosed = false

        let content = NSView(frame: frame)
        content.wantsLayer = true
        content.layer?.backgroundColor = NSColor.controlBackgroundColor.cgColor

        let generateButton = NSButton(title: "Generate Portal Emitter", target: self, action: #selector(generateTool))
        generateButton.frame = NSRect(x: 20, y: frame.height - 52, width: 210, height: 32)
        content.addSubview(generateButton)

        let openButton = NSButton(title: "Open OBJ…", target: self, action: #selector(openModel))
        openButton.frame = NSRect(x: 240, y: frame.height - 52, width: 120, height: 32)
        content.addSubview(openButton)

        let outputButton = NSButton(title: "Output folder…", target: self, action: #selector(chooseOutputFolder))
        outputButton.frame = NSRect(x: 370, y: frame.height - 52, width: 140, height: 32)
        content.addSubview(outputButton)

        statusText = NSTextField(labelWithString: "Ready — Blender-backed generator")
        statusText.frame = NSRect(x: 525, y: frame.height - 50, width: 640, height: 28)
        statusText.autoresizingMask = [.width]
        content.addSubview(statusText)

        preview = ModelPreviewView(frame: NSRect(x: 20, y: 20, width: frame.width - 430, height: frame.height - 90))
        preview.autoresizingMask = [.width, .height]
        content.addSubview(preview)

        let infoPanel = NSScrollView(frame: NSRect(x: frame.width - 380, y: 20, width: 340, height: frame.height - 90))
        infoPanel.borderType = .grooveBorder
        infoPanel.hasVerticalScroller = true
        infoPanel.hasHorizontalScroller = false
        infoPanel.autoresizingMask = [.minXMargin, .height]

        infoText = NSTextView(frame: infoPanel.contentView.bounds)
        infoText.isEditable = false
        infoText.isSelectable = true
        infoText.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        infoText.backgroundColor = NSColor.textBackgroundColor
        infoText.textColor = NSColor.labelColor
        infoText.string = """
        Generator: Robogen/Cubegen-style pipeline
        Model preview: SceneKit OBJ viewer
        Build output: \(outputRoot.path)

        Generate Portal Emitter to create the Blender source, FBX, GLB, OBJ, preview, geometry QA and manifest.
        Drag to orbit, scroll to zoom.
        """

        infoPanel.documentView = infoText
        content.addSubview(infoPanel)
        window.contentView = content
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        let defaultModel = outputRoot.appendingPathComponent("portal_emitter/PortalEmitter.obj")
        if FileManager.default.fileExists(atPath: defaultModel.path) {
            loadGeneratedPackage(defaultModel.deletingLastPathComponent())
        }
    }

    @objc private func generateTool() {
        guard generatorProcess == nil else { return }
        do {
            let root = try toolgenRoot()
            let python = try findPython()
            let outputRoot = self.outputRoot
            try FileManager.default.createDirectory(at: outputRoot, withIntermediateDirectories: true)

            let process = Process()
            process.executableURL = URL(fileURLWithPath: python)
            process.arguments = [
                root.appendingPathComponent("build_toolset.py").path,
                "--tool", "portal_emitter",
                "--output", outputRoot.path,
                "--force",
            ]
            process.currentDirectoryURL = root
            var environment = ProcessInfo.processInfo.environment
            environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + (environment["PATH"] ?? "/usr/bin:/bin")
            environment["PYTHONUNBUFFERED"] = "1"
            process.environment = environment

            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            process.terminationHandler = { [weak self] finishedProcess in
                let output = String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
                let status = finishedProcess.terminationStatus
                Task { @MainActor [weak self] in
                    self?.generatorFinished(status: status, output: output, outputRoot: outputRoot)
                }
            }
            try process.run()
            generatorProcess = process
            statusText.stringValue = "Generating Portal Emitter with Blender…"
            infoText.string = "Running build_toolset.py\n\n\(process.arguments?.joined(separator: " ") ?? "")"
        } catch {
            showError(error)
        }
    }

    @objc private func openModel() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = UTType(filenameExtension: "obj").map { [$0] } ?? []
        guard panel.runModal() == .OK, let selected = panel.url else { return }
        do {
            try preview.loadModel(from: selected)
            statusText.stringValue = "Viewing \(selected.lastPathComponent)"
            loadPackageInfo(selected.deletingLastPathComponent())
        } catch {
            showError(error)
        }
    }

    @objc private func chooseOutputFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let selected = panel.url else { return }
        outputRoot = selected
        statusText.stringValue = "Output: \(selected.path)"
    }

    private func generatorFinished(status: Int32, output: String, outputRoot: URL) {
        generatorProcess = nil
        infoText.string = output.isEmpty ? "Generator completed without console output." : output
        guard status == 0 else {
            statusText.stringValue = "Generation failed (exit \(status)); see output."
            return
        }

        let package = outputRoot.appendingPathComponent("portal_emitter")
        loadGeneratedPackage(package.appendingPathComponent("PortalEmitter.obj").deletingLastPathComponent())
        statusText.stringValue = "Generated and QA-verified Portal Emitter"
    }

    private func loadGeneratedPackage(_ package: URL) {
        do {
            try preview.loadModel(from: package.appendingPathComponent("PortalEmitter.obj"))
            loadPackageInfo(package)
        } catch {
            showError(error)
        }
    }

    private func loadPackageInfo(_ package: URL) {
        let contractURL = package.appendingPathComponent("tool_contract.json")
        let qaURL = package.appendingPathComponent("qa_geometry.json")
        let manifestURL = package.appendingPathComponent("manifest.json")
        let sections = [("TOOL CONTRACT", contractURL), ("MEASURED GEOMETRY QA", qaURL), ("BUILD MANIFEST", manifestURL)]
        var content: [String] = []
        for (title, url) in sections where FileManager.default.fileExists(atPath: url.path) {
            do {
                let data = try Data(contentsOf: url)
                let json = try JSONSerialization.jsonObject(with: data)
                let formatted = try JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted, .sortedKeys])
                content.append("\(title)\n\(String(decoding: formatted, as: UTF8.self))")
            } catch {
                content.append("\(title)\nCould not read \(url.lastPathComponent): \(error.localizedDescription)")
            }
        }
        infoText.string = content.isEmpty ? "No contract or QA report beside this model." : content.joined(separator: "\n\n")
    }

    private func toolgenRoot() throws -> URL {
        if let configured = ProcessInfo.processInfo.environment["TOOLGEN_ROOT"] {
            let root = URL(fileURLWithPath: configured, isDirectory: true)
            if FileManager.default.fileExists(atPath: root.appendingPathComponent("build_toolset.py").path) {
                return root
            }
        }
        if let bundled = Bundle.main.resourceURL?.appendingPathComponent("toolgen", isDirectory: true),
           FileManager.default.fileExists(atPath: bundled.appendingPathComponent("build_toolset.py").path) {
            return bundled
        }
        let sourceRoot = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        if FileManager.default.fileExists(atPath: sourceRoot.appendingPathComponent("build_toolset.py").path) {
            return sourceRoot
        }
        throw NSError(
            domain: "ToolGenViewer",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "Toolgen's Python backend could not be found. Rebuild the app bundle or set TOOLGEN_ROOT."]
        )
    }

    private func findPython() throws -> String {
        let environment = ProcessInfo.processInfo.environment
        var candidates = [environment["TOOLGEN_PYTHON"], "/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
        if let path = environment["PATH"] {
            candidates.append(contentsOf: path.split(separator: ":").map { "\($0)/python3" })
        }
        if let python = candidates.compactMap({ $0 }).first(where: { FileManager.default.isExecutableFile(atPath: $0) }) {
            return python
        }
        throw NSError(
            domain: "ToolGenViewer",
            code: 2,
            userInfo: [NSLocalizedDescriptionKey: "Python 3 was not found. Set TOOLGEN_PYTHON to its executable path."]
        )
    }

    private func showError(_ error: Error) {
        let alert = NSAlert(error: error)
        alert.runModal()
    }
}

@main
struct ToolGenViewerApp {
    @MainActor
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}
