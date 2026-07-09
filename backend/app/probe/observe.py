from __future__ import annotations
from typing import Dict, List, Optional
from app.probe.config import ProbeConfig
from app.probe.report import Observation, Signal


def _by_name(signals: List[Signal]) -> Dict[str, Signal]:
    return {s.name: s for s in signals}


def _f(sig: Optional[Signal], default: float = 0.0) -> float:
    if sig is None or not isinstance(sig.value, (int, float)):
        return default
    return float(sig.value)


def observe_image(signals: List[Signal], cfg: ProbeConfig) -> Observation:
    s = _by_name(signals)
    overlap = _f(s.get("text_overlap"))
    edge = _f(s.get("edge_density"))
    edge_strength = s.get("edge_density").strength if s.get("edge_density") else 0.0
    coverage = _f(s.get("coverage"))
    t = cfg.thresholds

    if overlap >= t.overlap_covered:
        return Observation(label="text_covered_image", confidence=round(overlap, 3))

    matters = coverage >= t.coverage_min
    if edge >= t.edge_density_min and matters:
        conf = round(0.6 * (edge_strength or 0.0) + 0.4 * min(coverage, 1.0), 3)
        return Observation(label="text_image", confidence=conf)
    if edge < t.edge_density_min / 2 and matters:
        return Observation(label="decorative_image", confidence=round(1.0 - (edge_strength or 0.0), 3))
    return Observation(label="uncertain", confidence=0.4)


def observe_table(signals: List[Signal], cfg: ProbeConfig) -> Observation:
    s = _by_name(signals)
    grid = s.get("table_grid")
    return Observation(label="table_grid", confidence=round(grid.strength if grid else 0.5, 3))
