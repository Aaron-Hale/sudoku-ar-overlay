import SwiftUI
import Combine
import ARKit
import SceneKit
import UIKit
import CoreImage
import Foundation
import simd

struct SolveResponse: Decodable {
    let status: String
    let message: String?
    let latencyMs: Double?
    let confidence: Double?
    let imageWidth: Int?
    let imageHeight: Int?
    let givensCount: Int?
    let cornersPx: [[Double]]?
    let givens: [[Int]]?
    let solution: [[Int]]?

    enum CodingKeys: String, CodingKey {
        case status
        case message
        case latencyMs = "latency_ms"
        case confidence
        case imageWidth = "image_width"
        case imageHeight = "image_height"
        case givensCount = "givens_count"
        case cornersPx = "corners_px"
        case givens
        case solution
    }
}

struct SolveFrameLock {
    let inverseViewMatrix: simd_float4x4
    let inverseProjectionMatrix: simd_float4x4
    let viewportSize: CGSize
    let planePoint: SIMD3<Float>
    let planeNormal: SIMD3<Float>
}

final class SolverClient {
    let baseURL = URL(string: "http://192.168.1.74:8000")!

    func solve(imageJPEG: Data) async throws -> SolveResponse {
        let url = baseURL.appendingPathComponent("solve")
        var request = URLRequest(url: url, timeoutInterval: 25)
        request.httpMethod = "POST"

        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()

        body.appendMultipartField(
            name: "metadata_json",
            value: #"{"source":"SudokuAROverlay ARSCNView snapshot"}"#,
            boundary: boundary
        )

        body.appendMultipartFile(
            name: "image",
            filename: "arkit_view_snapshot.jpg",
            mimeType: "image/jpeg",
            data: imageJPEG,
            boundary: boundary
        )

        body.appendString("--\(boundary)--\r\n")
        request.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        guard (200..<300).contains(http.statusCode) else {
            let text = String(data: data, encoding: .utf8) ?? "<no response body>"
            throw NSError(domain: "SolverClient", code: http.statusCode, userInfo: [
                NSLocalizedDescriptionKey: "HTTP \(http.statusCode): \(text)"
            ])
        }

        return try JSONDecoder().decode(SolveResponse.self, from: data)
    }
}

extension Data {
    mutating func appendString(_ value: String) {
        append(value.data(using: .utf8)!)
    }

    mutating func appendMultipartField(name: String, value: String, boundary: String) {
        appendString("--\(boundary)\r\n")
        appendString("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
        appendString("\(value)\r\n")
    }

    mutating func appendMultipartFile(
        name: String,
        filename: String,
        mimeType: String,
        data: Data,
        boundary: String
    ) {
        appendString("--\(boundary)\r\n")
        appendString("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\n")
        appendString("Content-Type: \(mimeType)\r\n\r\n")
        append(data)
        appendString("\r\n")
    }
}

@MainActor
final class AppState: ObservableObject {
    weak var sceneView: ARSCNView?

    @Published var statusText: String = "Tap center of puzzle to solve"
    @Published var isSolving: Bool = false
    @Published var lastSolveResponse: SolveResponse?

    private let solverClient = SolverClient()
    private var pendingSolveFrameLock: SolveFrameLock?
    private var worldSolutionNode: SCNNode?

    func sendCurrentFrameToSolver(tapPoint: CGPoint? = nil) {
        guard !isSolving else { return }

        guard let sceneView,
              let frame = sceneView.session.currentFrame else {
            statusText = "No AR frame available yet."
            return
        }

        let lockPoint = tapPoint ?? CGPoint(
            x: sceneView.bounds.width / 2.0,
            y: sceneView.bounds.height / 2.0
        )

        guard let lock = makeSolveFrameLock(
            frame: frame,
            sceneView: sceneView,
            lockPoint: lockPoint
        ) else {
            statusText = "Could not lock table plane. Move slowly, then tap puzzle center again."
            return
        }

        pendingSolveFrameLock = lock

        // Clear old overlay before snapshot so the solver does not see old blue digits.
        worldSolutionNode?.removeFromParentNode()
        worldSolutionNode = nil

        let snapshot = sceneView.snapshot()

        guard let jpeg = snapshot.jpegData(compressionQuality: 0.90) else {
            statusText = "Could not create AR view snapshot JPEG."
            return
        }

        isSolving = true
        statusText = "Frame/table locked at tap point. Solving..."

        Task {
            defer {
                isSolving = false
            }

            do {
                let response = try await solverClient.solve(imageJPEG: jpeg)
                lastSolveResponse = response

                let latency = response.latencyMs.map { String(format: "%.0f ms", $0) } ?? "n/a"
                let givens = response.givensCount.map { "\($0)" } ?? "n/a"

                guard response.status == "solved" else {
                    statusText = "Solver failed: \(response.message ?? "no message")"
                    return
                }

                let placed = placeWorldSolutionOverlay(response)
                if placed {
                    statusText = "Solved | \(latency) | givens \(givens)"
                }
            } catch {
                statusText = "Solver call failed: \(error.localizedDescription)"
            }
        }
    }

    private func currentInterfaceOrientation() -> UIInterfaceOrientation {
        if let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene {
            return scene.interfaceOrientation
        }
        return .portrait
    }

    private func makeSolveFrameLock(
        frame: ARFrame,
        sceneView: ARSCNView,
        lockPoint: CGPoint
    ) -> SolveFrameLock? {
        let viewSize = sceneView.bounds.size
        let orientation = currentInterfaceOrientation()

        // Lock the physical plane at the user's tap point, not just screen center.
        // The user should tap near the center of the Sudoku puzzle.
        let primaryQuery = sceneView.raycastQuery(
            from: lockPoint,
            allowing: .estimatedPlane,
            alignment: .horizontal
        )

        let fallbackCenter = CGPoint(x: viewSize.width / 2.0, y: viewSize.height / 2.0)
        let fallbackQuery = sceneView.raycastQuery(
            from: fallbackCenter,
            allowing: .estimatedPlane,
            alignment: .horizontal
        )

        let hit =
            primaryQuery.flatMap { sceneView.session.raycast($0).first } ??
            fallbackQuery.flatMap { sceneView.session.raycast($0).first }

        guard let hit else {
            return nil
        }

        let projection = frame.camera.projectionMatrix(
            for: orientation,
            viewportSize: viewSize,
            zNear: 0.001,
            zFar: 10.0
        )

        let view = frame.camera.viewMatrix(for: orientation)

        let transform = hit.worldTransform
        let planePoint = transform.translation

        var normal = SIMD3<Float>(
            transform.columns.1.x,
            transform.columns.1.y,
            transform.columns.1.z
        )

        if simd_length(normal) < 0.001 {
            normal = SIMD3<Float>(0, 1, 0)
        } else {
            normal = simd_normalize(normal)
        }

        return SolveFrameLock(
            inverseViewMatrix: simd_inverse(view),
            inverseProjectionMatrix: simd_inverse(projection),
            viewportSize: viewSize,
            planePoint: planePoint,
            planeNormal: normal
        )
    }

    private func placeWorldSolutionOverlay(_ response: SolveResponse) -> Bool {
        guard let sceneView else {
            statusText += " | no scene view"
            return false
        }

        guard let lock = pendingSolveFrameLock else {
            statusText += " | no locked geometry"
            return false
        }

        guard let corners = response.cornersPx,
              corners.count == 4,
              let imageWidth = response.imageWidth,
              let imageHeight = response.imageHeight,
              let givens = response.givens,
              let solution = response.solution else {
            statusText += " | missing response geometry"
            return false
        }

        let imageSize = CGSize(width: CGFloat(imageWidth), height: CGFloat(imageHeight))

        // Because we send sceneView.snapshot(), solver pixel coordinates map directly
        // to the ARSCNView bounds by scaling.
        let screenCorners: [CGPoint] = corners.map { c in
            let p = CGPoint(x: CGFloat(c[0]), y: CGFloat(c[1]))
            return snapshotImagePointToViewPoint(
                p,
                imageSize: imageSize,
                viewSize: lock.viewportSize
            )
        }

        guard screenCorners.count == 4 else {
            statusText += " | bad corner count"
            return false
        }

        var worldCorners: [SIMD3<Float>] = []

        for p in screenCorners {
            guard let wp = worldPointOnLockedPlane(screenPoint: p, lock: lock) else {
                statusText += " | corner plane intersection failed"
                return false
            }
            worldCorners.append(wp)
        }

        guard worldCorners.count == 4 else {
            statusText += " | bad world corner count"
            return false
        }

        worldSolutionNode?.removeFromParentNode()

        let node = makePerCellWorldSolutionNode(
            topLeft: worldCorners[0],
            topRight: worldCorners[1],
            bottomRight: worldCorners[2],
            bottomLeft: worldCorners[3],
            givens: givens,
            solution: solution,
            planeNormal: lock.planeNormal
        )

        sceneView.scene.rootNode.addChildNode(node)
        worldSolutionNode = node

        return true
    }

    private func snapshotImagePointToViewPoint(
        _ p: CGPoint,
        imageSize: CGSize,
        viewSize: CGSize
    ) -> CGPoint {
        let x = p.x / max(imageSize.width, 1.0) * viewSize.width
        let y = p.y / max(imageSize.height, 1.0) * viewSize.height
        return CGPoint(x: x, y: y)
    }

    private func worldPointOnLockedPlane(screenPoint: CGPoint, lock: SolveFrameLock) -> SIMD3<Float>? {
        guard lock.viewportSize.width > 1, lock.viewportSize.height > 1 else {
            return nil
        }

        let ndcX = Float((screenPoint.x / lock.viewportSize.width) * 2.0 - 1.0)
        let ndcY = Float(1.0 - (screenPoint.y / lock.viewportSize.height) * 2.0)

        if let p = intersectLockedPlane(ndcX: ndcX, ndcY: ndcY, nearZ: 0.0, farZ: 1.0, lock: lock) {
            return p
        }

        return intersectLockedPlane(ndcX: ndcX, ndcY: ndcY, nearZ: -1.0, farZ: 1.0, lock: lock)
    }

    private func intersectLockedPlane(
        ndcX: Float,
        ndcY: Float,
        nearZ: Float,
        farZ: Float,
        lock: SolveFrameLock
    ) -> SIMD3<Float>? {
        var nearCamera = lock.inverseProjectionMatrix * SIMD4<Float>(ndcX, ndcY, nearZ, 1.0)
        var farCamera = lock.inverseProjectionMatrix * SIMD4<Float>(ndcX, ndcY, farZ, 1.0)

        nearCamera = nearCamera / nearCamera.w
        farCamera = farCamera / farCamera.w

        let nearWorld4 = lock.inverseViewMatrix * SIMD4<Float>(
            nearCamera.x,
            nearCamera.y,
            nearCamera.z,
            1.0
        )

        let farWorld4 = lock.inverseViewMatrix * SIMD4<Float>(
            farCamera.x,
            farCamera.y,
            farCamera.z,
            1.0
        )

        let origin = SIMD3<Float>(nearWorld4.x, nearWorld4.y, nearWorld4.z)
        let far = SIMD3<Float>(farWorld4.x, farWorld4.y, farWorld4.z)
        let direction = simd_normalize(far - origin)

        let denom = simd_dot(direction, lock.planeNormal)
        if Swift.abs(denom) < 0.00001 {
            return nil
        }

        let t = simd_dot(lock.planePoint - origin, lock.planeNormal) / denom
        if t < 0 {
            return nil
        }

        return origin + direction * t
    }

    private func makePerCellWorldSolutionNode(
        topLeft: SIMD3<Float>,
        topRight: SIMD3<Float>,
        bottomRight: SIMD3<Float>,
        bottomLeft: SIMD3<Float>,
        givens: [[Int]],
        solution: [[Int]],
        planeNormal: SIMD3<Float>
    ) -> SCNNode {
        let root = SCNNode()

        let topEdge = topRight - topLeft
        let bottomEdge = bottomRight - bottomLeft
        let leftEdge = bottomLeft - topLeft
        let rightEdge = bottomRight - topRight

        let width = (simd_length(topEdge) + simd_length(bottomEdge)) / 2.0
        let height = (simd_length(leftEdge) + simd_length(rightEdge)) / 2.0

        guard width > 0.001, height > 0.001 else {
            return root
        }

        let xAxisRaw = topEdge + bottomEdge
        let zAxisRaw = leftEdge + rightEdge

        var xAxis = simd_length(xAxisRaw) > 0.001 ? simd_normalize(xAxisRaw) : SIMD3<Float>(1, 0, 0)
        var zAxis = simd_length(zAxisRaw) > 0.001 ? simd_normalize(zAxisRaw) : SIMD3<Float>(0, 0, 1)
        var normal = simd_length(planeNormal) > 0.001 ? simd_normalize(planeNormal) : simd_normalize(simd_cross(zAxis, xAxis))

        // Keep axes mutually coherent so planes are flat and readable.
        zAxis = simd_normalize(simd_cross(xAxis, normal))
        xAxis = simd_normalize(simd_cross(normal, zAxis))

        if simd_dot(simd_cross(xAxis, zAxis), normal) < 0 {
            normal = -normal
        }

        let digitPlaneWidth = width / 9.0 * 0.72
        let digitPlaneHeight = height / 9.0 * 0.72

        for r in 0..<9 {
            for c in 0..<9 {
                let given = givens[safe: r]?[safe: c] ?? 0
                let value = solution[safe: r]?[safe: c] ?? 0

                if given == 0 && value != 0 {
                    let u = (Float(c) + 0.5) / 9.0
                    let v = (Float(r) + 0.5) / 9.0

                    let cellWorld = bilinear3D(
                        topLeft: topLeft,
                        topRight: topRight,
                        bottomRight: bottomRight,
                        bottomLeft: bottomLeft,
                        u: u,
                        v: v
                    )

                    let digit = makeDigitNode(value, width: digitPlaneWidth, height: digitPlaneHeight)
                    let pos = cellWorld + normal * 0.00008
                    digit.simdTransform = flatPlaneTransform(
                        position: pos,
                        xAxis: xAxis,
                        yAxis: zAxis,
                        normal: normal
                    )

                    root.addChildNode(digit)
                }
            }
        }

        return root
    }

    private func bilinear3D(
        topLeft: SIMD3<Float>,
        topRight: SIMD3<Float>,
        bottomRight: SIMD3<Float>,
        bottomLeft: SIMD3<Float>,
        u: Float,
        v: Float
    ) -> SIMD3<Float> {
        let top = topLeft + (topRight - topLeft) * u
        let bottom = bottomLeft + (bottomRight - bottomLeft) * u
        return top + (bottom - top) * v
    }

    private func flatPlaneTransform(
        position: SIMD3<Float>,
        xAxis: SIMD3<Float>,
        yAxis: SIMD3<Float>,
        normal: SIMD3<Float>
    ) -> simd_float4x4 {
        var m = matrix_identity_float4x4
        m.columns.0 = SIMD4<Float>(xAxis.x, xAxis.y, xAxis.z, 0)
        m.columns.1 = SIMD4<Float>(yAxis.x, yAxis.y, yAxis.z, 0)
        m.columns.2 = SIMD4<Float>(normal.x, normal.y, normal.z, 0)
        m.columns.3 = SIMD4<Float>(position.x, position.y, position.z, 1)
        return m
    }

    private func makeDigitNode(_ value: Int, width: Float, height: Float) -> SCNNode {
        let plane = SCNPlane(width: CGFloat(width), height: CGFloat(height))
        let digitImage = makeDigitTexture(value)

        let material = SCNMaterial()
        material.diffuse.contents = digitImage
        material.lightingModel = .constant
        material.isDoubleSided = true
        material.transparencyMode = .aOne
        material.writesToDepthBuffer = false
        material.readsFromDepthBuffer = false

        plane.materials = [material]

        // No euler rotation here. We set simdTransform directly per digit.
        return SCNNode(geometry: plane)
    }

    private func makeDigitTexture(_ value: Int) -> UIImage {
        let canvas = CGSize(width: 256, height: 256)

        let format = UIGraphicsImageRendererFormat()
        format.opaque = false
        format.scale = 1.0

        let renderer = UIGraphicsImageRenderer(size: canvas, format: format)

        return renderer.image { _ in
            let paragraph = NSMutableParagraphStyle()
            paragraph.alignment = .center

            let color = UIColor(red: 0.08, green: 0.32, blue: 0.95, alpha: 0.96)

            let attrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 150, weight: .semibold),
                .foregroundColor: color,
                .paragraphStyle: paragraph
            ]

            let s = "\(value)" as NSString
            let textSize = s.size(withAttributes: attrs)

            let rect = CGRect(
                x: (canvas.width - textSize.width) / 2.0,
                y: (canvas.height - textSize.height) / 2.0 - 8.0,
                width: textSize.width,
                height: textSize.height
            )

            s.draw(in: rect, withAttributes: attrs)
        }
    }
}

struct ContentView: View {
    @StateObject private var appState = AppState()

    var body: some View {
        ZStack(alignment: .top) {
            ARSudokuView(appState: appState)
                .ignoresSafeArea()

            Color.clear
                .contentShape(Rectangle())
                .ignoresSafeArea()
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onEnded { value in
                            appState.statusText = "Tap received. Locking at puzzle tap..."
                            appState.sendCurrentFrameToSolver(tapPoint: value.location)
                        }
                )

            VStack(spacing: 5) {
                Text("Sudoku AR Overlay")
                    .font(.caption)
                    .bold()

                Text(appState.statusText)
                    .font(.caption2)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 8)

                if appState.isSolving {
                    Text("Solving...")
                        .font(.caption2)
                        .foregroundStyle(.white.opacity(0.80))
                } else {
                    Text("Tap center of puzzle to solve")
                        .font(.caption2)
                        .foregroundStyle(.white.opacity(0.80))
                }
            }
            .padding(.top, 10)
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .foregroundStyle(.white)
            .shadow(radius: 3)
            .background(
                Color.black.opacity(0.30)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            )
            .padding(.horizontal, 10)
            .allowsHitTesting(false)
        }
    }
}

struct ARSudokuView: UIViewRepresentable {
    @ObservedObject var appState: AppState

    func makeUIView(context: Context) -> ARSCNView {
        let sceneView = ARSCNView(frame: .zero)

        sceneView.delegate = context.coordinator
        sceneView.scene = SCNScene()
        sceneView.automaticallyUpdatesLighting = true
        sceneView.autoenablesDefaultLighting = true
        sceneView.debugOptions = []

        context.coordinator.sceneView = sceneView
        appState.sceneView = sceneView

        let config = ARWorldTrackingConfiguration()
        config.planeDetection = [.horizontal]
        config.environmentTexturing = .automatic

        sceneView.session.run(
            config,
            options: [.resetTracking, .removeExistingAnchors]
        )

        return sceneView
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(appState: appState)
    }

    final class Coordinator: NSObject, ARSCNViewDelegate {
        weak var sceneView: ARSCNView?
        private weak var appState: AppState?

        init(appState: AppState) {
            self.appState = appState
        }
    }
}

extension simd_float4x4 {
    var translation: SIMD3<Float> {
        SIMD3<Float>(columns.3.x, columns.3.y, columns.3.z)
    }
}

extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
