import SwiftUI
import Combine
import ARKit
import SceneKit
import UIKit
import CoreImage
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
    let planeY: Float
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

    @Published var statusText: String = "Tap anywhere to solve"
    @Published var isSolving: Bool = false
    @Published var lastSolveResponse: SolveResponse?

    private let solverClient = SolverClient()
    private var pendingSolveFrameLock: SolveFrameLock?
    private var worldSolutionNode: SCNNode?

    func sendCurrentFrameToSolver() {
        guard !isSolving else { return }

        guard let sceneView,
              let frame = sceneView.session.currentFrame else {
            statusText = "No AR frame available yet."
            return
        }

        guard let lock = makeSolveFrameLock(frame: frame, sceneView: sceneView) else {
            statusText = "Could not lock table plane. Center puzzle, move slowly, then tap again."
            return
        }

        pendingSolveFrameLock = lock

        // Clear old overlay before snapshot so Python does not see our previous blue digits.
        worldSolutionNode?.removeFromParentNode()
        worldSolutionNode = nil

        let snapshot = sceneView.snapshot()

        guard let jpeg = snapshot.jpegData(compressionQuality: 0.90) else {
            statusText = "Could not create AR view snapshot JPEG."
            return
        }

        isSolving = true
        statusText = "Frame/table locked. Sending snapshot to solver..."

        Task {
            defer {
                isSolving = false
            }

            do {
                let response = try await solverClient.solve(imageJPEG: jpeg)
                lastSolveResponse = response

                let latency = response.latencyMs.map { String(format: "%.0f ms", $0) } ?? "n/a"
                let givens = response.givensCount.map { "\($0)" } ?? "n/a"
                let imageSize = "\(response.imageWidth ?? 0)x\(response.imageHeight ?? 0)"

                guard response.status == "solved" else {
                    statusText = "Solver failed: \(response.message ?? "no message")"
                    return
                }

                let placed = placeWorldSolutionOverlay(response)
                if placed {
                    statusText = "Solved | \(latency) | givens \(givens) | image \(imageSize)"
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

    private func makeSolveFrameLock(frame: ARFrame, sceneView: ARSCNView) -> SolveFrameLock? {
        let viewSize = sceneView.bounds.size
        let orientation = currentInterfaceOrientation()

        // Lock the plane at tap time. Use center of screen because the user is expected
        // to center the puzzle before tapping.
        let center = CGPoint(x: viewSize.width / 2.0, y: viewSize.height / 2.0)

        guard let query = sceneView.raycastQuery(
            from: center,
            allowing: .estimatedPlane,
            alignment: .horizontal
        ) else {
            return nil
        }

        guard let hit = sceneView.session.raycast(query).first else {
            return nil
        }

        let projection = frame.camera.projectionMatrix(
            for: orientation,
            viewportSize: viewSize,
            zNear: 0.001,
            zFar: 10.0
        )

        let view = frame.camera.viewMatrix(for: orientation)

        return SolveFrameLock(
            inverseViewMatrix: simd_inverse(view),
            inverseProjectionMatrix: simd_inverse(projection),
            viewportSize: viewSize,
            planeY: hit.worldTransform.translation.y
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

        // Since the submitted image is a sceneView.snapshot(), image pixels map directly
        // to the ARSCNView bounds by simple scaling.
        let screenCorners: [CGPoint] = corners.map { c in
            let imageX = CGFloat(c[0])
            let imageY = CGFloat(c[1])
            return snapshotImagePointToViewPoint(
                CGPoint(x: imageX, y: imageY),
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

        let node = makeWorldSolutionNode(
            topLeft: worldCorners[0],
            topRight: worldCorners[1],
            bottomRight: worldCorners[2],
            bottomLeft: worldCorners[3],
            givens: givens,
            solution: solution
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

        // Try Metal-style depth first. This is the typical ARKit projection convention.
        if let p = intersectLockedPlane(ndcX: ndcX, ndcY: ndcY, nearZ: 0.0, farZ: 1.0, lock: lock) {
            return p
        }

        // Fallback for OpenGL-style clip depth if needed.
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

        let denom = direction.y
        if Swift.abs(denom) < 0.00001 {
            return nil
        }

        let t = (lock.planeY - origin.y) / denom
        if t < 0 {
            return nil
        }

        return origin + direction * t
    }

    private func makeWorldSolutionNode(
        topLeft: SIMD3<Float>,
        topRight: SIMD3<Float>,
        bottomRight: SIMD3<Float>,
        bottomLeft: SIMD3<Float>,
        givens: [[Int]],
        solution: [[Int]]
    ) -> SCNNode {
        let root = SCNNode()

        let center = (topLeft + topRight + bottomRight + bottomLeft) / 4.0

        let xAxisRaw = ((topRight - topLeft) + (bottomRight - bottomLeft)) / 2.0
        let zAxisRaw = ((bottomLeft - topLeft) + (bottomRight - topRight)) / 2.0

        let width = simd_length(xAxisRaw)
        let height = simd_length(zAxisRaw)

        guard width > 0.001, height > 0.001 else {
            return root
        }

        let xAxis = simd_normalize(xAxisRaw)
        let zAxis = simd_normalize(zAxisRaw)
        let yAxis = simd_normalize(simd_cross(zAxis, xAxis))

        var transform = matrix_identity_float4x4
        transform.columns.0 = SIMD4<Float>(xAxis.x, xAxis.y, xAxis.z, 0)
        transform.columns.1 = SIMD4<Float>(yAxis.x, yAxis.y, yAxis.z, 0)
        transform.columns.2 = SIMD4<Float>(zAxis.x, zAxis.y, zAxis.z, 0)
        transform.columns.3 = SIMD4<Float>(center.x, center.y, center.z, 1)

        root.simdTransform = transform

        let digitPlaneWidth = width / 9.0 * 0.72
        let digitPlaneHeight = height / 9.0 * 0.72

        for r in 0..<9 {
            for c in 0..<9 {
                let given = givens[safe: r]?[safe: c] ?? 0
                let value = solution[safe: r]?[safe: c] ?? 0

                if given == 0 && value != 0 {
                    let x = -width / 2.0 + (Float(c) + 0.5) * width / 9.0
                    let z = -height / 2.0 + (Float(r) + 0.5) * height / 9.0

                    let digit = makeDigitNode(value, width: digitPlaneWidth, height: digitPlaneHeight)
                    digit.position = SCNVector3(x, 0.00008, z)
                    root.addChildNode(digit)
                }
            }
        }

        return root
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

        let node = SCNNode(geometry: plane)

        // SCNPlane lives in local XY. Rotate into local X/Z so it lies flat on the puzzle plane.
        node.eulerAngles.x = -.pi / 2.0

        return node
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
                .onTapGesture {
                    appState.statusText = "Tap received. Locking frame/table..."
                    appState.sendCurrentFrameToSolver()
                }

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
                    Text("Tap anywhere to solve")
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
