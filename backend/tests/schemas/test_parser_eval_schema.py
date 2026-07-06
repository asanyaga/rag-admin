import pytest
from uuid import uuid4
from pydantic import ValidationError
from app.schemas.parser_eval import CaseCreate, RunCreate, VariantInput


def test_case_create_requires_dimension_and_expected():
    c = CaseCreate(source_document_id=uuid4(), dimension="text", expected={"pages": ["hi"]})
    assert c.dimension == "text"


def test_text_case_requires_pages_list():
    with pytest.raises(ValidationError):
        CaseCreate(source_document_id=uuid4(), dimension="text", expected={"wrong": 1})


def test_run_create_rejects_unknown_adapter():
    with pytest.raises(ValidationError):
        RunCreate(variants=[VariantInput(adapter="not_a_parser", config={})],
                  eval_case_ids=[uuid4()])


def test_run_create_accepts_known_adapter():
    r = RunCreate(variants=[VariantInput(adapter="docling", config={"x": 1})],
                  eval_case_ids=[uuid4()])
    assert r.variants[0].adapter == "docling"
