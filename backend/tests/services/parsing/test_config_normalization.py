"""Configs are resolved before hashing, so a ParseRun records what actually ran.

Before this, selecting docling in the UI and changing nothing stored
``{"parser": "docling"}`` — which says nothing about the layout model, OCR
engine, or table mode used, and hashes identically to every other defaulted run.
"""
from __future__ import annotations

import pytest

from app.services.parsing.config_models import normalize_parse_config
from app.services.parsing.parsing_service import _compute_config_hash


def test_a_defaulted_docling_config_records_what_ran():
    resolved = normalize_parse_config({"parser": "docling"})

    assert resolved["parser"] == "docling"          # routing key survives
    assert resolved["pipeline"] == "standard"
    assert resolved["backend"] == "docling_parse_v4"
    assert resolved["do_ocr"] is True
    assert resolved["layout_options"]["model"] == "docling_layout_heron"
    assert resolved["ocr_options"]["kind"] == "auto"
    assert resolved["table_structure_options"]["mode"] == "accurate"


def test_explicit_values_are_preserved():
    resolved = normalize_parse_config({
        "parser": "docling",
        "do_table_structure": False,
        "ocr_options": {"kind": "tesseract", "lang": ["eng"]},
    })
    assert resolved["do_table_structure"] is False
    assert resolved["ocr_options"]["kind"] == "tesseract"
    assert resolved["ocr_options"]["lang"] == ["eng"]


def test_equivalent_configs_collapse_to_one_hash():
    """Reuse should work across configs that differ only in what was implicit."""
    implicit = normalize_parse_config({"parser": "docling"})
    explicit = normalize_parse_config({
        "parser": "docling", "do_ocr": True, "table_structure_options": {"mode": "accurate"},
    })
    assert _compute_config_hash(implicit) == _compute_config_hash(explicit)


def test_genuinely_different_configs_still_differ():
    fast = normalize_parse_config({
        "parser": "docling", "table_structure_options": {"mode": "fast"}})
    accurate = normalize_parse_config({"parser": "docling"})
    assert _compute_config_hash(fast) != _compute_config_hash(accurate)


def test_layout_model_choice_changes_the_hash():
    """The eval product exists to compare these; they must not collide."""
    heron = normalize_parse_config({"parser": "docling"})
    egret = normalize_parse_config({
        "parser": "docling", "layout_options": {"model": "docling_layout_egret_large"}})
    assert _compute_config_hash(heron) != _compute_config_hash(egret)


def test_the_stored_config_hashes_to_its_own_hash():
    """Whatever is persisted must be re-hashable to the same value, or the
    stored config and config_hash are describing different things."""
    resolved = normalize_parse_config({"parser": "docling", "do_ocr": False})
    assert _compute_config_hash(resolved) == _compute_config_hash(
        normalize_parse_config(resolved))


@pytest.mark.parametrize("config", [
    {"parser": "llamaparse", "tier": "agentic"},
    {"parser": "simple"},
    {"parser": "custom_pipeline", "tools": {}, "capabilities": {}},
    {"parser": "not_a_parser"},
    {},
])
def test_parsers_without_a_config_model_pass_through_untouched(config):
    assert normalize_parse_config(config) == config


def test_an_invalid_config_is_left_alone_for_the_runner_to_report():
    """Normalization must not swallow a bad config — the runner raises a real
    DoclingRunError with a usable message."""
    bad = {"parser": "docling", "ocr_options": {"kind": "not-an-engine"}}
    assert normalize_parse_config(bad) == bad


def test_normalization_does_not_mutate_its_input():
    original = {"parser": "docling", "do_ocr": False}
    snapshot = dict(original)
    normalize_parse_config(original)
    assert original == snapshot


# ── Normalized configs must still build docling options ──────────────────────

def test_a_normalized_config_can_still_be_turned_into_docling_options():
    """Normalization writes every field explicitly, including the Optionals we
    leave as None to defer to docling. to_pipeline_options() relied on
    exclude_unset to skip those — once they are explicitly set, `lang: None`
    reached docling's `lang: List[str]` and blew up mid-parse.
    """
    from app.services.parsing.docling_config import DoclingConfig

    resolved = normalize_parse_config({"parser": "docling"})
    cfg = DoclingConfig.from_parse_config(resolved)
    opts = cfg.to_pipeline_options()

    # `auto` defers language detection to docling, so [] is its real default;
    # the point is that this no longer raises on `lang: None`.
    assert opts.ocr_options.lang == []
    assert opts.ocr_options.kind == "auto"


@pytest.mark.parametrize("user_config", [
    {},
    {"do_ocr": False},
    {"ocr_options": {"kind": "easyocr"}},
    {"ocr_options": {"kind": "tesseract", "lang": ["eng"]}},
    {"table_structure_options": {"mode": "fast"}},
    {"layout_options": {"model": "docling_layout_egret_large"}},
    {"do_ocr": False, "do_table_structure": False},
    {"pipeline": "vlm"},
])
def test_every_config_survives_the_full_round_trip(user_config):
    """normalize -> persist -> runner -> docling options. The runner receives
    the normalized config, not the user's, so that is the path that matters."""
    from app.services.parsing.docling_config import DoclingConfig

    dispatched = {**user_config, "parser": "docling"}
    resolved = normalize_parse_config(dispatched)
    DoclingConfig.from_parse_config(resolved).to_pipeline_options()


def test_an_explicit_null_is_treated_as_unspecified():
    """A caller can POST `lang: null` directly; it must mean 'docling decides'
    rather than crashing the parse."""
    from app.services.parsing.docling_config import DoclingConfig

    cfg = DoclingConfig.from_parse_config({
        "parser": "docling", "ocr_options": {"kind": "easyocr", "lang": None}})
    assert cfg.to_pipeline_options().ocr_options.lang


def test_a_disabled_stage_records_no_options_for_it():
    resolved = normalize_parse_config({"parser": "docling", "do_ocr": False})
    assert resolved["do_ocr"] is False
    assert "ocr_options" not in resolved
    assert "table_structure_options" in resolved  # tables still on


def test_a_vlm_run_records_no_standard_pipeline_fields():
    resolved = normalize_parse_config({"parser": "docling", "pipeline": "vlm"})
    assert resolved["pipeline"] == "vlm"
    assert resolved["vlm_model"] == "smoldocling"
    for key in ("do_ocr", "ocr_options", "layout_options", "table_structure_options"):
        assert key not in resolved


def test_normalization_output_always_revalidates():
    """The invariant behind both bugs above: the runner re-parses the stored
    config, so anything normalization emits must be accepted by the model."""
    from app.services.parsing.docling_config import DoclingConfig

    for user_config in [
        {}, {"do_ocr": False}, {"do_table_structure": False},
        {"do_ocr": False, "do_table_structure": False},
        {"pipeline": "vlm"},
        {"ocr_options": {"kind": "rapidocr"}},
    ]:
        resolved = normalize_parse_config({**user_config, "parser": "docling"})
        DoclingConfig.from_parse_config(resolved).to_pipeline_options()
        # and again — normalization must be idempotent
        assert normalize_parse_config(resolved) == resolved
