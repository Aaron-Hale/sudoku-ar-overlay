import SwiftUI
import Combine
import ARKit
import SceneKit
import UIKit
import CoreImage
import ImageIO
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
    private func endpoint(baseURLString: String, path: String) throws -> URL {
        let trimmed = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        let normalized = trimmed.hasSuffix("/") ? String(trimmed.dropLast()) : trimmed

        guard let baseURL = URL(string: normalized),
              let scheme = baseURL.scheme?.lowercased(),
              ["http", "https"].contains(scheme) else {
            throw NSError(domain: "SolverClient", code: -1, userInfo: [
                NSLocalizedDescriptionKey: "Invalid backend URL. Use http://<MAC_WIFI_IP>:8000"
            ])
        }

        return baseURL.appendingPathComponent(path)
    }

    func health(baseURLString: String) async throws {
        let url = try endpoint(baseURLString: baseURLString, path: "health")
        var request = URLRequest(url: url, timeoutInterval: 5)
        request.httpMethod = "GET"

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse,
              (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
    }

    func detect(imageJPEG: Data, baseURLString: String) async throws -> SolveResponse {
        let url = try endpoint(baseURLString: baseURLString, path: "detect")
        var request = URLRequest(url: url, timeoutInterval: 12)
        request.httpMethod = "POST"

        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()

        body.appendMultipartField(
            name: "metadata_json",
            value: #"{"source":"SudokuAROverlay reacquisition detect"}"#,
            boundary: boundary
        )

        body.appendMultipartFile(
            name: "image",
            filename: "arkit_reacquire_frame.jpg",
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

    func solve(imageJPEG: Data, baseURLString: String) async throws -> SolveResponse {
        let url = try endpoint(baseURLString: baseURLString, path: "solve")
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
    private static let backendURLKey = "SudokuARBackendURL"
    private static let defaultBackendURL = "http://127.0.0.1:8000"

    weak var sceneView: ARSCNView?

    @Published var backendURLString: String {
        didSet {
            UserDefaults.standard.set(backendURLString, forKey: Self.backendURLKey)
        }
    }

    @Published var statusText: String = "Ready"
    @Published var isSolving: Bool = false
    @Published var hasActiveSolutionOverlay: Bool = false
    @Published var showCaptureGuide: Bool = true
    @Published var hasAttemptedSolve: Bool = false
    @Published var lastSolveSucceeded: Bool = false
    @Published var lastSolveSeconds: Double? = nil

    private let solverClient = SolverClient()
    private let ciContext = CIContext()
    private var worldSolutionNode: SCNNode?

    init() {
        self.backendURLString = UserDefaults.standard.string(forKey: Self.backendURLKey)
            ?? Self.defaultBackendURL
    }

    func updateBackendURL(_ value: String) {
        backendURLString = value
    }

    func normalizeBackendURL() {
        let trimmed = backendURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        backendURLString = trimmed.hasSuffix("/") ? String(trimmed.dropLast()) : trimmed
    }

    func pingBackend() {
        normalizeBackendURL()
        statusText = "Pinging backend..."

        Task {
            do {
                try await solverClient.health(baseURLString: backendURLString)
                statusText = "Backend reachable"
            } catch {
                statusText = "Backend unreachable"
            }
        }
    }

    // Dynamic ARImageAnchor experiment.
    // This is the most likely path to make the overlay feel glued to the paper.
    private var imageAnchorSolutionTexture: UIImage?
    private var currentSolveGeneration: Int = 0
    private var currentReferenceImageName: String = "SolvedSudokuBoard_0"
    private var isReacquiringPuzzle: Bool = false
    private var imageTrackingLostFrameCount: Int = 0
    private let imageTrackingLostGraceFrames: Int = 8
    private var solvedBoardFingerprint: String? 
    private let boardPhysicalWidthMeters: CGFloat = 0.085

    // Dynamic image-anchor reference crop is larger than the Sudoku grid.
    // This gives ARKit more surrounding paper/texture to recognize.
    // The solution texture still renders only over the inner board area.
    private let boardReferenceMarginScale: CGFloat = 1.25

    func clearDisplayedSolution() {
        isSolving = false
        hasActiveSolutionOverlay = false
        showCaptureGuide = true
        hasAttemptedSolve = false
        lastSolveSucceeded = false
        lastSolveSeconds = nil
        statusText = "Ready"

        worldSolutionNode?.removeFromParentNode()
        worldSolutionNode = nil

        imageAnchorSolutionTexture = nil

        if let sceneView {
            sceneView.scene.rootNode.enumerateChildNodes { node, _ in
                if node.name == "dynamicImageAnchorSolutionOverlay" ||
                    node.name == "poseEstimatedWorldSolutionOverlay" ||
                    node.name == "lockedWorldSolutionOverlay" ||
                    node.name == "persistentImageAnchorSolutionOverlay" {
                    node.removeFromParentNode()
                }
            }
        }
    }

    func sendCurrentFrameToSolver() {
        guard !isSolving else { return }

        showCaptureGuide = false
        hasAttemptedSolve = true
        lastSolveSucceeded = false
        lastSolveSeconds = nil

        guard let sceneView,
              let frame = sceneView.session.currentFrame else {
            statusText = "No AR frame available yet."
            return
        }

        guard let capturedUIImage = makeUIImage(from: frame.capturedImage),
              let jpeg = capturedUIImage.jpegData(compressionQuality: 0.85) else {
            statusText = "Could not convert AR frame to JPEG."
            return
        }

        currentSolveGeneration += 1
        currentReferenceImageName = "SolvedSudokuBoard_\(currentSolveGeneration)"
        removeAllDynamicImageAnchorOverlayNodes()

        worldSolutionNode?.removeFromParentNode()
        worldSolutionNode = nil
        hasActiveSolutionOverlay = false

        isSolving = true
        statusText = "Solving"

        Task {
            defer {
                isSolving = false
            }

            do {
                let response = try await solverClient.solve(imageJPEG: jpeg, baseURLString: backendURLString)

                let latency = response.latencyMs.map { String(format: "%.0f ms", $0) } ?? "n/a"
                let givens = response.givensCount.map { "\($0)" } ?? "n/a"
                let imageSize = "\(response.imageWidth ?? 0)x\(response.imageHeight ?? 0)"

                guard response.status == "solved" else {
                    hasActiveSolutionOverlay = false
                    lastSolveSucceeded = false
                    lastSolveSeconds = nil
                    statusText = "Failed"
                    return
                }

                solvedBoardFingerprint = boardFingerprint(response.givens)

                let placed = placeWorldSolutionOverlay(response)
                if placed {
                    hasActiveSolutionOverlay = true
                    lastSolveSucceeded = true
                    lastSolveSeconds = response.latencyMs.map { $0 / 1000.0 }
                    statusText = "SOLVED!"
                    startDynamicImageAnchorTracking(response: response, capturedImage: capturedUIImage)
                } else {
                    hasActiveSolutionOverlay = false
                    lastSolveSucceeded = false
                    lastSolveSeconds = nil
                    statusText = "Failed"
                }
            } catch {
                hasActiveSolutionOverlay = false
                lastSolveSucceeded = false
                lastSolveSeconds = nil
                statusText = "Failed"
            }
        }
    }

    func forceResetSolveState() {
        isSolving = false
        hasActiveSolutionOverlay = false
        statusText = "Ready. Fill the corners with the puzzle, then press Solve."
    }

    private func makeUIImage(from pixelBuffer: CVPixelBuffer) -> UIImage? {
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer).oriented(.right)

        guard let cgImage = ciContext.createCGImage(ciImage, from: ciImage.extent) else {
            return nil
        }

        return UIImage(cgImage: cgImage)
    }

    private func makeJPEG(from pixelBuffer: CVPixelBuffer) -> Data? {
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer).oriented(.right)

        guard let cgImage = ciContext.createCGImage(ciImage, from: ciImage.extent) else {
            return nil
        }

        let image = UIImage(cgImage: cgImage)
        return image.jpegData(compressionQuality: 0.85)
    }

    private func removeAllDynamicImageAnchorOverlayNodes() {
        guard let sceneView else { return }

        sceneView.scene.rootNode.enumerateChildNodes { node, _ in
            if node.name == "dynamicImageAnchorSolutionOverlay" {
                node.removeFromParentNode()
            }
        }
    }

    func imageAnchorTrackingLost() {
        // ARKit removed/lost the image anchor. Hide the overlay rather than
        // showing a floating fallback, then actively try to reacquire.
        imageTrackingLostFrameCount = imageTrackingLostGraceFrames
        worldSolutionNode?.isHidden = true
        hasActiveSolutionOverlay = true
        statusText = "Reacquiring puzzle..."
        startPuzzleReacquisitionLoop()
    }


    private func boardFingerprint(_ givens: [[Int]]?) -> String? {
        guard let givens else {
            return nil
        }

        var parts: [String] = []
        for r in 0..<9 {
            for c in 0..<9 {
                let value = givens[safe: r]?[safe: c] ?? 0
                if value != 0 {
                    parts.append("\(r),\(c),\(value)")
                }
            }
        }

        return parts.joined(separator: "|")
    }

    private func boardFingerprintSimilarity(_ a: String?, _ b: String?) -> Double {
        guard let a, let b, !a.isEmpty, !b.isEmpty else {
            return 0.0
        }

        let sa = Set(a.split(separator: "|").map(String.init))
        let sb = Set(b.split(separator: "|").map(String.init))

        guard !sa.isEmpty else {
            return 0.0
        }

        let intersection = sa.intersection(sb).count
        return Double(intersection) / Double(sa.count)
    }

    private func startPuzzleReacquisitionLoop() {
        guard !isReacquiringPuzzle else {
            return
        }

        guard solvedBoardFingerprint != nil else {
            return
        }

        isReacquiringPuzzle = true

        Task {
            var attempts = 0

            while isReacquiringPuzzle && attempts < 12 {
                attempts += 1

                try? await Task.sleep(nanoseconds: 800_000_000)

                guard isReacquiringPuzzle else {
                    break
                }

                guard let sceneView,
                      let frame = sceneView.session.currentFrame,
                      let capturedUIImage = makeUIImage(from: frame.capturedImage),
                      let jpeg = capturedUIImage.jpegData(compressionQuality: 0.82) else {
                    continue
                }

                do {
                    statusText = "Reacquiring puzzle... \(attempts)"

                    let response = try await solverClient.detect(imageJPEG: jpeg, baseURLString: backendURLString)

                    guard response.status == "solved" else {
                        continue
                    }

                    let detectedFingerprint = boardFingerprint(response.givens)
                    let similarity = boardFingerprintSimilarity(solvedBoardFingerprint, detectedFingerprint)

                    if similarity >= 0.70 {
                        statusText = "Puzzle reacquired | match \(String(format: "%.0f%%", similarity * 100))"
                        startDynamicImageAnchorTracking(response: response, capturedImage: capturedUIImage)
                        isReacquiringPuzzle = false
                        return
                    } else {
                        // Different puzzle or bad OCR. Do not attach old answer.
                        statusText = "Different puzzle detected — press Solve"
                        isReacquiringPuzzle = false
                        hasActiveSolutionOverlay = false
                        removeAllDynamicImageAnchorOverlayNodes()
                        worldSolutionNode?.removeFromParentNode()
                        worldSolutionNode = nil
                        return
                    }
                } catch {
                    continue
                }
            }

            if isReacquiringPuzzle {
                isReacquiringPuzzle = false
                statusText = "Puzzle lost — point back at puzzle or press Solve"
            }
        }
    }

    private func startDynamicImageAnchorTracking(response: SolveResponse, capturedImage: UIImage) {
        guard let sceneView else {
            statusText += " | no scene view for image anchor"
            return
        }

        guard let corners = response.cornersPx,
              corners.count == 4,
              let givens = response.givens,
              let solution = response.solution else {
            statusText += " | missing image-anchor inputs"
            return
        }

        guard let referenceCGImage = makeBoardReferenceCGImage(
            from: capturedImage,
            corners: corners,
            marginScale: boardReferenceMarginScale
        ) else {
            statusText += " | board crop failed"
            return
        }

        imageAnchorSolutionTexture = makeSolutionTexture(givens: givens, solution: solution)

        let referenceImage = ARReferenceImage(
            referenceCGImage,
            orientation: .up,
            physicalWidth: boardPhysicalWidthMeters * boardReferenceMarginScale
        )
        referenceImage.name = currentReferenceImageName

        let config = ARWorldTrackingConfiguration()
        config.planeDetection = [.horizontal]
        config.environmentTexturing = .automatic
        config.isAutoFocusEnabled = true
        config.detectionImages = [referenceImage]
        config.maximumNumberOfTrackedImages = 1

        // Do not reset tracking. Keep the current AR world and add image detection.
        sceneView.session.run(config, options: [])

        statusText += " | larger image anchor armed"
    }

    private func makeBoardReferenceCGImage(
        from image: UIImage,
        corners: [[Double]],
        marginScale: CGFloat
    ) -> CGImage? {
        guard let cgImage = image.cgImage else {
            return nil
        }

        guard corners.count == 4 else {
            return nil
        }

        let width = CGFloat(cgImage.width)
        let height = CGFloat(cgImage.height)

        var pts = corners.map { c in
            CGPoint(x: CGFloat(c[0]), y: CGFloat(c[1]))
        }

        let center = CGPoint(
            x: pts.map(\.x).reduce(0, +) / CGFloat(pts.count),
            y: pts.map(\.y).reduce(0, +) / CGFloat(pts.count)
        )

        pts = pts.map { p in
            let x = center.x + (p.x - center.x) * marginScale
            let y = center.y + (p.y - center.y) * marginScale

            return CGPoint(
                x: min(max(x, 0), width - 1),
                y: min(max(y, 0), height - 1)
            )
        }

        let input = CIImage(cgImage: cgImage)

        guard let filter = CIFilter(name: "CIPerspectiveCorrection") else {
            return nil
        }

        // Python/UIImage points use top-left origin.
        // Core Image uses bottom-left origin, so flip y.
        func ciVector(_ p: CGPoint) -> CIVector {
            CIVector(x: p.x, y: height - p.y)
        }

        filter.setValue(input, forKey: kCIInputImageKey)
        filter.setValue(ciVector(pts[0]), forKey: "inputTopLeft")
        filter.setValue(ciVector(pts[1]), forKey: "inputTopRight")
        filter.setValue(ciVector(pts[2]), forKey: "inputBottomRight")
        filter.setValue(ciVector(pts[3]), forKey: "inputBottomLeft")

        guard let output = filter.outputImage else {
            return nil
        }

        let extent = output.extent.integral

        guard extent.width > 100, extent.height > 100 else {
            return nil
        }

        return ciContext.createCGImage(output, from: extent)
    }

    func attachImageAnchorOverlay(to anchorNode: SCNNode, imageAnchor: ARImageAnchor) {
        guard let solutionTexture = imageAnchorSolutionTexture else {
            return
        }

        let overlayName = "dynamicImageAnchorSolutionOverlay"

        // Ignore stale anchors from previous solves/puzzles.
        guard imageAnchor.referenceImage.name == currentReferenceImageName else {
            anchorNode.childNode(withName: overlayName, recursively: false)?.isHidden = true
            return
        }

        // If image tracking drops, hide the overlay instead of showing the
        // less-accurate table/world fallback. The fallback visibly floats/lifts
        // during movement, which is worse than a short reacquire state.
        guard imageAnchor.isTracked else {
            anchorNode.childNode(withName: overlayName, recursively: false)?.isHidden = true
            worldSolutionNode?.isHidden = true
            hasActiveSolutionOverlay = false
            statusText = "Reacquiring puzzle..."
            return
        }

        // Image anchor is actively tracked, so show the precise image overlay.
        worldSolutionNode?.isHidden = true

        let overlayNode: SCNNode

        if let existing = anchorNode.childNode(withName: overlayName, recursively: false) {
            overlayNode = existing
            overlayNode.isHidden = false
        } else {
            // The image anchor tracks a larger crop around the Sudoku board,
            // but the solved digits should cover only the inner Sudoku grid.
            let plane = SCNPlane(
                width: boardPhysicalWidthMeters,
                height: boardPhysicalWidthMeters
            )

            let material = SCNMaterial()
            material.diffuse.contents = solutionTexture
            material.lightingModel = .constant
            material.isDoubleSided = true
            material.transparencyMode = .aOne
            material.blendMode = .alpha
            material.readsFromDepthBuffer = true
            material.writesToDepthBuffer = false
            material.transparency = 0.90

            plane.materials = [material]

            overlayNode = SCNNode(geometry: plane)
            overlayNode.name = overlayName

            // ARImageAnchor lies in X/Z; SCNPlane is X/Y by default.
            overlayNode.eulerAngles.x = -.pi / 2.0

            // Keep almost flush on the image plane.
            overlayNode.position = SCNVector3(0, 0.000003, 0)

            anchorNode.addChildNode(overlayNode)
        }

        hasActiveSolutionOverlay = true
        statusText = "Solved | image-anchor overlay active"
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
        overlayNode.position = SCNVector3(0, 0.00001, 0)

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

            let font = UIFont.systemFont(ofSize: 65, weight: .semibold)

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
    @State private var showBackendSettings = false

    var body: some View {
        ZStack {
            ARSudokuView(appState: appState)
                .ignoresSafeArea()

            if appState.showCaptureGuide && !appState.isSolving {
                CornerCaptureGuide()
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
            }

            VStack {
                statusPanel
                    .padding(.top, 12)
                    .padding(.horizontal, 12)

                backendPanel
                    .padding(.horizontal, 12)

                Spacer()

                bottomControls
                    .padding(.horizontal, 18)
                    .padding(.bottom, 28)
            }
        }
    }

    private var backendPanel: some View {
        VStack(spacing: 8) {
            HStack {
                Button {
                    showBackendSettings.toggle()
                } label: {
                    Text(showBackendSettings ? "Hide Backend" : "Backend")
                        .font(.caption)
                        .bold()
                }

                Spacer()

                Button {
                    appState.pingBackend()
                } label: {
                    Text("Ping")
                        .font(.caption)
                        .bold()
                }
            }

            if showBackendSettings {
                TextField(
                    "http://<MAC_WIFI_IP>:8000",
                    text: Binding(
                        get: { appState.backendURLString },
                        set: { appState.updateBackendURL($0) }
                    )
                )
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled(true)
                .keyboardType(.URL)
                .font(.caption)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(Color.white.opacity(0.92))
                .foregroundStyle(.black)
                .clipShape(RoundedRectangle(cornerRadius: 10))

                Text("Use your Mac Wi-Fi IP while the local FastAPI backend is running.")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.86))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(
            Color.black.opacity(0.34)
                .clipShape(RoundedRectangle(cornerRadius: 14))
        )
        .foregroundStyle(.white)
        .shadow(radius: 3)
    }

    private var statusPanel: some View {
        VStack(spacing: 3) {
            if appState.isSolving {
                Text("Solving")
                    .font(.headline)
                    .bold()
            } else if appState.lastSolveSucceeded {
                Text("SOLVED!")
                    .font(.headline)
                    .bold()

                if let seconds = appState.lastSolveSeconds {
                    Text(String(format: "%.2f seconds", seconds))
                        .font(.caption)
                        .monospacedDigit()
                }
            } else if appState.hasAttemptedSolve {
                Text("Failed")
                    .font(.headline)
                    .bold()
            } else {
                Text("Line up puzzle")
                    .font(.caption)
                    .bold()
            }
        }
        .foregroundStyle(.white)
        .shadow(radius: 3)
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
        .background(
            Color.black.opacity(0.34)
                .clipShape(RoundedRectangle(cornerRadius: 14))
        )
        .allowsHitTesting(false)
    }

    private var bottomControls: some View {
        HStack(spacing: 12) {
            Button {
                appState.sendCurrentFrameToSolver()
            } label: {
                Text(appState.hasActiveSolutionOverlay ? "Re-scan" : "Scan")
                    .font(.headline)
                    .bold()
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .foregroundStyle(.white)
            .background(
                appState.isSolving
                ? Color.gray.opacity(0.65)
                : Color.blue.opacity(0.86)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .disabled(appState.isSolving)

            Button {
                appState.clearDisplayedSolution()
            } label: {
                Text("Clear")
                    .font(.headline)
                    .bold()
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .foregroundStyle(.white)
            .background(Color.black.opacity(0.52))
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
        .shadow(radius: 4)
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

        func renderer(_ renderer: SCNSceneRenderer, didAdd node: SCNNode, for anchor: ARAnchor) {
            guard let imageAnchor = anchor as? ARImageAnchor else {
                return
            }

            Task { @MainActor in
                self.appState?.attachImageAnchorOverlay(to: node, imageAnchor: imageAnchor)
            }
        }

        func renderer(_ renderer: SCNSceneRenderer, didUpdate node: SCNNode, for anchor: ARAnchor) {
            guard let imageAnchor = anchor as? ARImageAnchor else {
                return
            }

            Task { @MainActor in
                self.appState?.attachImageAnchorOverlay(to: node, imageAnchor: imageAnchor)
            }
        }

        func renderer(_ renderer: SCNSceneRenderer, didRemove node: SCNNode, for anchor: ARAnchor) {
            guard anchor is ARImageAnchor else {
                return
            }

            Task { @MainActor in
                self.appState?.imageAnchorTrackingLost()
            }
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
