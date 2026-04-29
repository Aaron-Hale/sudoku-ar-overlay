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

final class SolverClient {
    let baseURL = URL(string: "http://192.168.1.74:8000")!

    func solve(imageJPEG: Data) async throws -> SolveResponse {
        let url = baseURL.appendingPathComponent("solve")
        var request = URLRequest(url: url, timeoutInterval: 20)
        request.httpMethod = "POST"

        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()

        body.appendMultipartField(
            name: "metadata_json",
            value: #"{"source":"SudokuAROverlay capturedImage fast baseline"}"#,
            boundary: boundary
        )

        body.appendMultipartFile(
            name: "image",
            filename: "arkit_captured_frame.jpg",
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
    @Published var hasActiveSolutionOverlay: Bool = false

    private let solverClient = SolverClient()
    private let ciContext = CIContext()
    private var worldSolutionNode: SCNNode?

    func sendCurrentFrameToSolver() {
        guard !isSolving else { return }

        guard let sceneView,
              let frame = sceneView.session.currentFrame else {
            statusText = "No AR frame available yet."
            return
        }

        guard let jpeg = makeJPEG(from: frame.capturedImage) else {
            statusText = "Could not convert AR frame to JPEG."
            return
        }

        worldSolutionNode?.removeFromParentNode()
        worldSolutionNode = nil
        hasActiveSolutionOverlay = false

        isSolving = true
        statusText = "Sending camera frame to solver..."

        Task {
            defer {
                isSolving = false
            }

            do {
                let response = try await solverClient.solve(imageJPEG: jpeg)

                let latency = response.latencyMs.map { String(format: "%.0f ms", $0) } ?? "n/a"
                let givens = response.givensCount.map { "\($0)" } ?? "n/a"
                let imageSize = "\(response.imageWidth ?? 0)x\(response.imageHeight ?? 0)"

                guard response.status == "solved" else {
                    hasActiveSolutionOverlay = false
                    statusText = "Solver failed: \(response.message ?? "no message")"
                    return
                }

                let placed = placeWorldSolutionOverlay(response)
                if placed {
                    hasActiveSolutionOverlay = true
                    statusText = "Solved | \(latency) | givens \(givens) | image \(imageSize)"
                } else {
                    hasActiveSolutionOverlay = false
                }
            } catch {
                hasActiveSolutionOverlay = false
                statusText = "Solver call failed: \(error.localizedDescription)"
            }
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

        let viewSize = sceneView.bounds.size
        let imageSize = CGSize(width: CGFloat(imageWidth), height: CGFloat(imageHeight))

        let screenPoints = corners.map {
            mapImagePoint($0, imageSize: imageSize, viewSize: viewSize)
        }

        var worldPoints: [SIMD3<Float>] = []

        for point in screenPoints {
            guard let query = sceneView.raycastQuery(
                from: point,
                allowing: .estimatedPlane,
                alignment: .horizontal
            ) else {
                statusText += " | raycast query failed"
                return false
            }

            let results = sceneView.session.raycast(query)

            guard let first = results.first else {
                statusText += " | raycast missed table"
                return false
            }

            worldPoints.append(first.worldTransform.translation)
        }

        guard worldPoints.count == 4 else {
            statusText += " | not enough world corners"
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

        // Instead of rendering 81 separate AR digit nodes, render one transparent
        // board-space solution texture on a single flat plane. This mirrors the
        // old homography overlay approach and should feel more like ink on one sheet.
        let solutionImage = makeSolutionTexture(givens: givens, solution: solution)

        let plane = SCNPlane(width: CGFloat(width), height: CGFloat(height))

        let material = SCNMaterial()
        material.diffuse.contents = solutionImage
        material.lightingModel = .constant
        material.isDoubleSided = true
        material.transparencyMode = .aOne
        material.blendMode = .alpha
        material.readsFromDepthBuffer = true
        material.writesToDepthBuffer = false
        material.transparency = 1.0

        plane.materials = [material]

        let overlayNode = SCNNode(geometry: plane)

        // SCNPlane is local X/Y. Rotate into the board's local X/Z plane.
        overlayNode.eulerAngles.x = -.pi / 2.0

        // Tiny offset above board plane to avoid flicker/z-fighting.
        overlayNode.position = SCNVector3(0, 0.00008, 0)

        root.addChildNode(overlayNode)

        return root
    }

    private func makeSolutionTexture(givens: [[Int]], solution: [[Int]]) -> UIImage {
        let canvasSide: CGFloat = 900
        let cell: CGFloat = canvasSide / 9.0
        let canvas = CGSize(width: canvasSide, height: canvasSide)

        let format = UIGraphicsImageRendererFormat()
        format.opaque = false
        format.scale = 1.0

        let renderer = UIGraphicsImageRenderer(size: canvas, format: format)

        return renderer.image { _ in
            let paragraph = NSMutableParagraphStyle()
            paragraph.alignment = .center

            // Strong blue, slightly lighter than before, but not light blue.
            let digitColor = UIColor(red: 0.08, green: 0.32, blue: 0.95, alpha: 0.96)

            let font = UIFont.systemFont(ofSize: 76, weight: .semibold)

            let attrs: [NSAttributedString.Key: Any] = [
                .font: font,
                .foregroundColor: digitColor,
                .paragraphStyle: paragraph
            ]

            for r in 0..<9 {
                for c in 0..<9 {
                    let given = givens[safe: r]?[safe: c] ?? 0
                    let value = solution[safe: r]?[safe: c] ?? 0

                    guard given == 0, value != 0 else {
                        continue
                    }

                    let s = "\(value)" as NSString
                    let textSize = s.size(withAttributes: attrs)

                    let x = CGFloat(c) * cell
                    let y = CGFloat(r) * cell

                    let rect = CGRect(
                        x: x,
                        y: y + (cell - textSize.height) / 2.0 - 4.0,
                        width: cell,
                        height: textSize.height + 12.0
                    )

                    s.draw(in: rect, withAttributes: attrs)
                }
            }
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
        material.readsFromDepthBuffer = true
        material.writesToDepthBuffer = false

        plane.materials = [material]

        let node = SCNNode(geometry: plane)
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

            // Tap layer
            Color.clear
                .contentShape(Rectangle())
                .ignoresSafeArea()
                .onTapGesture {
                    appState.statusText = "Tap received. Sending frame..."
                    appState.sendCurrentFrameToSolver()
                }

            // Pre-solve capture guide. Screen-space only; not sent to solver because
            // solver uses ARFrame.capturedImage, not sceneView.snapshot().
            if !appState.isSolving && !appState.hasActiveSolutionOverlay {
                CornerCaptureGuide()
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
            }

            VStack(spacing: 5) {
                Text("Sudoku AR Overlay")
                    .font(.caption)
                    .bold()

                Text(appState.statusText)
                    .font(.caption2)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 8)

                Text(appState.isSolving ? "Solving..." : (appState.hasActiveSolutionOverlay ? "Tap again to rescan" : "Fill the corners with the puzzle, then tap"))
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.80))
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

struct CornerCaptureGuide: View {
    var body: some View {
        GeometryReader { geo in
            let guideWidth = geo.size.width * 0.62
            let guideHeight = guideWidth
            let cornerLength = guideWidth * 0.13
            let lineWidth: CGFloat = 3.0
            let rect = CGRect(
                x: (geo.size.width - guideWidth) / 2.0,
                y: (geo.size.height - guideHeight) / 2.0 + 12.0,
                width: guideWidth,
                height: guideHeight
            )

            ZStack {
                Path { path in
                    // Top-left
                    path.move(to: CGPoint(x: rect.minX, y: rect.minY + cornerLength))
                    path.addLine(to: CGPoint(x: rect.minX, y: rect.minY))
                    path.addLine(to: CGPoint(x: rect.minX + cornerLength, y: rect.minY))

                    // Top-right
                    path.move(to: CGPoint(x: rect.maxX - cornerLength, y: rect.minY))
                    path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
                    path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY + cornerLength))

                    // Bottom-right
                    path.move(to: CGPoint(x: rect.maxX, y: rect.maxY - cornerLength))
                    path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
                    path.addLine(to: CGPoint(x: rect.maxX - cornerLength, y: rect.maxY))

                    // Bottom-left
                    path.move(to: CGPoint(x: rect.minX + cornerLength, y: rect.maxY))
                    path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
                    path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY - cornerLength))
                }
                .stroke(
                    Color.white.opacity(0.72),
                    style: StrokeStyle(lineWidth: lineWidth, lineCap: .round, lineJoin: .round)
                )
                .shadow(color: .black.opacity(0.45), radius: 2, x: 0, y: 1)

                Text("Fill corners with puzzle")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.78))
                    .shadow(radius: 2)
                    .position(x: geo.size.width / 2.0, y: rect.maxY + 24.0)
            }
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
