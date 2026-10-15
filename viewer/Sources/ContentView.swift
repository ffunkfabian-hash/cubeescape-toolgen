import AppKit
import SceneKit
import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class Playhead: ObservableObject { @Published var fraction = 0.0 }

@MainActor
final class ViewerModel: ObservableObject {
    @Published private(set) var data: ToolData
    @Published private(set) var scene: ToolScene
    @Published private(set) var selected: ModelInfo
    @Published var look: ToolLook { didSet { scene.apply(look) } }
    @Published var viewName = "Iso"
    @Published var playing = false
    @Published var loop = false
    @Published var speed = 1.0
    @Published var turntable = false
    @Published var floor = true { didSet { scene.showFloor(floor) } }
    @Published var sockets = false { didSet { scene.showSockets(sockets) } }
    @Published var status = ""
    @Published var busy = false
    @Published var tier = "quick"
    @Published var console = ""
    @Published var comparison: ToolScene?
    let playhead = Playhead()
    private var timer: Timer?
    private var lastTick = Date()
    private var fraction = 0.0
    private var comparisonLook: ToolLook?
    private var process: Process?
    private var logHandle: FileHandle?
    private var logURL: URL?
    private var outputRoot: URL

    init(data: ToolData, selection: String? = nil) throws {
        let info = data.catalog.models.first { $0.id == selection } ?? data.catalog.models[0]
        self.data = data
        selected = info
        scene = ToolScene(data: try ModelData(directory: data.directory(info)))
        look = ToolLook(model: info.id)
        outputRoot = Main.value(CommandLine.arguments, "--output").map { URL(fileURLWithPath: $0) } ??
            URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Documents/CubeEscapeToolgen")
        status = "\(selected.label) · \(selected.variantLabel) geladen"
    }

    func select(_ info: ModelInfo) {
        do {
            let next = ToolScene(data: try ModelData(directory: data.directory(info)))
            stop()
            selected = info; scene = next; look.model = info.id
            scene.apply(look); sockets = false
            setView(info.variant == "fps" ? "FPS" : "Iso")
            status = "\(info.label) · \(info.variantLabel) geladen"
        } catch { status = error.localizedDescription }
    }

    func selectTool(_ id: String) {
        if let info = data.catalog.models.first(where: { $0.tool == id && $0.variant == selected.variant }) ??
                      data.catalog.models.first(where: { $0.tool == id }) { select(info) }
    }

    func setView(_ name: String) {
        if name == "FPS", selected.variant != "fps" {
            guard let peer = data.catalog.models.first(where: { $0.tool == selected.tool && $0.variant == "fps" }) else {
                status = "Für dieses Werkzeug ist kein Ego-Modell vorhanden."
                return
            }
            select(peer)
            return
        }
        if name == "FPS", let saved = comparisonLook, comparison != nil,
           let info = data.catalog.models.first(where: { $0.id == saved.model }), info.variant != "fps",
           let peer = data.catalog.models.first(where: { $0.tool == info.tool && $0.variant == "fps" }) {
            do {
                let next = ToolScene(data: try ModelData(directory: data.directory(peer)))
                var converted = saved; converted.model = peer.id
                next.apply(converted); next.seek(fraction)
                comparison = next; comparisonLook = converted
            } catch {
                comparison = nil; comparisonLook = nil
                status = error.localizedDescription
            }
        }
        viewName = name; scene.setView(name); scene.showFloor(floor)
        comparison?.setView(name); comparison?.showFloor(floor)
    }

    func seek(_ value: Double) {
        fraction = min(1, max(0, value)); playhead.fraction = fraction
        scene.seek(fraction); comparison?.seek(fraction)
    }

    func play() {
        guard selected.frames > 1 else { return }
        if fraction >= 1 { seek(0) }
        playing.toggle(); updateTimer()
    }

    func stop() { playing = false; seek(0); updateTimer() }

    func updateTimer() {
        timer?.invalidate(); timer = nil
        guard playing || turntable else { return }
        lastTick = Date()
        timer = Timer.scheduledTimer(withTimeInterval: 1 / 60, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.tick() }
        }
    }

    private func tick() {
        let now = Date(); let delta = min(0.1, now.timeIntervalSince(lastTick)); lastTick = now
        if turntable { scene.turn(Float(delta * 0.4)); comparison?.turn(Float(delta * 0.4)) }
        if playing {
            let duration = Double(scene.data.doc.frames - 1) / scene.data.doc.fps
            let next = fraction + delta * speed / max(duration, 0.001)
            if next >= 1 && !loop { seek(1); playing = false; updateTimer() }
            else { seek(next >= 1 ? next.truncatingRemainder(dividingBy: 1) : next) }
        }
    }

    func rememberB() {
        do {
            let next = ToolScene(data: scene.data); next.apply(look); next.setView(viewName)
            next.seek(fraction); next.showFloor(floor); comparison = next; comparisonLook = look
            status = "B gespeichert – rechts der gemerkte Look"
        }
    }

    func saveLook() {
        let panel = NSSavePanel(); panel.allowedContentTypes = [.json]; panel.nameFieldStringValue = "Werkzeug-Look.json"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(look).write(to: url); status = "Look gespeichert"
        } catch { status = error.localizedDescription }
    }

    func openLook() {
        let panel = NSOpenPanel(); panel.allowedContentTypes = [.json]
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let next = try JSONDecoder().decode(ToolLook.self, from: Data(contentsOf: url))
            try next.validate(catalog: data.catalog)
            if let model = data.catalog.models.first(where: { $0.id == next.model }) { select(model) }
            look = next; status = "Look geladen"
        } catch { status = error.localizedDescription }
    }

    func screenshot() {
        let panel = NSSavePanel(); panel.allowedContentTypes = [.png]
        panel.nameFieldStringValue = "\(selected.label)-\(selected.variant).png"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do { try scene.snapshot(size: CGSize(width: 1470, height: 956)).writePNG(url); status = "Screenshot gespeichert" }
        catch { status = error.localizedDescription }
    }

    func chooseCatalog() {
        let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let next = try ToolData(root: url)
            let first = next.catalog.models[0]
            let loaded = ToolScene(data: try ModelData(directory: next.directory(first)))
            stop(); data = next; selected = first; scene = loaded; look = ToolLook(model: first.id)
            setView(first.variant == "fps" ? "FPS" : "Iso"); status = "Modellkatalog geladen"
        } catch { status = error.localizedDescription }
    }

    func chooseOutput() {
        let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = true
        guard panel.runModal() == .OK, let url = panel.url else { return }
        outputRoot = url; status = "Ausgabe: \(url.path)"
    }

    func generate() {
        guard !busy else { return }
        do {
            guard let resources = Bundle.main.resourceURL else { throw ViewerError.invalid("App-Ressourcen fehlen.") }
            let backend = resources.appendingPathComponent("backend/toolgen/generate_tools.py")
            try FileManager.default.createDirectory(at: outputRoot, withIntermediateDirectories: true)
            // Keep the bundled library available when generating the first individual tool.
            let library = resources.appendingPathComponent("ViewerData")
            for info in data.catalog.models {
                let source = library.appendingPathComponent(info.tool)
                let target = outputRoot.appendingPathComponent(info.tool)
                if !FileManager.default.fileExists(atPath: target.path), FileManager.default.fileExists(atPath: source.path) {
                    try FileManager.default.copyItem(at: source, to: target)
                }
            }
            let python = ProcessInfo.processInfo.environment["TOOLGEN_PYTHON"] ??
                ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"].first {
                    FileManager.default.isExecutableFile(atPath: $0)
                } ?? "/usr/bin/python3"
            let job = Process(); job.executableURL = URL(fileURLWithPath: python)
            job.arguments = [backend.path, "--tier", tier, "--tool", selected.tool, "--output", outputRoot.path]
            var environment = ProcessInfo.processInfo.environment
            environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + (environment["PATH"] ?? "/usr/bin:/bin")
            environment["PYTHONUNBUFFERED"] = "1"; job.environment = environment
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("toolgen-\(UUID().uuidString).log")
            FileManager.default.createFile(atPath: url.path, contents: nil)
            let handle = try FileHandle(forWritingTo: url)
            job.standardOutput = handle; job.standardError = handle
            let destination = outputRoot
            job.terminationHandler = { [weak self] finished in
                Task { @MainActor [weak self] in self?.finished(status: finished.terminationStatus, output: destination) }
            }
            try job.run(); process = job; logHandle = handle; logURL = url
            busy = true; console = ""; status = "\(selected.label) wird erzeugt (\(tier))…"
        } catch { status = error.localizedDescription }
    }

    func cancelGeneration() { process?.terminate() }

    private func finished(status: Int32, output: URL) {
        try? logHandle?.close(); logHandle = nil; process = nil; busy = false
        if let url = logURL {
            console = (try? String(contentsOf: url, encoding: .utf8)) ?? ""
            try? FileManager.default.removeItem(at: url); logURL = nil
        }
        guard status == 0 else { self.status = "Erzeugung fehlgeschlagen (\(status)); Details im Protokoll."; return }
        do {
            let next = try ToolData(root: output)
            let id = selected.id
            let info = next.catalog.models.first { $0.id == id } ?? next.catalog.models[0]
            let loaded = ToolScene(data: try ModelData(directory: next.directory(info)))
            stop(); data = next; selected = info; scene = loaded; look.model = info.id
            scene.apply(look); setView(viewName); self.status = "\(selected.label) erzeugt und geprüft"
        } catch { self.status = error.localizedDescription }
    }
}

struct SceneContainer: NSViewRepresentable {
    let tool: ToolScene
    final class Coordinator { var cameraRevision = -1 }
    func makeCoordinator() -> Coordinator { Coordinator() }
    func makeNSView(context: Context) -> SCNView {
        let view = SCNView()
        view.allowsCameraControl = true; view.antialiasingMode = .multisampling4X
        view.defaultCameraController.interactionMode = .orbitTurntable
        view.preferredFramesPerSecond = 60
        return view
    }
    func updateNSView(_ view: SCNView, context: Context) {
        let changed = view.scene !== tool.scene
        if changed { view.scene = tool.scene }
        if changed || context.coordinator.cameraRevision != tool.cameraRevision {
            view.pointOfView = tool.camera
            context.coordinator.cameraRevision = tool.cameraRevision
        }
    }
}

struct SceneViewport: View {
    let tool: ToolScene
    let firstPerson: Bool
    var body: some View {
        GeometryReader { geometry in
            let size = ToolScene.viewportSize(available: geometry.size, firstPerson: firstPerson)
            SceneContainer(tool: tool).frame(width: size.width, height: size.height)
                .position(x: geometry.size.width / 2, y: geometry.size.height / 2)
        }.background(Color(red: 0.075, green: 0.085, blue: 0.11))
    }
}

struct PlaybackBar: View {
    @ObservedObject var model: ViewerModel
    @ObservedObject var playhead: Playhead
    var body: some View {
        HStack {
            Button(model.playing ? "Pause" : "Abspielen") { model.play() }.keyboardShortcut(.space, modifiers: [])
                .disabled(model.selected.frames <= 1)
            Button("Reset") { model.stop() }
            Slider(value: Binding(get: { playhead.fraction }, set: { model.seek($0) }), in: 0...1)
                .disabled(model.selected.frames <= 1)
            Text("\(Int(playhead.fraction * Double(model.selected.frames - 1)) + 1)/\(model.selected.frames)")
                .monospacedDigit().frame(width: 64)
            Toggle("Loop", isOn: $model.loop)
            Picker("Tempo", selection: $model.speed) { Text("½×").tag(0.5); Text("1×").tag(1.0); Text("2×").tag(2.0) }
                .labelsHidden().frame(width: 70)
        }
    }
}

struct ContentView: View {
    @ObservedObject var model: ViewerModel
    var body: some View {
        HSplitView {
            VStack(spacing: 0) {
                HStack(spacing: 2) {
                    SceneViewport(tool: model.scene, firstPerson: model.viewName == "FPS")
                    if let comparison = model.comparison { SceneViewport(tool: comparison, firstPerson: model.viewName == "FPS").overlay(alignment: .topLeading) { Text("B").font(.title).padding() } }
                }
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        ForEach(ToolScene.views, id: \.self) { name in
                            Button(name == "FPS" ? "Ego" : name) { model.setView(name) }
                                .tint(model.viewName == name ? .cyan : nil)
                                .help(name == "FPS" ? "Passendes Ego-Modell laden und aus Spielerperspektive anzeigen (75°)." : name)
                        }
                        Toggle("Drehteller", isOn: $model.turntable).toggleStyle(.button)
                            .onChange(of: model.turntable) { model.updateTimer() }
                        Toggle("Boden", isOn: $model.floor).toggleStyle(.button)
                        Toggle("Anker", isOn: $model.sockets).toggleStyle(.button)
                    }
                    PlaybackBar(model: model, playhead: model.playhead)
                    Text(model.status).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                }.padding(12).background(.ultraThinMaterial)
            }.frame(minWidth: 560)
            Sidebar(model: model).frame(minWidth: 330, idealWidth: 360, maxWidth: 440)
        }
    }
}

struct Sidebar: View {
    @ObservedObject var model: ViewerModel
    var body: some View {
        VStack(spacing: 0) {
            HStack { Text("Cube Escape Werkzeuge").font(.title2.bold()); Spacer() }.padding(14)
            Divider()
            GeometryReader { geometry in ScrollView { content.frame(width: geometry.size.width, alignment: .leading) } }
        }
    }

    var content: some View {
        VStack(alignment: .leading, spacing: 18) {
            section("Werkzeug") {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 130))], spacing: 6) {
                    ForEach(Array(model.data.catalog.models.filter { $0.variant == "world" }), id: \.tool) { info in
                        Button(info.label) { model.selectTool(info.tool) }.frame(maxWidth: .infinity)
                            .tint(model.selected.tool == info.tool ? .cyan : nil)
                    }
                }
            }
            section("Modellvariante") {
                Picker("Variante", selection: Binding(get: { model.selected.id }, set: { id in
                    if let info = model.data.catalog.models.first(where: { $0.id == id }) { model.select(info) }
                })) {
                    ForEach(model.data.catalog.models.filter { $0.tool == model.selected.tool }) { info in
                        Text(info.variantLabel).tag(info.id)
                    }
                }.labelsHidden()
            }
            section("Oberfläche") {
                Picker("Finish", selection: $model.look.finish) {
                    ForEach(["Original", "Matt", "Lack"], id: \.self) { Text($0).tag($0) }
                }.pickerStyle(.segmented)
                ColorPicker("Verkleidung", selection: Binding(get: {
                    let color = model.look.armor ?? [0.66, 0.685, 0.72]
                    return Color(red: color[0], green: color[1], blue: color[2])
                }, set: { color in
                    if let rgb = NSColor(color).usingColorSpace(.deviceRGB) { model.look.armor = [rgb.redComponent, rgb.greenComponent, rgb.blueComponent] }
                }), supportsOpacity: false)
                HStack { Text("Leuchtstärke"); Slider(value: $model.look.glow, in: 0...3) }
                Button("Originalmaterialien") { model.look = ToolLook(model: model.selected.id) }
                HStack { Button("Als B merken") { model.rememberB() }; Button("B schließen") { model.comparison = nil }.disabled(model.comparison == nil) }
            }
            section("Animation") {
                Text(model.selected.clip ?? "Statisches Modell").font(.callout)
                Text("Aktionen starten auf Wunsch. Der Bogen spannt, löst und lädt nach; der Magnetgreifer öffnet und schließt.")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            section("Modellprüfung") {
                LabeledContent("Dreiecke", value: model.selected.triangles.formatted())
                LabeledContent("Frames", value: String(model.selected.frames))
                LabeledContent("QA", value: model.selected.qa == "roundtrip" ? "Geometrie + Reimport ✓" : "Geometrie ✓")
                Text("Unity-Import und Spielverhalten werden separat abgenommen.").font(.caption).foregroundStyle(.secondary)
            }
            section("Erzeugen") {
                Picker("Teststufe", selection: $model.tier) {
                    Text("Schnell").tag("quick"); Text("Standard").tag("standard"); Text("Vollständig").tag("full")
                }.disabled(model.busy)
                HStack {
                    Button(model.busy ? "Wird erzeugt…" : "Werkzeug erzeugen") { model.generate() }.disabled(model.busy)
                    if model.busy { ProgressView().controlSize(.small) }
                }
                Button("Ausgabeordner…") { model.chooseOutput() }.disabled(model.busy)
                if !model.console.isEmpty {
                    DisclosureGroup("Protokoll") { Text(model.console).font(.system(size: 10, design: .monospaced)).textSelection(.enabled) }
                }
            }
            section("Dateien") {
                HStack { Button("Look laden…") { model.openLook() }.keyboardShortcut("o"); Button("Look speichern…") { model.saveLook() }.keyboardShortcut("s") }
                Button("Screenshot…") { model.screenshot() }.keyboardShortcut("s", modifiers: [.command, .shift])
                Button("Modellkatalog öffnen…") { model.chooseCatalog() }
                Button("Exportordner anzeigen") { NSWorkspace.shared.open(model.data.root.appendingPathComponent(model.selected.tool)) }
            }
            Text("\(model.data.catalog.version) · \(model.data.catalog.codename)\nZiehen: drehen · Scrollen: zoomen · Leertaste: Aktion")
                .font(.caption).foregroundStyle(.secondary)
        }.padding(14).buttonStyle(.bordered)
    }

    private func section<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) { Text(title.uppercased()).font(.caption.bold()).foregroundStyle(.secondary); content() }
    }
}
