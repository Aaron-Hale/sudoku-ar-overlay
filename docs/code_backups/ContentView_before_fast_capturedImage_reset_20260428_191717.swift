import SwiftUI
import Combine
import ARKit
import SceneKit
import UIKit
import CoreImage

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
    let cameraTransform: simd_float4x4
    let inverseProjection: simd_float4x4
    let viewportSize: CGSize
    let planeY: Float
}

final class SolverClient {
    let baseURL = URL(string: "http://192.168.1.74:8000")!

    func solve(imageJPEG: Data) async throws -> SolveResponse {
        let url = baseURL.appendingPathComponent("solve")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()

        body.appendMultipartField(
            name: "metadata_json",
            value: #"{"source":"SudokuAROverlay iPhone debug frame"}"#,
            boundary: boundary
        )

        body.appendMultipartFile(
            name: "image",
            filename: "arkit_frame.jpg",
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

    mutating func appendMultipartFile(name: String, filename: String, mimeType: String, data: Data, boundary: String) {
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

    @Published var statusText: String = "AR ready. Tap table to place test grid."
    @Published var isSolving: Bool = false
    @Published var lastSolveResponse: SolveResponse?
    @Published var showDebugOverlay: Bool = false

    private let solverClient = SolverClient()
    private let ciContext = CIContext()
    private var pendingSolveFrameLock: SolveFrameLock?
    private var worldSolutionNode: SCNNode?

    func sendCurrentFrameToSolver() {
        guard !isSolving else { return }

        guard let sceneView = sceneView,
              let frame = sceneView.session.currentFrame else {
            statusText = "No AR frame available yet."
            return
        }

        guard let lock = makeSolveFrameLock(frame: frame, sceneView: sceneView) else {
            statusText = "Could not lock table plane. Center puzzle, move slowly, then tap again."
            return
        }

        pendingSolveFrameLock = lock
        statusText = "Frame and table locked. Sending to solver..."

        guard let jpeg = makeJPEG(from: frame.capturedImage) else {
            statusText = "Could not convert AR frame to JPEG."
            return
        }

        isSolving = true
        statusText = "Sending frame to solver..."

        Task {
            do {
                let response = try await solverClient.solve(imageJPEG: jpeg)
                lastSolveResponse = response

                let latency = response.latencyMs.map { String(format: "%.0f ms", $0) } ?? "n/a"
                let givens = response.givensCount.map { "\($0)" } ?? "n/a"
                let imageSize = "\(response.imageWidth ?? 0)x\(response.imageHeight ?? 0)"

                if response.status == "solved" {
                    statusText = "Solved | latency \(latency) | givens \(givens) | image \(imageSize)"
                    placeWorldSolutionOverlay(response)
                } else {
                    statusText = "Solver: \(response.status) | \(response.message ?? "no message")"
                }
            } catch {
                statusText = "Solver call failed: \(error.localizedDescription)"
            }

            isSolving = false
        }
    }

    private func makeJPEG(from pixelBuffer: CVPixelBuffer) -> Data? {
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer).oriented(.right)

        guard let cgImage = ciContext.createCGImage(ciImage, from: ciImage.extent) else {
            return nil
        }

        let image = UIImage(cgImage: cgImage)
        return image.jpegData(compressionQuality: 0.85)
    }

    private func placeWorldSolutionOverlay(_ response: SolveResponse) -> Bool {
        guard let sceneView else {
            statusText += " | no scene view"
            return false
        }

        guard let corners = response.cornersPx,
              corners.count == 4,
              let imageWidth = response.imageWidth,
              let imageHeight = response.imageHeight,
              let solution = response.solution,
              let givens = response.givens else {
            statusText += " | missing solve geometry"
            return false
        }

        guard let lock = pendingSolveFrameLock else {
            statusText += " | no locked tap geometry"
            return false
        }

        let viewSize = lock.viewportSize
        let imageSize = CGSize(width: CGFloat(imageWidth), height: CGFloat(imageHeight))

        let screenPoints = corners.map {
            mapImagePoint($0, imageSize: imageSize, viewSize: viewSize)
        }

        var worldPoints: [SIMD3<Float>] = []

        for point in screenPoints {
            guard let worldPoint = worldPointOnLockedPlane(screenPoint: point, lock: lock) else {
                statusText += " | locked plane intersection failed"
                return false
            }

            worldPoints.append(worldPoint)
        }

        guard worldPoints.count == 4 else {
            statusText += " | not enough locked world corners"
            return false
        }

        worldSolutionNode?.removeFromParentNode()

        let node = makeWorldSolutionNode(
            topLeft: worldPoints[0],
            topRight: worldPoints[1],
            bottomRight: worldPoints[2],
            bottomLeft: worldPoints[3],
            givens: givens,
            solution: solution
        )

        sceneView.scene.rootNode.addChildNode(node)
        worldSolutionNode = node

        return true
    }


    private func makeSolveFrameLock(frame: ARFrame, sceneView: ARSCNView) -> SolveFrameLock? {
        let viewSize = sceneView.bounds.size

        // Lock the table/paper plane immediately at tap time.
        // This avoids using a later camera pose after the network solver returns.
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
            for: .portrait,
            viewportSize: viewSize,
            zNear: 0.001,
            zFar: 10.0
        )

        return SolveFrameLock(
            cameraTransform: frame.camera.transform,
            inverseProjection: simd_inverse(projection),
            viewportSize: viewSize,
            planeY: hit.worldTransform.translation.y
        )
    }

    private func worldPointOnLockedPlane(screenPoint: CGPoint, lock: SolveFrameLock) -> SIMD3<Float>? {
        guard lock.viewportSize.width > 1, lock.viewportSize.height > 1 else {
            return nil
        }

        // Convert UIKit screen coordinate to normalized device coordinates.
        let ndcX = Float((screenPoint.x / lock.viewportSize.width) * 2.0 - 1.0)
        let ndcY = Float(1.0 - (screenPoint.y / lock.viewportSize.height) * 2.0)

        var nearCamera = lock.inverseProjection * SIMD4<Float>(ndcX, ndcY, 0.0, 1.0)
        var farCamera = lock.inverseProjection * SIMD4<Float>(ndcX, ndcY, 1.0, 1.0)

        nearCamera = nearCamera / nearCamera.w
        farCamera = farCamera / farCamera.w

        let nearWorld4 = lock.cameraTransform * SIMD4<Float>(
            nearCamera.x,
            nearCamera.y,
            nearCamera.z,
            1.0
        )

        let farWorld4 = lock.cameraTransform * SIMD4<Float>(
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

    private func mapImagePoint(_ p: [Double], imageSize: CGSize, viewSize: CGSize) -> CGPoint {
        let x = CGFloat(p[0])
        let y = CGFloat(p[1])

        let scale = max(viewSize.width / imageSize.width, viewSize.height / imageSize.height)
        let scaledWidth = imageSize.width * scale
        let scaledHeight = imageSize.height * scale

        let xOffset = (viewSize.width - scaledWidth) / 2.0
        let yOffset = (viewSize.height - scaledHeight) / 2.0

        return CGPoint(
            x: xOffset + x * scale,
            y: yOffset + y * scale
        )
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

        let xAxis = simd_normalize(xAxisRaw)
        let zAxis = simd_normalize(zAxisRaw)
        let yAxis = simd_normalize(simd_cross(zAxis, xAxis))

        var transform = matrix_identity_float4x4
        transform.columns.0 = SIMD4<Float>(xAxis.x, xAxis.y, xAxis.z, 0)
        transform.columns.1 = SIMD4<Float>(yAxis.x, yAxis.y, yAxis.z, 0)
        transform.columns.2 = SIMD4<Float>(zAxis.x, zAxis.y, zAxis.z, 0)
        transform.columns.3 = SIMD4<Float>(center.x, center.y, center.z, 1)

        root.simdTransform = transform

        // Gridlines intentionally hidden for product-like numbers-only overlay.

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

    private func addGridLines(to root: SCNNode, width: Float, height: Float) {
        // Thin, flat, low-glow grid. This should read more like a 2D overlay
        // and less like a chunky 3D AR object.
        let thin: CGFloat = 0.00045
        let heavy: CGFloat = 0.00095
        let lineHeight: CGFloat = 0.00018

        let minorColor = UIColor(white: 0.05, alpha: 0.34)
        let majorColor = UIColor(white: 0.02, alpha: 0.48)

        for i in 0...9 {
            let isHeavy = i % 3 == 0
            let thickness = isHeavy ? heavy : thin
            let color = isHeavy ? majorColor : minorColor

            let x = -width / 2.0 + Float(i) * width / 9.0
            let z = -height / 2.0 + Float(i) * height / 9.0

            let vertical = SCNBox(
                width: thickness,
                height: lineHeight,
                length: CGFloat(height),
                chamferRadius: 0
            )
            vertical.firstMaterial?.diffuse.contents = color
            vertical.firstMaterial?.emission.contents = UIColor.clear
            vertical.firstMaterial?.lightingModel = .constant
            vertical.firstMaterial?.isDoubleSided = true

            let verticalNode = SCNNode(geometry: vertical)
            verticalNode.position = SCNVector3(x, 0.001, 0)
            root.addChildNode(verticalNode)

            let horizontal = SCNBox(
                width: CGFloat(width),
                height: lineHeight,
                length: thickness,
                chamferRadius: 0
            )
            horizontal.firstMaterial?.diffuse.contents = color
            horizontal.firstMaterial?.emission.contents = UIColor.clear
            horizontal.firstMaterial?.lightingModel = .constant
            horizontal.firstMaterial?.isDoubleSided = true

            let horizontalNode = SCNNode(geometry: horizontal)
            horizontalNode.position = SCNVector3(0, 0.001, z)
            root.addChildNode(horizontalNode)
        }
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

        // SCNPlane lies in local XY by default; rotate it flat into the board's X/Z plane.
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

            // Lighter blue, still strong enough to stand out from pencil/print.
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
            ARSudokuTestView(appState: appState)
                .ignoresSafeArea()

            // Full-screen tap catcher. This is intentionally above the AR view
            // so SwiftUI reliably receives taps and calls the solver.
            Color.clear
                .contentShape(Rectangle())
                .ignoresSafeArea()
                .onTapGesture {
                    appState.statusText = "Tap received. Sending frame to solver..."
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

                Text(appState.isSolving ? "Solving..." : "Tap anywhere to solve")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.75))
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




struct DebugSolutionOverlay: View {
    let response: SolveResponse

    var body: some View {
        GeometryReader { geo in
            if let corners = response.cornersPx,
               corners.count == 4,
               let imageWidth = response.imageWidth,
               let imageHeight = response.imageHeight {

                let viewSize = geo.size
                let imageSize = CGSize(width: CGFloat(imageWidth), height: CGFloat(imageHeight))
                let mappedCorners = corners.map { mapImagePoint($0, imageSize: imageSize, viewSize: viewSize) }

                ZStack {
                    Path { path in
                        path.move(to: mappedCorners[0])
                        path.addLine(to: mappedCorners[1])
                        path.addLine(to: mappedCorners[2])
                        path.addLine(to: mappedCorners[3])
                        path.closeSubpath()
                    }
                    .stroke(Color.clear, lineWidth: 0)

                    if let solution = response.solution, solution.count == 9 {
                        ForEach(0..<81, id: \.self) { idx in
                            let r = idx / 9
                            let c = idx % 9
                            let isGiven = response.givens?[safe: r]?[safe: c] ?? 0
                            let value = solution[safe: r]?[safe: c] ?? 0

                            if isGiven == 0 && value != 0 {
                                let p = cellCenter(row: r, col: c, corners: mappedCorners)

                                Text("\(value)")
                                    .font(.system(size: 20, weight: .semibold, design: .rounded))
                                    .foregroundColor(Color(red: 0.16, green: 0.35, blue: 0.95))
                                    .shadow(color: .black, radius: 2)
                                    .position(p)
                            }
                        }
                    }
                }
            }
        }
    }

    private func mapImagePoint(_ p: [Double], imageSize: CGSize, viewSize: CGSize) -> CGPoint {
        let x = CGFloat(p[0])
        let y = CGFloat(p[1])

        let scale = max(viewSize.width / imageSize.width, viewSize.height / imageSize.height)
        let scaledWidth = imageSize.width * scale
        let scaledHeight = imageSize.height * scale

        let xOffset = (viewSize.width - scaledWidth) / 2.0
        let yOffset = (viewSize.height - scaledHeight) / 2.0

        return CGPoint(x: xOffset + x * scale, y: yOffset + y * scale)
    }

    private func cellCenter(row: Int, col: Int, corners: [CGPoint]) -> CGPoint {
        let tl = corners[0]
        let tr = corners[1]
        let br = corners[2]
        let bl = corners[3]

        let u = CGFloat(col) / 9.0 + 0.5 / 9.0
        let v = CGFloat(row) / 9.0 + 0.5 / 9.0

        let top = lerp(tl, tr, u)
        let bottom = lerp(bl, br, u)
        return lerp(top, bottom, v)
    }

    private func lerp(_ a: CGPoint, _ b: CGPoint, _ t: CGFloat) -> CGPoint {
        CGPoint(x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t)
    }
}

struct ARSudokuTestView: UIViewRepresentable {
    @ObservedObject var appState: AppState

    func makeUIView(context: Context) -> ARSCNView {
        let sceneView = ARSCNView(frame: .zero)

        sceneView.delegate = context.coordinator
        sceneView.scene = SCNScene()
        sceneView.automaticallyUpdatesLighting = true
        sceneView.autoenablesDefaultLighting = true
        sceneView.debugOptions = []

        let tap = UITapGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleTap(_:))
        )

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
        private var currentGridNode: SCNNode?

        init(appState: AppState) {
            self.appState = appState
        }

        @objc func handleTap(_ recognizer: UITapGestureRecognizer) {
            Task { @MainActor in
                self.appState?.statusText = "Tap received. Sending frame to solver..."
                self.appState?.sendCurrentFrameToSolver()
            }
        }

        private func placeSudokuGrid(at transform: simd_float4x4, in sceneView: ARSCNView) {
            currentGridNode?.removeFromParentNode()

            let grid = makeSudokuGridNode(sizeMeters: 0.22)
            grid.simdTransform = transform

            sceneView.scene.rootNode.addChildNode(grid)
            currentGridNode = grid
        }

        private func makeSudokuGridNode(sizeMeters: Float) -> SCNNode {
            let root = SCNNode()
            let size = CGFloat(sizeMeters)
            let cell = size / 9.0

            for i in 0...9 {
                let isHeavy = i % 3 == 0
                let thickness: CGFloat = isHeavy ? 0.0035 : 0.0015
                let color = isHeavy ? UIColor(white: 0.02, alpha: 0.45) : UIColor(white: 0.05, alpha: 0.30)

                let vertical = SCNBox(width: thickness, height: 0.001, length: size, chamferRadius: 0)
                vertical.firstMaterial?.diffuse.contents = color
                vertical.firstMaterial?.emission.contents = UIColor.clear

                let verticalNode = SCNNode(geometry: vertical)
                verticalNode.position = SCNVector3(Float(-size / 2.0 + CGFloat(i) * cell), 0.001, 0)
                root.addChildNode(verticalNode)

                let horizontal = SCNBox(width: size, height: 0.001, length: thickness, chamferRadius: 0)
                horizontal.firstMaterial?.diffuse.contents = color
                horizontal.firstMaterial?.emission.contents = UIColor.clear

                let horizontalNode = SCNNode(geometry: horizontal)
                horizontalNode.position = SCNVector3(0, 0.001, Float(-size / 2.0 + CGFloat(i) * cell))
                root.addChildNode(horizontalNode)
            }

            return root
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
