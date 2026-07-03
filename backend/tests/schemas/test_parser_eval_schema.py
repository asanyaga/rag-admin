import pytest
from uuid import uuid4
from pydantic import ValidationError
from app.schemas.parser_eval import CaseCreate, RunCreate, TargetInput


def test_valid_text_target():
    c = CaseCreate(name="c", doc_type="invoice", source_document_id=uuid4(),
                   targets=[TargetInput(dimension="text", expected={"pages": ["a", "b"]})])
    assert c.targets[0].expected["pages"] == ["a", "b"]


def test_text_target_requires_pages_list():
    with pytest.raises(ValidationError):
        TargetInput(dimension="text", expected={"wrong": 1})


def test_run_create_accepts_valid_parser():
    run = RunCreate(name="run", case_ids=[uuid4()], parsers=["docling"])
    assert run.parsers == ["docling"]


def test_run_create_rejects_unknown_parser():
    with pytest.raises(ValidationError):
        RunCreate(name="run", case_ids=[uuid4()], parsers=["nope"])
