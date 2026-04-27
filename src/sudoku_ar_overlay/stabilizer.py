from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from sudoku_ar_overlay.overlay import order_corners_clockwise


@dataclass
class StabilizerResult:
    accepted: bool
    corners: np.ndarray | None
    reason: str
    alpha_used: float = 0.0
    mean_motion_px: float = 0.0


class CornerStabilizer:
    """Stabilizes detected board corners before rendering.

    This sits between raw segmentation output and the AR overlay.

    Pipeline:
      raw corners
        -> quality threshold
        -> jump rejection
        -> median over recent detections
        -> adaptive exponential smoothing
        -> stabilized render corners
    """

    def __init__(
        self,
        median_window: int = 5,
        min_quality: float = 0.30,
        static_alpha: float = 0.12,
        moving_alpha: float = 0.55,
        static_motion_px: float = 5.0,
        fast_motion_px: float = 45.0,
        max_jump_ratio: float = 0.25,
    ) -> None:
        self.history: deque[np.ndarray] = deque(maxlen=max(1, median_window))
        self.previous: np.ndarray | None = None

        self.min_quality = min_quality
        self.static_alpha = static_alpha
        self.moving_alpha = moving_alpha
        self.static_motion_px = static_motion_px
        self.fast_motion_px = fast_motion_px
        self.max_jump_ratio = max_jump_ratio

    def reset(self) -> None:
        self.history.clear()
        self.previous = None

    def update(
        self,
        detected_corners: np.ndarray,
        quality: float,
        frame_shape: tuple[int, int, int],
    ) -> StabilizerResult:
        if detected_corners is None:
            return StabilizerResult(False, self.previous, "no detected corners")

        if quality < self.min_quality:
            return StabilizerResult(
                False,
                self.previous,
                f"quality below threshold: {quality:.2f} < {self.min_quality:.2f}",
            )

        current = order_corners_clockwise(detected_corners).astype("float32")
        frame_h, frame_w = frame_shape[:2]
        frame_diag = float(np.hypot(frame_w, frame_h))

        mean_motion_px = 0.0

        if self.previous is not None:
            mean_motion_px = float(np.mean(np.linalg.norm(current - self.previous, axis=1)))
            jump_ratio = mean_motion_px / max(frame_diag, 1.0)

            if jump_ratio > self.max_jump_ratio:
                return StabilizerResult(
                    False,
                    self.previous,
                    f"rejected jump: {jump_ratio:.3f} > {self.max_jump_ratio:.3f}",
                    mean_motion_px=mean_motion_px,
                )

        self.history.append(current)

        stacked = np.stack(list(self.history), axis=0)
        median_corners = np.median(stacked, axis=0).astype("float32")

        if self.previous is None:
            self.previous = median_corners
            return StabilizerResult(
                True,
                self.previous,
                "initialized",
                alpha_used=1.0,
                mean_motion_px=0.0,
            )

        median_motion_px = float(np.mean(np.linalg.norm(median_corners - self.previous, axis=1)))

        if median_motion_px <= self.static_motion_px:
            alpha = self.static_alpha
        elif median_motion_px >= self.fast_motion_px:
            alpha = self.moving_alpha
        else:
            t = (median_motion_px - self.static_motion_px) / max(
                self.fast_motion_px - self.static_motion_px,
                1e-6,
            )
            alpha = self.static_alpha + t * (self.moving_alpha - self.static_alpha)

        smoothed = alpha * median_corners + (1.0 - alpha) * self.previous
        self.previous = smoothed.astype("float32")

        return StabilizerResult(
            True,
            self.previous,
            "accepted",
            alpha_used=float(alpha),
            mean_motion_px=median_motion_px,
        )
