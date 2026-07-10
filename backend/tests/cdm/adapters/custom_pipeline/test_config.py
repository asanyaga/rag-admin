import pytest

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import build_pipeline_config

BASE = {
    "tools": {"fitz": {"tool": "fitz", "config": {}}},
    "capabilities": {"text_extraction": "fitz"},
}


def test_builds_a_single_slot_pipeline():
    p = build_pipeline_config(BASE)
    inst = p.for_capability(Capability.TEXT_EXTRACTION)
    assert inst.key == "fitz"
    assert inst.tool.tool_id == "fitz"
    assert inst.emit == frozenset({Capability.TEXT_EXTRACTION})
    assert p.for_capability(Capability.TABLE_DETECTION) is None


def test_one_instance_serves_many_slots_and_is_built_once():
    cfg = {
        "tools": {"f": {"tool": "fitz", "config": {}},
                  "t": {"tool": "fitz_tables", "config": {}}},
        "capabilities": {"text_extraction": "f", "table_detection": "t"},
    }
    p = build_pipeline_config(cfg)
    assert len(p.instances) == 2
    assert {i.key for i in p.instances} == {"f", "t"}


def test_tool_config_is_validated_and_applied():
    cfg = {
        "tools": {"fitz": {"tool": "fitz", "config": {"span_detail": True}}},
        "capabilities": {"text_extraction": "fitz"},
    }
    inst = build_pipeline_config(cfg).for_capability(Capability.TEXT_EXTRACTION)
    assert inst.tool.config.span_detail is True


def test_text_extraction_slot_is_required():
    with pytest.raises(ValueError, match="text_extraction"):
        build_pipeline_config({"tools": {}, "capabilities": {}})


def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError, match="unknown tool"):
        build_pipeline_config({"tools": {"x": {"tool": "nope"}},
                               "capabilities": {"text_extraction": "x"}})


def test_unknown_capability_is_rejected():
    with pytest.raises(ValueError, match="unknown capability"):
        build_pipeline_config({"tools": {"f": {"tool": "fitz"}},
                               "capabilities": {"text_extraction": "f",
                                                "teleportation": "f"}})


def test_staging_capability_has_no_tools_yet():
    with pytest.raises(ValueError, match="staging capability"):
        build_pipeline_config({"tools": {"f": {"tool": "fitz"}},
                               "capabilities": {"text_extraction": "f",
                                                "layout_analysis": "f"}})


def test_capability_not_provided_by_tool_is_rejected():
    with pytest.raises(ValueError, match="does not provide"):
        build_pipeline_config({
            "tools": {"f": {"tool": "fitz"}},
            "capabilities": {"text_extraction": "f", "table_detection": "f"},
        })


def test_dangling_instance_reference_is_rejected():
    with pytest.raises(ValueError, match="unknown instance"):
        build_pipeline_config({"tools": {"f": {"tool": "fitz"}},
                               "capabilities": {"text_extraction": "ghost"}})


def test_thresholds_and_page_flags_defaults():
    p = build_pipeline_config(BASE)
    assert p.eviction_overlap_threshold == 0.5
    assert p.ocr_eviction_threshold == 0.3
    assert p.page_flags.min_chars == 10 and p.page_flags.cid_ratio == 0.3


def test_two_table_tools_are_structurally_unrepresentable():
    # The capabilities map is a dict — there is only ever one table_detection
    # key, so the old "only one table tool" runtime guard has nothing to guard.
    cfg = {"tools": {"a": {"tool": "camelot"}, "b": {"tool": "fitz_tables"},
                     "f": {"tool": "fitz"}},
           "capabilities": {"text_extraction": "f", "table_detection": "b"}}
    p = build_pipeline_config(cfg)
    assert p.for_capability(Capability.TABLE_DETECTION).key == "b"
    # The unreferenced instance "a" is never built.
    assert {i.key for i in p.instances} == {"b", "f"}
