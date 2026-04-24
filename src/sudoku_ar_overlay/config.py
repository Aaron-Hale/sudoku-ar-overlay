from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayConfig:
    board_size_px: int = 900
    cell_size_px: int = 100
    font_scale: float = 1.7
    font_thickness: int = 4
    alpha: float = 0.85


@dataclass(frozen=True)
class TrackingConfig:
    smoothing_alpha: float = 0.25
    lost_after_frames: int = 15
    detection_every_n_frames: int = 5
