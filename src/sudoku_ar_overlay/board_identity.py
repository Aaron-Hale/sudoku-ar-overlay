from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from sudoku_ar_overlay.grid_validation import warp_candidate


@dataclass
class BoardFingerprint:
    """Compact visual identity for a Sudoku board.

    The fingerprint intentionally emphasizes cell interiors and avoids grid lines.
    This makes it more useful for telling two printed Sudoku puzzles apart than a
    full-board template where the black grid dominates the correlation score.
    """

    vector: np.ndarray
    occupancy: np.ndarray
    size: int
    cell_size: int


@dataclass
class KnownBoard:
    board_id: int
    givens: Any
    solution: Any
    fingerprint: BoardFingerprint
    frame_idx: int
    solve_latency_ms: float
    label: str


@dataclass
class BoardMatch:
    ok: bool
    score: float
    corr_score: float
    occupancy_score: float
    known_board: KnownBoard | None
    reason: str


def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    vec = vec.astype("float32").reshape(-1)
    mean = float(vec.mean())
    std = float(vec.std())
    if std < 1e-6:
        return vec * 0.0
    return (vec - mean) / std


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    aa = _normalize_vector(a)
    bb = _normalize_vector(b)
    denom = float(np.linalg.norm(aa) * np.linalg.norm(bb))
    if denom < 1e-6:
        return 0.0
    return float(np.dot(aa, bb) / denom)


def create_board_fingerprint(
    frame_bgr: np.ndarray,
    corners: np.ndarray,
    *,
    size: int = 450,
    cell_size: int = 24,
    inner_frac: float = 0.58,
) -> BoardFingerprint:
    """Create a same-board visual fingerprint from a Sudoku candidate.

    The board is warped to a canonical square. For each of the 81 cells, only the
    center portion is used so that grid lines do not dominate the match. The
    resulting vector captures printed givens / page texture / cell appearance.
    """

    warp = warp_candidate(frame_bgr, corners, size=size)
    gray = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Normalize lighting while preserving printed digit structure.
    gray = cv2.equalizeHist(gray)

    cell = size / 9.0
    half_inner = (cell * inner_frac) / 2.0

    crops = []
    occupancy = []

    for r in range(9):
        for c in range(9):
            cx = (c + 0.5) * cell
            cy = (r + 0.5) * cell
            x0 = max(0, int(round(cx - half_inner)))
            x1 = min(size, int(round(cx + half_inner)))
            y0 = max(0, int(round(cy - half_inner)))
            y1 = min(size, int(round(cy + half_inner)))

            crop = gray[y0:y1, x0:x1]
            if crop.size == 0:
                crop = np.full((cell_size, cell_size), 255, dtype=np.uint8)

            crop = cv2.resize(crop, (cell_size, cell_size), interpolation=cv2.INTER_AREA)
            darkness = (255.0 - crop.astype("float32")) / 255.0

            # Printed digits create more dark/edge structure than blank cells.
            occupancy.append(float(darkness.mean() > 0.16))
            crops.append(darkness)

    vector = np.stack(crops, axis=0).reshape(-1).astype("float32")
    occ = np.asarray(occupancy, dtype="float32")

    return BoardFingerprint(
        vector=vector,
        occupancy=occ,
        size=size,
        cell_size=cell_size,
    )


def compare_board_fingerprints(a: BoardFingerprint, b: BoardFingerprint) -> tuple[float, float, float]:
    corr_score = _corr(a.vector, b.vector)

    if a.occupancy.shape == b.occupancy.shape and a.occupancy.size:
        occupancy_score = float((a.occupancy == b.occupancy).mean())
    else:
        occupancy_score = 0.0

    # Clamp correlation into [0, 1]-ish range before mixing.
    corr01 = max(0.0, min(1.0, (corr_score + 1.0) / 2.0))
    score = 0.70 * corr01 + 0.30 * occupancy_score
    return float(score), float(corr01), float(occupancy_score)


class KnownBoardRegistry:
    """Stores solved boards and matches returning candidates to known identities."""

    def __init__(self, *, max_boards: int = 8, match_threshold: float = 0.78, size: int = 450) -> None:
        self.max_boards = int(max_boards)
        self.match_threshold = float(match_threshold)
        self.size = int(size)
        self._boards: list[KnownBoard] = []
        self._next_id = 1

    @property
    def boards(self) -> list[KnownBoard]:
        return list(self._boards)

    def add(
        self,
        *,
        frame_bgr: np.ndarray,
        corners: np.ndarray,
        givens: Any,
        solution: Any,
        frame_idx: int,
        solve_latency_ms: float = 0.0,
        label: str = "",
    ) -> KnownBoard:
        fp = create_board_fingerprint(frame_bgr, corners, size=self.size)
        board = KnownBoard(
            board_id=self._next_id,
            givens=givens,
            solution=solution,
            fingerprint=fp,
            frame_idx=frame_idx,
            solve_latency_ms=float(solve_latency_ms or 0.0),
            label=label or f"board_{self._next_id}",
        )
        self._next_id += 1

        self._boards.append(board)
        if len(self._boards) > self.max_boards:
            self._boards = self._boards[-self.max_boards :]

        return board

    def match(self, frame_bgr: np.ndarray, corners: np.ndarray) -> BoardMatch:
        if not self._boards:
            return BoardMatch(False, 0.0, 0.0, 0.0, None, "no known boards")

        try:
            candidate_fp = create_board_fingerprint(frame_bgr, corners, size=self.size)
        except Exception as exc:
            return BoardMatch(False, 0.0, 0.0, 0.0, None, f"fingerprint failed: {type(exc).__name__}: {exc}")

        best: tuple[float, float, float, KnownBoard] | None = None
        for board in self._boards:
            score, corr_score, occupancy_score = compare_board_fingerprints(candidate_fp, board.fingerprint)
            if best is None or score > best[0]:
                best = (score, corr_score, occupancy_score, board)

        if best is None:
            return BoardMatch(False, 0.0, 0.0, 0.0, None, "no known boards")

        score, corr_score, occupancy_score, board = best
        ok = score >= self.match_threshold
        reason = (
            f"known-board {'match' if ok else 'miss'}: "
            f"id={board.board_id} score={score:.3f} "
            f"corr={corr_score:.3f} occ={occupancy_score:.3f} "
            f"threshold={self.match_threshold:.3f}"
        )
        return BoardMatch(ok, score, corr_score, occupancy_score, board, reason)
