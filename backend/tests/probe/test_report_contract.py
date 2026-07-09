from app.probe.report import (
    BBox, Signal, Observation, RegionFinding, PageProfile, ProbeReport,
)
from app.probe.config import ProbeConfig, DEFAULT_CONFIG


def test_probe_report_roundtrips_json():
    region = RegionFinding(
        id="p0:img0", page_index=0, kind="image",
        bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
        signals=[Signal(name="edge_density", value=0.21, unit=None, strength=0.85, detail="sobel")],
        observation=Observation(label="text_image", confidence=0.88),
    )
    page = PageProfile(index=0, page_type="scanned", signals=[], regions=[region])
    report = ProbeReport(
        document_id="doc-1", filename="a.pdf", page_count=1,
        inspection={"backend": "fitz", "backend_version": "1.27", "config_used": DEFAULT_CONFIG.model_dump()},
        pages=[page], suggestion=None, duration_ms=5, probed_at="2026-07-09T00:00:00Z",
    )
    dumped = report.model_dump(mode="json")
    assert dumped["pages"][0]["regions"][0]["observation"]["label"] == "text_image"
    assert ProbeReport.model_validate(dumped).pages[0].regions[0].observation.confidence == 0.88


def test_default_config_has_all_signals_and_thresholds():
    cfg = ProbeConfig()
    assert set(cfg.enabled_signals) == {
        "text_layer", "font_health", "copy_restricted",
        "coverage", "dpi", "text_overlap", "table_grid", "edge_density",
    }
    assert cfg.thresholds.edge_density_min == 0.15
    assert cfg.backend == "fitz"
