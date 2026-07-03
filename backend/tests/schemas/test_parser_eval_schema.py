import pytest
from uuid import uuid4
from pydantic import ValidationError
from app.schemas.parser_eval import CaseCreate, TargetInput


def test_valid_text_target():
    c = CaseCreate(name="c", doc_type="invoice", source_document_id=uuid4(),
                   targets=[TargetInput(dimension="text", expected={"pages": ["a", "b"]})])
    assert c.targets[0].expected["pages"] == ["a", "b"]


def test_text_target_requires_pages_list():
    with pytest.raises(ValidationError):
        TargetInput(dimension="text", expected={"wrong": 1})
