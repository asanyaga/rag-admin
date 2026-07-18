"""Tests for DoclingConfig — the validated config surface for ParserKind.DOCLING.

Defaults deliberately track docling's own (verified against docling 2.105.0), so
an empty config produces the same behaviour as bare `DocumentConverter()`.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.parsing.docling_config import DoclingConfig


# ── Defaults track docling's own ──────────────────────────────────────────────

def test_empty_config_matches_docling_defaults():
    cfg = DoclingConfig.model_validate({})
    assert cfg.pipeline == "standard"
    assert cfg.backend == "docling_parse_v4"
    assert cfg.do_ocr is True
    assert cfg.do_table_structure is True
    assert cfg.do_code_enrichment is False
    assert cfg.do_formula_enrichment is False
    assert cfg.force_backend_text is False
    # docling's default engine is the auto-selector, not easyocr
    assert cfg.ocr_options.kind == "auto"
    assert cfg.table_structure_options.mode == "accurate"
    assert cfg.table_structure_options.do_cell_matching is True
    assert cfg.layout_options.model == "docling_layout_heron"


def test_page_batch_size_is_ours_not_doclings():
    assert DoclingConfig.model_validate({}).page_batch_size == 20


# ── Round-tripping ────────────────────────────────────────────────────────────

def test_full_standard_config_round_trips():
    raw = {
        "pipeline": "standard",
        "backend": "pypdfium2",
        "do_ocr": True,
        "do_table_structure": True,
        "force_backend_text": True,
        "images_scale": 2.0,
        "layout_options": {"model": "docling_layout_egret_large",
                           "create_orphan_clusters": False},
        "ocr_options": {"kind": "tesseract", "lang": ["eng"],
                        "force_full_page_ocr": True, "psm": 6},
        "table_structure_options": {"mode": "fast", "do_cell_matching": False},
        "page_batch_size": 10,
    }
    cfg = DoclingConfig.model_validate(raw)
    # exclude_unset, not exclude_defaults: a value the user set explicitly must
    # survive the round trip even when it equals the default.
    assert cfg.model_dump(exclude_unset=True, mode="json") == raw


def test_vlm_config_round_trips():
    raw = {"pipeline": "vlm", "vlm_model": "smoldocling"}
    cfg = DoclingConfig.model_validate(raw)
    assert cfg.pipeline == "vlm"
    assert cfg.vlm_model == "smoldocling"


# ── OCR engine union ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", ["auto", "easyocr", "tesseract", "tesserocr", "rapidocr"])
def test_supported_ocr_engines_accepted(kind):
    cfg = DoclingConfig.model_validate({"ocr_options": {"kind": kind}})
    assert cfg.ocr_options.kind == kind


@pytest.mark.parametrize("kind", ["ocrmac", "kserve_v2_ocr", "nemotron-ocr"])
def test_unsupported_ocr_engines_rejected(kind):
    """Engines needing platform support we don't have are excluded from the
    union rather than exposed and failing mid-parse."""
    with pytest.raises(ValidationError):
        DoclingConfig.model_validate({"ocr_options": {"kind": kind}})


def test_unknown_ocr_engine_rejected():
    with pytest.raises(ValidationError):
        DoclingConfig.model_validate({"ocr_options": {"kind": "not-an-engine"}})


def test_engine_specific_field_on_wrong_engine_rejected():
    """psm belongs to tesseract, not easyocr — extra fields are not silently kept."""
    with pytest.raises(ValidationError):
        DoclingConfig.model_validate({"ocr_options": {"kind": "easyocr", "psm": 6}})


# ── Stage options require their stage ─────────────────────────────────────────

def test_ocr_options_with_ocr_disabled_rejected():
    with pytest.raises(ValidationError, match="do_ocr"):
        DoclingConfig.model_validate({
            "do_ocr": False,
            "ocr_options": {"kind": "tesseract", "lang": ["eng"]},
        })


def test_table_options_with_table_structure_disabled_rejected():
    with pytest.raises(ValidationError, match="do_table_structure"):
        DoclingConfig.model_validate({
            "do_table_structure": False,
            "table_structure_options": {"mode": "fast"},
        })


def test_disabling_a_stage_without_configuring_it_is_fine():
    cfg = DoclingConfig.model_validate({"do_ocr": False, "do_table_structure": False})
    assert cfg.do_ocr is False
    assert cfg.do_table_structure is False


def test_standard_only_fields_rejected_on_vlm_pipeline():
    with pytest.raises(ValidationError, match="standard"):
        DoclingConfig.model_validate({"pipeline": "vlm", "do_ocr": False})


# ── Other validation ──────────────────────────────────────────────────────────

def test_unknown_backend_rejected():
    with pytest.raises(ValidationError):
        DoclingConfig.model_validate({"backend": "pdfminer"})


def test_unknown_layout_model_rejected():
    with pytest.raises(ValidationError):
        DoclingConfig.model_validate({"layout_options": {"model": "layoutlmv3"}})


def test_unknown_top_level_key_rejected():
    """A typo'd key must 422 at the boundary, not be silently dropped."""
    with pytest.raises(ValidationError):
        DoclingConfig.model_validate({"do_ocrr": True})


@pytest.mark.parametrize("bad", [0, -1, 1001])
def test_page_batch_size_bounds(bad):
    with pytest.raises(ValidationError):
        DoclingConfig.model_validate({"page_batch_size": bad})


# ── Bridge into docling's own option objects ──────────────────────────────────

def test_to_pipeline_options_builds_standard_options():
    from docling.datamodel.pipeline_options import TableFormerMode

    cfg = DoclingConfig.model_validate({
        "ocr_options": {"kind": "tesseract", "lang": ["eng"], "force_full_page_ocr": True},
        "table_structure_options": {"mode": "fast"},
        "layout_options": {"model": "docling_layout_egret_large"},
    })
    opts = cfg.to_pipeline_options()

    assert opts.do_ocr is True
    assert opts.ocr_options.kind == "tesseract"
    assert opts.ocr_options.lang == ["eng"]
    assert opts.ocr_options.force_full_page_ocr is True
    assert opts.table_structure_options.mode is TableFormerMode.FAST
    assert opts.layout_options.model_spec.name == "docling_layout_egret_large"


def test_to_pipeline_options_omits_unset_engine_fields():
    """Fields we don't set must fall through to docling's defaults rather than
    being pinned to ours."""
    cfg = DoclingConfig.model_validate({"ocr_options": {"kind": "easyocr"}})
    opts = cfg.to_pipeline_options()
    assert opts.ocr_options.lang == ["fr", "de", "es", "en"]  # docling's default
    assert opts.ocr_options.confidence_threshold == 0.5


def test_disabled_stages_reach_docling():
    cfg = DoclingConfig.model_validate({"do_ocr": False, "do_table_structure": False})
    opts = cfg.to_pipeline_options()
    assert opts.do_ocr is False
    assert opts.do_table_structure is False
