from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from sudoku_ar_overlay.overlay import order_corners_clockwise
from sudoku_ar_overlay.tracking import score_corners


@dataclass
class FlowTrackingResult:
    ok: bool
    corners: np.ndarray | None
    reason: str
    num_points: int = 0
    num_inliers: int = 0
    inlier_ratio: float = 0.0


class FlowHomographyTracker:
    """Fast frame-to-frame planar tracker using optical flow + homography.

    Intended role:
      - segmentation initializes or refreshes absolute board corners
      - optical flow tracks board motion every frame
      - homography updates board corners from previous frame to current frame
    """

    def __init__(
        self,
        max_corners: int = 250,
        quality_level: float = 0.01,
        min_distance: int = 7,
        block_size: int = 7,
        min_points: int = 25,
        min_inlier_ratio: float = 0.45,
        ransac_reproj_threshold: float = 4.0,
        refresh_points_every: int = 15,
    ) -> None:
        self.max_corners = max_corners
        self.quality_level = quality_level
        self.min_distance = min_distance
        self.block_size = block_size
        self.min_points = min_points
        self.min_inlier_ratio = min_inlier_ratio
        self.ransac_reproj_threshold = ransac_reproj_threshold
        self.refresh_points_every = refresh_points_every

        self.prev_gray: np.ndarray | None = None
        self.prev_pts: np.ndarray | None = None
        self.corners: np.ndarray | None = None
        self.frames_since_refresh = 0
        self.initialized = False

    def reset(self) -> None:
        self.prev_gray = None
        self.prev_pts = None
        self.corners = None
        self.frames_since_refresh = 0
        self.initialized = False

    def initialize(self, frame_bgr: np.ndarray, corners: np.ndarray) -> FlowTrackingResult:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        ordered = order_corners_clockwise(corners).astype("float32")

        pts = self._detect_points(gray, ordered)

        if pts is None or len(pts) < self.min_points:
            self.reset()
            num = 0 if pts is None else len(pts)
            return FlowTrackingResult(
                ok=False,
                corners=None,
                reason=f"not enough feature points to initialize: {num}",
                num_points=num,
            )

        self.prev_gray = gray
        self.prev_pts = pts
        self.corners = ordered
        self.frames_since_refresh = 0
        self.initialized = True

        return FlowTrackingResult(
            ok=True,
            corners=self.corners,
            reason="initialized",
            num_points=len(pts),
        )

    def update(self, frame_bgr: np.ndarray) -> FlowTrackingResult:
        if (
            not self.initialized
            or self.prev_gray is None
            or self.prev_pts is None
            or self.corners is None
        ):
            return FlowTrackingResult(False, None, "tracker not initialized")

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            self.prev_gray,
            gray,
            self.prev_pts,
            None,
            winSize=(21, 21),
            maxLevel=3,
            criteria=(
                cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                30,
                0.01,
            ),
        )

        if next_pts is None or status is None:
            self.reset()
            return FlowTrackingResult(False, None, "optical flow failed")

        status = status.reshape(-1).astype(bool)
        old_good = self.prev_pts.reshape(-1, 2)[status]
        new_good = next_pts.reshape(-1, 2)[status]

        if len(old_good) < self.min_points:
            self.reset()
            return FlowTrackingResult(
                False,
                None,
                f"too few tracked points: {len(old_good)}",
                num_points=len(old_good),
            )

        H, inlier_mask = cv2.findHomography(
            old_good,
            new_good,
            cv2.RANSAC,
            self.ransac_reproj_threshold,
        )

        if H is None or inlier_mask is None:
            self.reset()
            return FlowTrackingResult(
                False,
                None,
                "homography failed",
                num_points=len(old_good),
            )

        inlier_mask = inlier_mask.reshape(-1).astype(bool)
        num_inliers = int(inlier_mask.sum())
        inlier_ratio = num_inliers / max(len(old_good), 1)

        if num_inliers < self.min_points or inlier_ratio < self.min_inlier_ratio:
            self.reset()
            return FlowTrackingResult(
                False,
                None,
                f"bad homography inliers: {num_inliers}/{len(old_good)}",
                num_points=len(old_good),
                num_inliers=num_inliers,
                inlier_ratio=float(inlier_ratio),
            )

        new_corners = cv2.perspectiveTransform(
            self.corners.reshape(1, 4, 2).astype("float32"),
            H,
        ).reshape(4, 2)

        scored = score_corners(
            new_corners,
            frame_shape=frame_bgr.shape,
            previous_corners=self.corners,
        )

        if not scored.detected or scored.corners is None:
            self.reset()
            return FlowTrackingResult(
                False,
                None,
                f"corner sanity failed: {scored.reason}",
                num_points=len(old_good),
                num_inliers=num_inliers,
                inlier_ratio=float(inlier_ratio),
            )

        self.corners = scored.corners.astype("float32")
        self.prev_gray = gray
        self.prev_pts = new_good[inlier_mask].reshape(-1, 1, 2).astype("float32")
        self.frames_since_refresh += 1

        if self.frames_since_refresh >= self.refresh_points_every:
            refreshed_pts = self._detect_points(gray, self.corners)
            if refreshed_pts is not None and len(refreshed_pts) >= self.min_points:
                self.prev_pts = refreshed_pts
                self.frames_since_refresh = 0

        return FlowTrackingResult(
            ok=True,
            corners=self.corners,
            reason="tracked",
            num_points=len(self.prev_pts) if self.prev_pts is not None else len(old_good),
            num_inliers=num_inliers,
            inlier_ratio=float(inlier_ratio),
        )

    def _detect_points(self, gray: np.ndarray, corners: np.ndarray) -> np.ndarray | None:
        mask = np.zeros(gray.shape, dtype=np.uint8)
        poly = order_corners_clockwise(corners).astype(np.int32).reshape(-1, 1, 2)

        cv2.fillConvexPoly(mask, poly, 255)

        # Slight erosion keeps points away from board edges/background.
        kernel = np.ones((9, 9), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)

        pts = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=self.max_corners,
            qualityLevel=self.quality_level,
            minDistance=self.min_distance,
            mask=mask,
            blockSize=self.block_size,
        )

        if pts is None:
            return None

        return pts.astype("float32")
