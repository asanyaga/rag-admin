import pytest

from app.cdm.adapters.local_pipeline.config import (
    CamelotConfig,
    FitzConfig,
    LocalPipelineConfig,
    build_pipeline_config,
)


def test_fitz_config_defaults():
    c = FitzConfig()
    assert c.min_chars_threshold == 10
    assert c.include_images is True
    assert c.span_detail is False


def test_camelot_config_defaults():
    c = CamelotConfig()
    assert c.flavor == "lattice"
    assert c.edge_tol == 50
    assert c.row_tol == 2
    assert c.copy_text == []


def test_build_pipeline_config_fitz_only():
    cfg = build_pipeline_config({
        "tools": [{"tool_id": "fitz", "config": {"min_chars_threshold": 5}}],
        "eviction_overlap_threshold": 0.4,
    })
    assert isinstance(cfg, LocalPipelineConfig)
    assert cfg.eviction_overlap_threshold == 0.4
    assert [t.tool_id for t in cfg.tools] == ["fitz"]


def test_build_pipeline_config_fitz_and_camelot_order_preserved():
    cfg = build_pipeline_config({
        "tools": [
            {"tool_id": "fitz", "config": {}},
            {"tool_id": "camelot", "config": {"flavor": "stream"}},
        ],
    })
    assert [t.tool_id for t in cfg.tools] == ["fitz", "camelot"]
    assert cfg.eviction_overlap_threshold == 0.5  # default


def test_build_pipeline_config_rejects_unknown_tool():
    with pytest.raises(ValueError, match="unknown tool"):
        build_pipeline_config({"tools": [{"tool_id": "bogus", "config": {}}]})
