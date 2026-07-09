import numpy as np
from app.probe.config import ProbeConfig
from app.probe.signals.edge_density import edge_density


def _text_like():
    # Dense, high-frequency variation like packed text strokes.
    rng = np.random.default_rng(42)
    return (rng.integers(0, 2, size=(64, 64)) * 255).astype(np.uint8)


def _smooth():
    # A gentle gradient like a photo/background — few sharp edges.
    return np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (64, 1))


def test_text_like_pattern_has_higher_density_than_smooth():
    d_text = float(edge_density(_text_like(), ProbeConfig()).value)
    d_smooth = float(edge_density(_smooth(), ProbeConfig()).value)
    assert d_text > d_smooth


def test_strength_crosses_threshold_for_text_like():
    sig = edge_density(_text_like(), ProbeConfig())
    assert sig.name == "edge_density"
    assert sig.strength >= 0.5
