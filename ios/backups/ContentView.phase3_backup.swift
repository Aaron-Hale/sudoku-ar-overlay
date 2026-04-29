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

    @Published var statusText: String = "AR ready. Tap table to place grid."
    @Published var isSolving: Bool = false
    @Published var lastSolveResponse: SolveResponse?
    @Published var showDebugOverlay: Bool = true

    private let solverClient = SolverClient()
    private let ciContext = CIContext()

    func sendCurrentFrameToSolver() {
        guard !isSolving else { return }

        guard let frame = sceneView?.session.currentFrame else {
            statusText = "No AR frame available yet."
            return
        }

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
}

struct ContentView: View {
    @StateObject private var appState = AppState()

    var body: some View {
        ZStack(alignment: .top) {
            ARSudokuTestView(appState: appState)
                .ignoresSafeArea()

            if appState.showDebugOverlay, let response = appState.lastSolveResponse {
                DebugSolutionOverlay(response: response)
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
            }

            VStack(spacing: 10) {
                Text("Sudoku AR Overlay")
                    .font(.headline)

                Text(appState.statusText)
                    .font(.caption)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 12)

                HStack(spacing: 10) {
                    Button {
                        appState.sendCurrentFrameToSolver()
                    } label: {
                        Text(appState.isSolving ? "Solving..." : "Send Frame to Solver")
                            .font(.subheadline)
                            .bold()
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                            .background(appState.isSolving ? Color.gray : Color.blue)
                            .foregroundColor(.white)
                            .clipShape(Capsule())
                    }
                    .disabled(appState.isSolving)

                    Button {
                        appState.showDebugOverlay.toggle()
                    } label: {
                        Text(appState.showDebugOverlay ? "Hide Overlay" : "Show Overlay")
                            .font(.subheadline)
                            .bold()
                            .padding(.horizontal, 12)
                            .padding(.vertical, 10)
                            .background(Color.black.opacity(0.55))
                            .foregroundColor(.white)
                            .clipShape(Capsule())
                    }
                }

                Text("Debug overlay is screen-space only. Hold still after sending. AR-world placement comes next.")
                    .font(.caption2)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 12)
            }
            .padding(.top, 14)
            .padding(.horizontal, 12)
            .foregroundStyle(.white)
            .shadow(radius: 5)
            .background(
                Color.black.opacity(0.35)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            )
            .padding(.horizontal, 10)
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
                    .stroke(Color.green, lineWidth: 4)

                    if let solution = response.solution, solution.count == 9 {
                        ForEach(0..<81, id: \.self) { idx in
                            let r = idx / 9
                            let c = idx % 9
                            let isGiven = response.givens?[safe: r]?[safe: c] ?? 0
                            let value = solution[safe: r]?[safe: c] ?? 0

                            if isGiven == 0 && value != 0 {
                                let p = cellCenter(row: r, col: c, corners: mappedCorners)

                                Text("\(value)")
                                    .font(.system(size: 22, weight: .heavy, design: .rounded))
                                    .foregroundColor(.cyan)
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

        // The JPEG sent to Python is portrait-oriented. AR preview uses aspect-fill.
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
        CGPoint(
            x: a.x + (b.x - a.x) * t,
            y: a.y + (b.y - a.y) * t
        )
    }
}

extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
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
        sceneView.debugOptions = [.showFeaturePoints]

        let tap = UITapGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleTap(_:))
        )
        sceneView.addGestureRecognizer(tap)

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
            guard let sceneView = sceneView else { return }

            let location = recognizer.location(in: sceneView)

            guard let query = sceneView.raycastQuery(
                from: location,
                allowing: .estimatedPlane,
                alignment: .horizontal
            ) else {
                Task { @MainActor in
                    self.appState?.statusText = "Could not create raycast query."
                }
                return
            }

            let results = sceneView.session.raycast(query)

            guard let first = results.first else {
                Task { @MainActor in
                    self.appState?.statusText = "No table hit. Move slowly and tap again."
                }
                return
            }

            placeSudokuGrid(at: first.worldTransform, in: sceneView)

            Task { @MainActor in
                self.appState?.statusText = "Placed AR grid. Send a frame to solver for debug overlay."
            }
        }

        private func placeSudokuGrid(at transform: simd_float4x4, in sceneView: ARSCNView) {
            currentGridNode?.removeFromParentNode()

            let grid = makeSudokuGridNode(sizeMeters: 0.22)
            grid.simdTransform = transform

            sceneView.scene.rootNode.addChildNode(grid)
            currentGridNode = grid

            print("Placed test Sudoku grid anchor.")
        }

        private func makeSudokuGridNode(sizeMeters: Float) -> SCNNode {
            let root = SCNNode()

            let lineColor = UIColor.systemGreen
            let heavyLineColor = UIColor.systemYellow

            let lineThickness: CGFloat = 0.0015
            let heavyLineThickness: CGFloat = 0.0035

            let size = CGFloat(sizeMeters)
            let cell = size / 9.0

            for i in 0...9 {
                let isHeavy = i % 3 == 0
                let thickness = isHeavy ? heavyLineThickness : lineThickness
                let color = isHeavy ? heavyLineColor : lineColor

                let verticalGeometry = SCNBox(
                    width: thickness,
                    height: 0.001,
                    length: size,
                    chamferRadius: 0
                )
                verticalGeometry.firstMaterial?.diffuse.contents = color
                verticalGeometry.firstMaterial?.emission.contents = color

                let verticalNode = SCNNode(geometry: verticalGeometry)
                verticalNode.position = SCNVector3(
                    Float(-size / 2.0 + CGFloat(i) * cell),
                    0.001,
                    0
                )
                root.addChildNode(verticalNode)

                let horizontalGeometry = SCNBox(
                    width: size,
                    height: 0.001,
                    length: thickness,
                    chamferRadius: 0
                )
                horizontalGeometry.firstMaterial?.diffuse.contents = color
                horizontalGeometry.firstMaterial?.emission.contents = color

                let horizontalNode = SCNNode(geometry: horizontalGeometry)
                horizontalNode.position = SCNVector3(
                    0,
                    0.001,
                    Float(-size / 2.0 + CGFloat(i) * cell)
                )
                root.addChildNode(horizontalNode)
            }

            return root
        }
    }
}
