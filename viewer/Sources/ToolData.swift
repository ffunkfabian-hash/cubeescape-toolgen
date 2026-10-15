import Foundation

struct Catalog: Decodable {
    let format: Int
    let version: String
    let codename: String
    let models: [ModelInfo]
}

struct ModelInfo: Decodable, Identifiable, Hashable {
    let id: String
    let tool: String
    let label: String
    let variant: String
    let path: String
    let asset: String
    let clip: String?
    let triangles: Int
    let frames: Int
    let qa: String
    var variantLabel: String { variant == "fps" ? "Egoperspektive" : variant == "arrow" ? "Pfeil" : "Weltmodell" }
}

struct NodeInfo: Decodable {
    let name: String
    let parent: Int?
    let rest: [Float]
    let stepScale: Bool?
}
struct TargetInfo: Decodable { let weight: Int; let vertexOffset: Int }
struct PartInfo: Decodable {
    let node: Int
    let material: Int
    let vertexOffset: Int
    let vertexCount: Int
    let indexOffset: Int
    let indexCount: Int
    let targets: [TargetInfo]
}
struct MaterialInfo: Decodable {
    let name: String
    let color: [Double]
    let metallic: Double
    let roughness: Double
    let emission: [Double]
    let strength: Double
}
struct MorphInfo: Decodable { let node: Int; let name: String }
struct SceneDoc: Decodable {
    let format: Int
    let vertexStride: Int
    let fps: Double
    let frames: Int
    let clip: String?
    let autoplay: Bool
    let loop: Bool
    let nodes: [NodeInfo]
    let parts: [PartInfo]
    let materials: [MaterialInfo]
    let morphs: [MorphInfo]
    let bounds: [[Float]]
    let floatsPerFrame: Int
    let triangles: Int
}

enum ViewerError: LocalizedError {
    case invalid(String)
    var errorDescription: String? { if case .invalid(let text) = self { return text }; return nil }
}

struct ToolLook: Codable {
    var format = "CubeEscapeToolLook"
    var version = 1
    var model = "portal_emitter/world"
    var finish = "Original"
    var armor: [Double]? = nil
    var glow = 1.0

    func validate(catalog: Catalog) throws {
        guard format == "CubeEscapeToolLook", version == 1 else {
            throw ViewerError.invalid("Unbekanntes Look-Format oder neuere Version.")
        }
        guard catalog.models.contains(where: { $0.id == model }), ["Original", "Matt", "Lack"].contains(finish),
              glow.isFinite, (0...3).contains(glow),
              armor == nil || (armor!.count == 3 && armor!.allSatisfy { $0.isFinite && (0...1).contains($0) }) else {
            throw ViewerError.invalid("Der Look enthält unbekannte Modelle oder ungültige Materialwerte.")
        }
    }
}

final class ToolData {
    let root: URL
    let catalog: Catalog
    init(root: URL) throws {
        self.root = root
        catalog = try JSONDecoder().decode(Catalog.self, from: Data(contentsOf: root.appendingPathComponent("catalog.json")))
        guard catalog.format == 1, !catalog.models.isEmpty,
              Set(catalog.models.map(\.id)).count == catalog.models.count else {
            throw ViewerError.invalid("Modellkatalog fehlt, ist leer oder hat ein unbekanntes Format.")
        }
        for info in catalog.models { _ = try directory(info) }
    }

    func directory(_ info: ModelInfo) throws -> URL {
        let path = root.appendingPathComponent(info.path).standardizedFileURL.resolvingSymlinksInPath()
        let base = root.standardizedFileURL.resolvingSymlinksInPath().path + "/"
        guard path.path.hasPrefix(base) else { throw ViewerError.invalid("Modellpfad liegt außerhalb des Katalogs.") }
        return path
    }

    static func locate() -> URL? {
        let args = CommandLine.arguments
        if let index = args.firstIndex(of: "--data"), index + 1 < args.count {
            return URL(fileURLWithPath: args[index + 1], isDirectory: true)
        }
        if let path = ProcessInfo.processInfo.environment["TOOLGEN_DATA"] { return URL(fileURLWithPath: path) }
        if let resource = Bundle.main.resourceURL?.appendingPathComponent("ViewerData"),
           FileManager.default.fileExists(atPath: resource.appendingPathComponent("catalog.json").path) { return resource }
        return nil
    }
}

final class ModelData {
    let doc: SceneDoc
    let vertices: Data
    let indices: Data
    let animation: [Float]
    init(directory: URL) throws {
        doc = try JSONDecoder().decode(SceneDoc.self, from: Data(contentsOf: directory.appendingPathComponent("scene.json")))
        vertices = try Data(contentsOf: directory.appendingPathComponent("vertices.bin"))
        indices = try Data(contentsOf: directory.appendingPathComponent("indices.bin"))
        let buffer = try Data(contentsOf: directory.appendingPathComponent("anim.bin"))
        guard buffer.count % 4 == 0 else { throw ViewerError.invalid("Animationspuffer ist unvollständig.") }
        animation = buffer.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
        guard doc.format == 1, doc.vertexStride == 8, doc.frames > 0, doc.fps > 0, doc.fps.isFinite,
              !doc.nodes.isEmpty, !doc.parts.isEmpty, !doc.materials.isEmpty,
              doc.floatsPerFrame == doc.nodes.count * 10 + doc.morphs.count,
              animation.count == doc.frames * doc.floatsPerFrame, animation.allSatisfy(\.isFinite),
              doc.bounds.count == 2, doc.bounds.allSatisfy({ $0.count == 3 && $0.allSatisfy(\.isFinite) }),
              vertices.count % 32 == 0, indices.count % 4 == 0 else {
            throw ViewerError.invalid("Modelldaten sind beschädigt oder verwenden ein unbekanntes Format.")
        }
        for (index, node) in doc.nodes.enumerated() {
            guard node.rest.count == 10, node.rest.allSatisfy(\.isFinite),
                  node.parent == nil || (node.parent! >= 0 && node.parent! < doc.nodes.count && node.parent != index) else {
                throw ViewerError.invalid("Ungültige Modellhierarchie.")
            }
        }
        for (index, node) in doc.nodes.enumerated() {
            var visited = Set<Int>([index]); var parent = node.parent
            while let current = parent {
                guard visited.insert(current).inserted else { throw ViewerError.invalid("Zyklische Modellhierarchie.") }
                parent = doc.nodes[current].parent
            }
        }
        let finiteVertices = vertices.withUnsafeBytes { raw in
            stride(from: 0, to: raw.count, by: 4).allSatisfy { raw.loadUnaligned(fromByteOffset: $0, as: Float.self).isFinite }
        }
        guard finiteVertices else { throw ViewerError.invalid("Mesh-Puffer enthält ungültige Werte.") }
        for material in doc.materials {
            guard material.color.count == 4, material.emission.count == 4,
                  (material.color + material.emission + [material.metallic, material.roughness, material.strength]).allSatisfy(\.isFinite) else {
                throw ViewerError.invalid("Ungültiges Material.")
            }
        }
        for part in doc.parts {
            guard part.node >= 0, part.node < doc.nodes.count, part.material >= 0, part.material < doc.materials.count,
                  part.vertexOffset >= 0, part.vertexCount > 0, part.indexOffset >= 0, part.indexCount > 0,
                  part.indexCount % 3 == 0, part.vertexOffset <= vertices.count / 32 - part.vertexCount,
                  part.indexOffset <= indices.count / 4 - part.indexCount,
                  part.targets.allSatisfy({ $0.weight >= 0 && $0.weight < doc.morphs.count && $0.vertexOffset >= 0 &&
                      $0.vertexOffset <= vertices.count / 32 - part.vertexCount }) else {
                throw ViewerError.invalid("Ungültige Mesh-Puffergrenzen.")
            }
            let validIndices = indices.withUnsafeBytes { raw in
                (part.indexOffset..<(part.indexOffset + part.indexCount)).allSatisfy {
                    raw.loadUnaligned(fromByteOffset: $0 * 4, as: UInt32.self) < part.vertexCount
                }
            }
            guard validIndices else { throw ViewerError.invalid("Mesh-Index liegt außerhalb des Vertex-Puffers.") }
        }
    }
}
