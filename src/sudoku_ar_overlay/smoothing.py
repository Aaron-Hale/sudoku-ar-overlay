import numpy as np


def smooth_corners(
    previous: np.ndarray | None,
    current: np.ndarray,
    alpha: float = 0.25,
) -> np.ndarray:
    """Exponential moving average for four board corners."""
    current = current.astype("float32")

    if previous is None:
        return current

    previous = previous.astype("float32")
    return alpha * current + (1.0 - alpha) * previous
