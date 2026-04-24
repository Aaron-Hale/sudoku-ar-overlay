from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class BoardStatus(str, Enum):
    NO_BOARD = "NO_BOARD"
    BOARD_DETECTED = "BOARD_DETECTED"
    SOLVED_TRACKING = "SOLVED_TRACKING"
    TRACKING_LOST = "TRACKING_LOST"
    REACQUIRED = "REACQUIRED"


@dataclass
class BoardSession:
    status: BoardStatus = BoardStatus.NO_BOARD
    givens: Optional[list[list[int]]] = None
    solution: Optional[list[list[int]]] = None
    missing_mask: Optional[list[list[bool]]] = None
    last_corners: Optional[np.ndarray] = None
    smoothed_corners: Optional[np.ndarray] = None
    last_seen_frame_idx: int = -1
    solved_at_frame_idx: int = -1
    solve_latency_ms: float = 0.0
    tracking_quality: float = 0.0

    def reset(self) -> None:
        self.status = BoardStatus.NO_BOARD
        self.givens = None
        self.solution = None
        self.missing_mask = None
        self.last_corners = None
        self.smoothed_corners = None
        self.last_seen_frame_idx = -1
        self.solved_at_frame_idx = -1
        self.solve_latency_ms = 0.0
        self.tracking_quality = 0.0

    def set_solved(
        self,
        givens: list[list[int]],
        solution: list[list[int]],
        corners: np.ndarray,
        frame_idx: int,
        solve_latency_ms: float = 0.0,
    ) -> None:
        self.givens = givens
        self.solution = solution
        self.missing_mask = [[givens[r][c] == 0 for c in range(9)] for r in range(9)]
        self.last_corners = corners.astype("float32")
        self.smoothed_corners = corners.astype("float32")
        self.last_seen_frame_idx = frame_idx
        self.solved_at_frame_idx = frame_idx
        self.solve_latency_ms = solve_latency_ms
        self.status = BoardStatus.SOLVED_TRACKING
