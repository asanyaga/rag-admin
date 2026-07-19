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
