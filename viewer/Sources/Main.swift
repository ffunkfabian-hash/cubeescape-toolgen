import AppKit
import SwiftUI

@main
enum Main {
    @MainActor static func main() {
        let args = CommandLine.arguments
        if args.contains("--check-navigation") { exit(navigation(args)) }
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
            print("NAVIGATION_OK \(checks) scenarios")
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
