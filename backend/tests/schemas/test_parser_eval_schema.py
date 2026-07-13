import pytest
from uuid import uuid4
from pydantic import ValidationError
from app.schemas.parser_eval import CaseCreate, CaseExpectedUpdate, RunCreate, VariantInput


def test_case_expected_update_accepts_tables():
    m = CaseExpectedUpdate(tables=[{"page": 1, "html": "<table><tr><td>a</td></tr></table>"}])
    assert m.tables[0]["html"].startswith("<table")


def test_case_expected_update_rejects_empty():
    with pytest.raises(ValidationError):
        CaseExpectedUpdate(tables=[])


def test_case_expected_update_rejects_missing_html():
    with pytest.raises(ValidationError):
        CaseExpectedUpdate(tables=[{"page": 1}])


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
    r = RunCreate(variants=[VariantInput(adapter="custom_pipeline", config={"x": 1})],
                  eval_case_ids=[uuid4()])
    assert r.variants[0].adapter == "custom_pipeline"


def test_table_case_accepts_tables_html():
    c = CaseCreate.model_validate(
        {"sourceDocumentId": "11111111-1111-1111-1111-111111111111",
         "dimension": "table",
         "expected": {"tables": [{"page": 1, "html": "<table><tr><td>a</td></tr></table>"}]}})
    assert c.dimension == "table"
    assert c.expected["tables"][0]["html"].startswith("<table")


def test_table_case_rejects_missing_html():
    with pytest.raises(ValidationError):
        CaseCreate.model_validate(
            {"sourceDocumentId": "11111111-1111-1111-1111-111111111111",
             "dimension": "table",
             "expected": {"tables": [{"page": 1}]}})


def test_table_case_rejects_non_list_tables():
    with pytest.raises(ValidationError):
        CaseCreate.model_validate(
            {"sourceDocumentId": "11111111-1111-1111-1111-111111111111",
             "dimension": "table",
             "expected": {"tables": "nope"}})
