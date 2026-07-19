"""Parse requests are validated at the API boundary.

An unknown parser or a malformed parser config previously surfaced only from
inside the background task, as "Internal error during parsing" on a run the
caller had already been told was accepted. These must 422 on the request.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers.documents import _validate_parse_request


# ── Parser identity ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "parser", ["simple", "llamaparse", "landing_ai", "docling", "custom_pipeline"])
def test_known_parsers_accepted(parser):
    _validate_parse_request(parser, None)


def test_unknown_parser_is_rejected():
    with pytest.raises(HTTPException) as exc:
        _validate_parse_request("magic_parser", None)
    assert exc.value.status_code == 422
    assert "magic_parser" in str(exc.value.detail)


def test_rejection_lists_the_valid_parsers():
    with pytest.raises(HTTPException) as exc:
        _validate_parse_request("nope", None)
    assert "docling" in str(exc.value.detail)


# ── Parser-specific config ────────────────────────────────────────────────────

def test_valid_docling_config_accepted():
    _validate_parse_request("docling", {
        "do_ocr": True,
        "ocr_options": {"kind": "tesseract", "lang": ["eng"]},
        "table_structure_options": {"mode": "fast"},
    })


def test_malformed_docling_config_is_rejected():
    with pytest.raises(HTTPException) as exc:
        _validate_parse_request("docling", {"ocr_options": {"kind": "not-an-engine"}})
    assert exc.value.status_code == 422


def test_docling_config_contradiction_is_rejected():
    with pytest.raises(HTTPException) as exc:
        _validate_parse_request("docling", {
            "do_ocr": False,
            "ocr_options": {"kind": "tesseract"},
        })
    assert exc.value.status_code == 422
    assert "do_ocr" in str(exc.value.detail)


def test_typo_in_docling_config_is_rejected():
    with pytest.raises(HTTPException) as exc:
        _validate_parse_request("docling", {"do_ocrr": True})
    assert exc.value.status_code == 422


def test_routing_keys_are_not_treated_as_docling_options():
    """The router threads its own keys through the same dict; they must not be
    mistaken for parser options."""
    _validate_parse_request("docling", {
        "parser": "docling",
        "representation_kind": "extract_rich",
        "do_ocr": False,
    })


def test_parsers_without_a_config_model_are_not_validated():
    """Only docling has a config model so far; the rest must pass through
    untouched rather than being rejected for having unknown keys."""
    _validate_parse_request("llamaparse", {"tier": "premium", "anything": 1})


def test_empty_config_is_valid_for_docling():
    _validate_parse_request("docling", {})
    _validate_parse_request("docling", None)
