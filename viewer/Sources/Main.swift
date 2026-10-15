import AppKit
import SwiftUI
import simd

@main
enum Main {
    @MainActor static func main() {
        let args = CommandLine.arguments
        if args.contains("--check-navigation") { exit(navigation(args)) }
        if let out = value(args, "--sequence") { exit(sequence(out, args: args)) }
        if let out = value(args, "--snapshot") { exit(snapshot(out, args: args)) }
        if let out = value(args, "--sidebar-check") { exit(sidebar(out, args: args)) }
        ToolViewerApp.main()
    }

    static func value(_ args: [String], _ key: String) -> String? {
        guard let index = args.firstIndex(of: key), index + 1 < args.count else { return nil }
        return args[index + 1]
    }

    @MainActor static func load(_ args: [String]) throws -> ViewerModel {
        guard let root = ToolData.locate() else { throw ViewerError.invalid("ViewerData fehlt. Bitte den Generator und viewer/build.sh ausführen.") }
        let data = try ToolData(root: root)
        if let id = value(args, "--model"), !data.catalog.models.contains(where: { $0.id == id }) {
            throw ViewerError.invalid("Unbekanntes Modell: \(id)")
        }
        let model = try ViewerModel(data: data, selection: value(args, "--model"))
        if let path = value(args, "--look") {
            let look = try JSONDecoder().decode(ToolLook.self, from: Data(contentsOf: URL(fileURLWithPath: path)))
            try look.validate(catalog: data.catalog)
            model.select(data.catalog.models.first { $0.id == look.model }!); model.look = look
        }
        model.setView(value(args, "--view") ?? (model.selected.variant == "fps" ? "FPS" : "Iso"))
        if let text = value(args, "--fov") {
            guard let degrees = Double(text), ToolData.fieldOfViewRange.contains(degrees) else {
                throw ViewerError.invalid("Sichtfeld muss zwischen 35 und 75 Grad liegen.")
            }
            model.fieldOfViewOverride = degrees
        }
        let frame = Double(value(args, "--frame") ?? "1") ?? 1
        model.seek((frame - 1) / Double(max(1, model.selected.frames - 1)))
        model.floor = !args.contains("--no-floor"); model.sockets = args.contains("--sockets")
        return model
    }

    @MainActor static func snapshot(_ output: String, args: [String]) -> Int32 {
        do {
            let model = try load(args)
            let sizes = (value(args, "--size") ?? "1470x956").split(separator: "x").compactMap { Double($0) }
            guard sizes.count == 2, sizes.allSatisfy({ $0 >= 64 && $0 <= 4096 }) else { throw ViewerError.invalid("Ungültige Screenshot-Größe.") }
            try model.scene.snapshot(size: CGSize(width: sizes[0], height: sizes[1])).writePNG(URL(fileURLWithPath: output))
            if let path = value(args, "--save-look") {
                let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
                try encoder.encode(model.look).write(to: URL(fileURLWithPath: path))
            }
            print("SNAPSHOT_OK \(model.selected.id) frame=\(value(args, "--frame") ?? "1") \(output)")
            return 0
        } catch { fputs("snapshot failed: \(error.localizedDescription)\n", stderr); return 1 }
    }

    @MainActor static func sequence(_ output: String, args: [String]) -> Int32 {
        do {
            let model = try load(args)
            let rate = Double(value(args, "--rate") ?? "60") ?? 0
            guard rate >= 1 && rate <= 120 else { throw ViewerError.invalid("Bildrate muss zwischen 1 und 120 liegen.") }
            let directory = URL(fileURLWithPath: output, isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let duration = Double(model.scene.data.doc.frames - 1) / model.scene.data.doc.fps
            let count = max(1, Int(ceil(duration * rate)))
            for index in 0...count {
                try autoreleasepool {
                    model.seek(Double(index) / Double(count))
                    let path = directory.appendingPathComponent(String(format: "frame-%04d.png", index))
                    try model.scene.snapshot(size: CGSize(width: 960, height: 540)).writePNG(path)
                }
            }
            print("SEQUENCE_OK \(model.selected.id) \(count + 1) images at \(rate) fps; \(output)")
            return 0
        } catch { fputs("sequence failed: \(error.localizedDescription)\n", stderr); return 1 }
    }

    @MainActor static func sidebar(_ output: String, args: [String]) -> Int32 {
        do {
            _ = NSApplication.shared
            let model = try load(args)
            let view = Sidebar(model: model).content.environment(\.colorScheme, .dark)
            let minimum = NSHostingController(rootView: view).sizeThatFits(in: CGSize(width: 1, height: 100000)).width
            let host = NSHostingView(rootView: view); host.frame = NSRect(x: 0, y: 0, width: 360, height: 1700)
            host.layoutSubtreeIfNeeded()
            guard let bitmap = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { throw ViewerError.invalid("Seitenleiste kann nicht gerendert werden.") }
            host.cacheDisplay(in: host.bounds, to: bitmap)
            try bitmap.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: output))
            print("SIDEBAR_CHECK \(minimum.rounded()) pt / 360 pt")
            return minimum <= 360.5 ? 0 : 1
        } catch { fputs("sidebar failed: \(error.localizedDescription)\n", stderr); return 1 }
    }

    @MainActor static func navigation(_ args: [String]) -> Int32 {
        do {
            let model = try load(args)
            func require(_ condition: Bool, _ message: String) throws {
                if !condition { throw ViewerError.invalid(message) }
            }
            var checks = 0
            for world in model.data.catalog.models where world.variant == "world" {
                model.select(world)
                model.look.finish = "Matt"
                model.rememberB()
                model.setView("FPS")
                try require(model.selected.tool == world.tool && model.selected.variant == "fps" && model.viewName == "FPS",
                            "Ego button did not select the matching FPS model: \(world.id)")
                let expected = try ModelData(directory: model.data.directory(model.selected))
                try require(model.comparison?.data.doc.nodes.first?.name == expected.doc.nodes.first?.name,
                            "B still uses the world model in Ego view: \(world.id)")
                try require(model.look.finish == "Matt", "Ego switch discarded the material look")
                model.seek(0.3)
                model.setView("FPS")
                try require(abs(model.playhead.fraction - 0.3) < 0.0001, "Repeated Ego click reset the animation")
                model.setView("Front")
                try require(model.selected.variant == "fps" && model.viewName == "Front", "FPS inspection selected another asset")
                checks += 1
            }
            for info in model.data.catalog.models where info.variant != "fps" {
                model.select(info)
                try require(model.viewName == "Iso", "World/arrow selection did not restore overview")
                model.setView("FPS")
                for tool in Set(model.data.catalog.models.map(\.tool)) {
                    model.selectTool(tool)
                    try require(model.selected.tool == tool && model.selected.variant == "fps" && model.viewName == "FPS",
                                "Tool switch lost Ego mode: \(tool)")
                }
                checks += 1
            }
            model.select(model.data.catalog.models.first { $0.id == "bow/fps" }!)
            guard let motion = model.scene.root.childNode(withName: "Viewmodel_Motion", recursively: true) else {
                throw ViewerError.invalid("FPS motion node missing")
            }
            model.seek(14.0 / 96); let first = motion.simdPosition
            model.seek(15.0 / 96); let last = motion.simdPosition
            model.seek(14.5 / 96); let middle = motion.simdPosition
            try require(simd_distance(first, last) > 0.00001 && simd_distance(middle, (first + last) / 2) < 0.000001,
                        "Viewer must interpolate between baked animation frames")
            guard let arrow = model.scene.root.childNode(withName: "LoadedArrowPresence", recursively: true) else {
                throw ViewerError.invalid("Arrow visibility node missing")
            }
            model.seek(42.5 / 96)
            try require(abs(arrow.simdScale.x - 1) < 0.0001, "Visibility events must not shrink the arrow between frames")
            model.seek(43.0 / 96)
            try require(abs(arrow.simdScale.x - 0.001) < 0.0001, "Arrow was not hidden on the release frame")
            checks += 1
            // Ego field of view: data default per tool, override, A/B, reset, clamping, no idle timer.
            for info in model.data.catalog.models where info.variant == "fps" {
                model.select(info)
                let expected = model.data.fieldOfView(tool: info.tool)
                guard let camera = model.scene.camera.camera else { throw ViewerError.invalid("Camera missing") }
                try require(model.fieldOfViewOverride == nil && abs(model.fieldOfView - expected) < 1e-9 &&
                            camera.projectionDirection == .vertical && abs(Double(camera.fieldOfView) - expected) < 1e-3,
                            "Ego view does not use the data FOV: \(info.id)")
                model.fieldOfViewOverride = 60
                model.rememberB()
                try require(abs(Double(camera.fieldOfView) - 60) < 1e-3 &&
                            abs(Double(model.comparison?.camera.camera?.fieldOfView ?? 0) - 60) < 1e-3,
                            "FOV override did not reach A and B: \(info.id)")
                try require(!model.timerActive, "FOV slider must not start a timer")
                model.fieldOfViewOverride = 200
                try require(abs(Double(camera.fieldOfView) - ToolData.fieldOfViewRange.upperBound) < 1e-3, "FOV is not clamped")
                model.resetFieldOfView(); model.comparison = nil
                try require(abs(Double(camera.fieldOfView) - expected) < 1e-3, "FOV reset did not restore the data value")
                checks += 1
            }
            try require(ModelInfo.label("game") == "Spielmodell" && ModelInfo.label("fps") == "Egoperspektive",
                        "Variant labels changed")
            for info in model.data.catalog.models where info.variant == "game" {
                model.select(info)
                try require(model.viewName == "Iso" && model.selected.variantLabel == "Spielmodell", "Game model selection failed")
                model.setView("FPS")
                try require(model.selected.tool == info.tool && model.selected.variant == "fps", "Ego from game model failed")
                checks += 1
            }
            for available in [CGSize(width: 560, height: 700), CGSize(width: 1200, height: 400), CGSize(width: 960, height: 540)] {
                let viewport = ToolScene.viewportSize(available: available, firstPerson: true)
                try require(abs(viewport.width / viewport.height - 16.0 / 9) < 0.000001 &&
                            viewport.width <= available.width && viewport.height <= available.height,
                            "Ego viewport must retain its authored 16:9 framing")
                try require(ToolScene.viewportSize(available: available, firstPerson: false) == available,
                            "Orbit viewport must fill its available area")
            }
            checks += 1
            print("NAVIGATION_OK \(checks) scenarios, including subframe interpolation")
            return 0
        } catch { fputs("navigation failed: \(error.localizedDescription)\n", stderr); return 1 }
    }
}

struct ToolViewerApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    var body: some Scene {
        WindowGroup("Cube Escape – Toolgen") {
            ViewerRoot().frame(minWidth: 1100, minHeight: 720).preferredColorScheme(.dark)
        }.windowStyle(.titleBar)
    }
}

@MainActor
final class Startup: ObservableObject {
    let model: ViewerModel?
    let error: String?
    init() {
        do { model = try Main.load(CommandLine.arguments); error = nil }
        catch { model = nil; self.error = error.localizedDescription }
    }
}

struct ViewerRoot: View {
    @StateObject private var startup = Startup()
    var body: some View {
        if let model = startup.model { ContentView(model: model) }
        else { Text(startup.error ?? "Modellkatalog konnte nicht geladen werden.").padding(40) }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps: true)
        if let size = Main.value(CommandLine.arguments, "--window") {
            let parts = size.split(separator: "x").compactMap { Double($0) }
            if parts.count == 2 {
                DispatchQueue.main.async { NSApp.windows.first?.setContentSize(NSSize(width: parts[0], height: parts[1])) }
            }
        }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}
