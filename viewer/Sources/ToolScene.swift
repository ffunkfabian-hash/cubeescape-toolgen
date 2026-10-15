import AppKit
import Metal
import SceneKit
import simd

@MainActor
final class ToolScene {
    static let views = ["Iso", "Front", "Seite", "Hinten", "FPS"]
    let data: ModelData
    let scene = SCNScene()
    let root = SCNNode()
    let camera = SCNNode()
    private var nodes: [SCNNode] = []
    private var materials: [SCNMaterial] = []
    private var morphers: [(SCNMorpher, [TargetInfo])] = []
    private let floor = SCNNode()
    private var sockets: [SCNNode] = []
    private var center = SCNVector3Zero
    private var span: Float = 1
    private(set) var currentView = "Iso"
    private(set) var cameraRevision = 0

    init(data: ModelData) {
        self.data = data
        scene.background.contents = NSColor(calibratedRed: 0.075, green: 0.085, blue: 0.11, alpha: 1)
        scene.rootNode.addChildNode(root)
        for info in data.doc.materials {
            let material = SCNMaterial()
            material.name = info.name
            material.lightingModel = .physicallyBased
            materials.append(material)
        }
        nodes = data.doc.nodes.map { info in let node = SCNNode(); node.name = info.name; return node }
        for (i, info) in data.doc.nodes.enumerated() {
            (info.parent.map { nodes[$0] } ?? root).addChildNode(nodes[i])
        }
        for part in data.doc.parts {
            let geometry = mesh(part, offset: part.vertexOffset)
            geometry.materials = [materials[part.material]]
            let node = SCNNode(geometry: geometry)
            if !part.targets.isEmpty {
                let morpher = SCNMorpher()
                morpher.calculationMode = .normalized
                morpher.targets = part.targets.map { mesh(part, offset: $0.vertexOffset) }
                node.morpher = morpher
                morphers.append((morpher, part.targets))
            }
            nodes[part.node].addChildNode(node)
        }
        for (i, info) in data.doc.nodes.enumerated() where info.name.hasPrefix("Socket_") || info.name == "Muzzle" {
            let sphere = SCNSphere(radius: 0.008)
            sphere.segmentCount = 8
            sphere.firstMaterial?.diffuse.contents = NSColor.systemOrange
            sphere.firstMaterial?.lightingModel = .constant
            let marker = SCNNode(geometry: sphere)
            marker.isHidden = true
            nodes[i].addChildNode(marker)
            sockets.append(marker)
        }
        let low = data.doc.bounds[0], high = data.doc.bounds[1]
        center = SCNVector3((low[0] + high[0]) / 2, (low[1] + high[1]) / 2, (low[2] + high[2]) / 2)
        span = max(high[0] - low[0], max(high[1] - low[1], high[2] - low[2]))
        let plane = SCNFloor()
        plane.reflectivity = 0
        plane.firstMaterial?.diffuse.contents = NSColor(calibratedWhite: 0.12, alpha: 1)
        plane.firstMaterial?.roughness.contents = 1
        floor.geometry = plane
        floor.position.y = CGFloat(low[1]) - 0.015
        scene.rootNode.addChildNode(floor)
        let ambient = SCNNode(); ambient.light = SCNLight(); ambient.light?.type = .ambient
        ambient.light?.intensity = 180
        scene.rootNode.addChildNode(ambient)
        for (position, intensity) in [(SCNVector3(2, 3, 4), 650.0), (SCNVector3(-3, 1, -2), 300.0)] {
            let light = SCNNode(); light.light = SCNLight(); light.light?.type = .omni
            light.light?.intensity = intensity; light.position = position
            scene.rootNode.addChildNode(light)
        }
        camera.camera = SCNCamera()
        camera.camera?.zNear = 0.01; camera.camera?.zFar = 100
        camera.camera?.wantsHDR = true; camera.camera?.bloomIntensity = 0.15
        camera.camera?.bloomThreshold = 1.5
        scene.rootNode.addChildNode(camera)
        seek(0)
        apply(ToolLook())
        setView("Iso")
    }

    private func mesh(_ part: PartInfo, offset: Int) -> SCNGeometry {
        let sources = [(SCNGeometrySource.Semantic.vertex, 3, 0), (.normal, 3, 12), (.texcoord, 2, 24)].map {
            SCNGeometrySource(data: data.vertices, semantic: $0.0, vectorCount: part.vertexCount,
                usesFloatComponents: true, componentsPerVector: $0.1, bytesPerComponent: 4,
                dataOffset: offset * 32 + $0.2, dataStride: 32)
        }
        let start = part.indexOffset * 4
        let element = SCNGeometryElement(data: data.indices.subdata(in: start..<(start + part.indexCount * 4)),
                                        primitiveType: .triangles, primitiveCount: part.indexCount / 3, bytesPerIndex: 4)
        return SCNGeometry(sources: sources, elements: [element])
    }

    func seek(_ fraction: Double) {
        let frame = min(data.doc.frames - 1, max(0, Int((fraction * Double(data.doc.frames - 1)).rounded())))
        let start = frame * data.doc.floatsPerFrame
        SCNTransaction.begin(); SCNTransaction.disableActions = true
        for (index, node) in nodes.enumerated() {
            let i = start + index * 10
            node.simdPosition = SIMD3(data.animation[i], data.animation[i + 1], data.animation[i + 2])
            node.simdOrientation = simd_quatf(ix: data.animation[i + 3], iy: data.animation[i + 4],
                                            iz: data.animation[i + 5], r: data.animation[i + 6])
            node.simdScale = SIMD3(data.animation[i + 7], data.animation[i + 8], data.animation[i + 9])
        }
        let weights = start + nodes.count * 10
        for (morpher, targets) in morphers {
            for (index, target) in targets.enumerated() {
                morpher.setWeight(CGFloat(data.animation[weights + target.weight]), forTargetAt: index)
            }
        }
        SCNTransaction.commit()
    }

    func apply(_ look: ToolLook) {
        for (index, material) in materials.enumerated() {
            let source = data.doc.materials[index]
            let armor = source.name.localizedCaseInsensitiveContains("armor") || source.name.localizedCaseInsensitiveContains("white")
            let color = armor ? look.armor ?? Array(source.color.prefix(3)) : Array(source.color.prefix(3))
            material.diffuse.contents = NSColor(calibratedRed: color[0], green: color[1], blue: color[2], alpha: source.color[3])
            material.metalness.contents = source.metallic
            material.roughness.contents = look.finish == "Matt" ? max(0.65, source.roughness) : look.finish == "Lack" ? 0.12 : source.roughness
            material.emission.contents = NSColor(calibratedRed: source.emission[0], green: source.emission[1], blue: source.emission[2], alpha: 1)
            material.emission.intensity = CGFloat(source.strength * look.glow)
        }
    }

    func setView(_ name: String) {
        cameraRevision += 1
        currentView = name
        root.eulerAngles = SCNVector3Zero
        let cam = camera.camera!
        cam.usesOrthographicProjection = name != "FPS"
        cam.orthographicScale = Double(max(span * 0.90, 0.2))
        cam.projectionDirection = .horizontal; cam.fieldOfView = 75
        if name == "FPS" {
            camera.position = SCNVector3Zero
            camera.eulerAngles = SCNVector3(0, CGFloat.pi, 0)
            cam.zNear = 0.03
        } else {
            cam.zNear = 0.01
            let offset: SCNVector3
            switch name {
            case "Front": offset = SCNVector3(0, 0, 3 * span)
            case "Seite": offset = SCNVector3(3 * span, 0, 0)
            case "Hinten": offset = SCNVector3(0, 0, -3 * span)
            default: offset = SCNVector3(2 * span, 1.3 * span, 2 * span)
            }
            camera.position = SCNVector3(center.x + offset.x, center.y + offset.y, center.z + offset.z)
            camera.look(at: center)
        }
        floor.isHidden = name == "FPS"
    }

    func showFloor(_ show: Bool) { floor.isHidden = !show || currentView == "FPS" }
    func showSockets(_ show: Bool) { for node in sockets { node.isHidden = !show } }
    func turn(_ radians: Float) { root.eulerAngles.y += CGFloat(radians) }

    func snapshot(size: CGSize) throws -> NSImage {
        guard let device = MTLCreateSystemDefaultDevice() else { throw ViewerError.invalid("Metal ist nicht verfügbar.") }
        let renderer = SCNRenderer(device: device, options: nil)
        renderer.scene = scene; renderer.pointOfView = camera
        return renderer.snapshot(atTime: 0, with: size, antialiasingMode: .multisampling4X)
    }
}

extension NSImage {
    func writePNG(_ url: URL) throws {
        guard let tiff = tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
              let png = bitmap.representation(using: .png, properties: [:]) else {
            throw ViewerError.invalid("Screenshot konnte nicht gespeichert werden.")
        }
        try png.write(to: url)
    }
}
