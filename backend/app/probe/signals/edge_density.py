from __future__ import annotations
import numpy as np
from app.probe.config import ProbeConfig
from app.probe.report import Signal

_KX = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
_KY = _KX.T


def _convolve2d(a: np.ndarray, k: np.ndarray) -> np.ndarray:
    padded = np.pad(a, 1, mode="edge")
    out = np.zeros_like(a, dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            out += k[dy, dx] * padded[dy:dy + a.shape[0], dx:dx + a.shape[1]]
    return out


def edge_density(gray: np.ndarray, cfg: ProbeConfig) -> Signal:
    if gray.size == 0 or min(gray.shape) == 0:
        # Degenerate/hairline region rasterized to a zero-size axis — nothing to assess.
        return Signal(name="edge_density", value=0.0, unit="fraction", strength=0.0,
                      detail="empty region")
    g = gray.astype(np.float32) / 255.0
    gx = _convolve2d(g, _KX)
    gy = _convolve2d(g, _KY)
    mag = np.sqrt(gx * gx + gy * gy)
    ratio = float((mag > 0.5).mean())   # fraction of strong-gradient pixels
    strength = min(ratio / (cfg.thresholds.edge_density_min * 2), 1.0)
    return Signal(name="edge_density", value=round(ratio, 4), unit="fraction",
                  strength=round(strength, 4), detail="sobel gradient-magnitude ratio")
