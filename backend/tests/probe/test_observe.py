from app.probe.config import ProbeConfig
from app.probe.observe import observe_image, observe_table
from app.probe.report import Signal


def _sig(name, value, strength=None):
    return Signal(name=name, value=value, strength=strength)


def test_text_covered_when_overlap_high():
    sigs = [_sig("text_overlap", 0.9, 0.9), _sig("edge_density", 0.2, 0.9), _sig("coverage", 0.5, 0.5)]
    obs = observe_image(sigs, ProbeConfig())
    assert obs.label == "text_covered_image"


def test_text_image_when_edgey_and_no_overlap():
    sigs = [_sig("text_overlap", 0.0, 0.0), _sig("edge_density", 0.22, 0.9), _sig("coverage", 0.9, 0.9)]
    obs = observe_image(sigs, ProbeConfig())
    assert obs.label == "text_image"
    assert obs.confidence > 0.6


def test_decorative_when_smooth_and_no_overlap():
    sigs = [_sig("text_overlap", 0.0, 0.0), _sig("edge_density", 0.02, 0.05), _sig("coverage", 0.95, 0.95)]
    obs = observe_image(sigs, ProbeConfig())
    assert obs.label == "decorative_image"


def test_uncertain_when_signals_disagree():
    sigs = [_sig("text_overlap", 0.0, 0.0), _sig("edge_density", 0.12, 0.4), _sig("coverage", 0.05, 0.05)]
    obs = observe_image(sigs, ProbeConfig())
    assert obs.label == "uncertain"


def test_observe_table():
    obs = observe_table([_sig("table_grid", 14.0, 0.8)], ProbeConfig())
    assert obs.label == "table_grid" and obs.confidence == 0.8
