import pytest
from pydantic import ValidationError
from app.cdm.classification import ClassifiedRegion, ClassificationRunStatus


def test_classified_region_required_fields():
    region = ClassifiedRegion(
        label="balance_sheet",
        page_start=5,
        page_end=8,
        block_ids=["b-001", "b-002"],
    )
    assert region.label == "balance_sheet"
    assert region.page_start == 5
    assert region.page_end == 8
    assert region.block_ids == ["b-001", "b-002"]
    assert region.confidence is None
    assert region.reasoning is None
    assert region.source == "llm"


def test_classified_region_frozen():
    region = ClassifiedRegion(label="x", page_start=0, page_end=1, block_ids=[])
    with pytest.raises(ValidationError):
        region.label = "y"  # type: ignore


def test_classified_region_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ClassifiedRegion(label="x", page_start=0, page_end=1, block_ids=[], unknown="bad")


def test_classification_run_status_values():
    assert ClassificationRunStatus.PENDING == "pending"
    assert ClassificationRunStatus.RUNNING == "running"
    assert ClassificationRunStatus.COMPLETED == "completed"
    assert ClassificationRunStatus.FAILED == "failed"
