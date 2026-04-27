from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class ReacquisitionCandidate:
    frame_idx: int
    corners: np.ndarray
    frame_shape: tuple[int, int, int]
    fit_error_px: float
    score: float
    reason: str


@dataclass
class StabilityResult:
    stable: bool
    candidate: ReacquisitionCandidate | None
    center_motion_frac: float
    area_ratio: float
    corner_motion_frac: float
    reason: str


def quad_area_px(corners: np.ndarray) -> float:
    pts = np.asarray(corners, dtype="float32").reshape(4, 2)
    return float(abs(cv2.contourArea(pts.reshape(-1, 1, 2))))


def quad_center_px(corners: np.ndarray) -> np.ndarray:
    return np.asarray(corners, dtype="float32").reshape(4, 2).mean(axis=0)


class CandidateStabilityBuffer:
    """Tracks candidate board detections and releases only stable candidates.

    This prevents overlay initialization while the board is still entering the
    frame, moving quickly, or producing unstable rough corners.
    """

    def __init__(
        self,
        *,
        min_frames: int = 4,
        max_history: int = 12,
        max_center_motion_frac: float = 0.025,
        max_area_ratio: float = 1.18,
        max_corner_motion_frac: float = 0.035,
        max_fit_error_px: float = 14.0,
    ) -> None:
        self.min_frames = min_frames
        self.max_center_motion_frac = max_center_motion_frac
        self.max_area_ratio = max_area_ratio
        self.max_corner_motion_frac = max_corner_motion_frac
        self.max_fit_error_px = max_fit_error_px
        self._items: deque[ReacquisitionCandidate] = deque(maxlen=max_history)

    def reset(self) -> None:
        self._items.clear()

    def push(self, candidate: ReacquisitionCandidate) -> StabilityResult:
        self._items.append(candidate)

        if len(self._items) < self.min_frames:
            return StabilityResult(
                stable=False,
                candidate=None,
                center_motion_frac=999.0,
                area_ratio=999.0,
                corner_motion_frac=999.0,
                reason=f"pending {len(self._items)}/{self.min_frames}",
            )

        recent = list(self._items)[-self.min_frames :]
        h, w = recent[-1].frame_shape[:2]
        diag = float((h * h + w * w) ** 0.5)

        centers = np.array([quad_center_px(c.corners) for c in recent], dtype="float32")
        center_span = float(np.linalg.norm(centers - centers.mean(axis=0), axis=1).max())
        center_motion_frac = center_span / max(diag, 1.0)

        areas = np.array([quad_area_px(c.corners) for c in recent], dtype="float32")
        area_ratio = float(areas.max() / max(areas.min(), 1.0))

        corner_stack = np.array(
            [np.asarray(c.corners, dtype="float32").reshape(4, 2) for c in recent],
            dtype="float32",
        )
        mean_corners = corner_stack.mean(axis=0)
        corner_motion = float(np.linalg.norm(corner_stack - mean_corners, axis=2).max())
        corner_motion_frac = corner_motion / max(diag, 1.0)

        worst_fit = max(c.fit_error_px for c in recent)

        stable = (
            center_motion_frac <= self.max_center_motion_frac
            and area_ratio <= self.max_area_ratio
            and corner_motion_frac <= self.max_corner_motion_frac
            and worst_fit <= self.max_fit_error_px
        )

        if stable:
            reason = (
                f"stable: center={center_motion_frac:.3f} "
                f"area_ratio={area_ratio:.2f} "
                f"corner={corner_motion_frac:.3f} "
                f"fit={worst_fit:.1f}px"
            )
            return StabilityResult(
                stable=True,
                candidate=recent[-1],
                center_motion_frac=center_motion_frac,
                area_ratio=area_ratio,
                corner_motion_frac=corner_motion_frac,
                reason=reason,
            )

        reason = (
            f"unstable: center={center_motion_frac:.3f} "
            f"area_ratio={area_ratio:.2f} "
            f"corner={corner_motion_frac:.3f} "
            f"fit={worst_fit:.1f}px"
        )
        return StabilityResult(
            stable=False,
            candidate=None,
            center_motion_frac=center_motion_frac,
            area_ratio=area_ratio,
            corner_motion_frac=corner_motion_frac,
            reason=reason,
        )
