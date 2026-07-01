import pytest

from app.cdm.adapters.local_pipeline.config import (
    CamelotConfig,
    FitzConfig,
    FitzTablesConfig,
    LocalPipelineConfig,
    TABLE_TOOL_IDS,
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


def test_fitz_tables_config_defaults():
    c = FitzTablesConfig()
    assert c.vertical_strategy == "lines_strict"
    assert c.horizontal_strategy == "lines_strict"
    assert c.snap_tolerance == 3.0
    assert c.join_tolerance == 3.0
    assert c.edge_min_length == 3.0
    assert c.min_words_vertical == 3
    assert c.min_words_horizontal == 1
    assert c.intersection_tolerance == 3.0
    assert c.text_tolerance == 3.0
    assert c.snap_x_tolerance is None
    assert c.snap_y_tolerance is None
    assert c.join_x_tolerance is None
    assert c.join_y_tolerance is None
    assert c.intersection_x_tolerance is None
    assert c.intersection_y_tolerance is None
    assert c.text_x_tolerance is None
    assert c.text_y_tolerance is None


def test_table_tool_ids_contains_camelot_and_fitz_tables():
    assert "camelot" in TABLE_TOOL_IDS
    assert "fitz_tables" in TABLE_TOOL_IDS


def test_build_pipeline_config_rejects_multiple_table_tools():
    with pytest.raises(ValueError, match="only one table tool allowed"):
        build_pipeline_config({
            "tools": [
                {"tool_id": "fitz", "config": {}},
                {"tool_id": "fitz_tables", "config": {}},
                {"tool_id": "camelot", "config": {}},
            ],
        })


def test_build_pipeline_config_fitz_and_fitz_tables():
    cfg = build_pipeline_config({
        "tools": [
            {"tool_id": "fitz", "config": {}},
            {"tool_id": "fitz_tables", "config": {}},
        ],
    })
    assert [t.tool_id for t in cfg.tools] == ["fitz", "fitz_tables"]
