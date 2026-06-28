# backend/tests/services/test_result_transform_service.py
import pytest
from uuid import uuid4
from app.services.result_transform_service import ResultTransformService, _extract_rows
from app.services.exceptions import NotFoundError


class _Result:
    def __init__(self, rows, rid=None):
        self.id = rid or uuid4()
        self.structured_data = {"records": rows}
        self.document_id = uuid4()
        self.extraction_schema_id = uuid4()
        self.schema_definition_snapshot = {"type": "object"}
        self.extraction_metadata = None


class _Repo:
    def __init__(self, results):
        self._results = {r.id: r for r in results}
        self.created = None
        self.updated = None

    async def get_by_id(self, rid):
        return self._results.get(rid)

    async def create(self, **kwargs):
        self.created = type("R", (), {"id": uuid4(), **kwargs})()
        return self.created

    async def update_result(self, result_id, structured_data, extraction_metadata=None, **_):
        self.updated = {"id": result_id, "structured_data": structured_data,
                        "extraction_metadata": extraction_metadata}
        obj = type("R", (), {"id": result_id, "structured_data": structured_data,
                             "extraction_metadata": extraction_metadata})()
        return obj


CFG = {"groupBy": ["productFamily"], "spine": {"whereFieldsPresent": ["sku"]}}
ROWS = [
    {"sku": None, "productFamily": "GP-40", "modelName": "GP-40", "widthMm": 470, "sourcePage": "Page 6"},
    {"sku": "1303050", "productFamily": "GP-40", "modelName": "GP-40 230/50/1", "listPrice": 1908, "sourcePage": "Page 7"},
]


@pytest.mark.asyncio
async def test_preview_does_not_persist():
    src = _Result(ROWS)
    repo = _Repo([src])
    svc = ResultTransformService(result_repo=repo)
    out = await svc.preview([src.id], "merge_records", CFG)
    assert len(out["rows"]) == 1
    assert out["rows"][0]["widthMm"] == 470
    assert repo.created is None
    assert repo.updated is None


@pytest.mark.asyncio
async def test_apply_persists_with_lineage():
    src = _Result(ROWS)
    repo = _Repo([src])
    svc = ResultTransformService(result_repo=repo)
    await svc.apply([src.id], "merge_records", CFG, user_id=uuid4())
    assert repo.created is not None
    lineage = repo.updated["extraction_metadata"]["lineage"]
    assert lineage["transform"]["type"] == "merge_records"
    assert str(src.id) in [str(x) for x in lineage["sourceResultIds"]]


@pytest.mark.asyncio
async def test_missing_source_raises():
    svc = ResultTransformService(result_repo=_Repo([]))
    with pytest.raises(NotFoundError):
        await svc.preview([uuid4()], "merge_records", CFG)


# --- _extract_rows unit tests -----------------------------------------------

def test_extract_rows_uses_records_key():
    rows = [{"a": 1}]
    assert _extract_rows({"records": rows}, {}) == rows


def test_extract_rows_uses_schema_array_field():
    rows = [{"modelName": "GP-40"}]
    schema = {"properties": {"items": {"type": "array", "items": {}}}}
    result = _extract_rows({"items": rows}, schema)
    assert result == rows


def test_extract_rows_prefers_records_over_schema_array():
    records = [{"x": 1}]
    items = [{"y": 2}]
    schema = {"properties": {"items": {"type": "array", "items": {}}}}
    assert _extract_rows({"records": records, "items": items}, schema) == records


def test_extract_rows_fallback_to_first_list_of_dicts():
    rows = [{"z": 3}]
    assert _extract_rows({"data": rows}, {}) == rows


def test_extract_rows_returns_empty_for_empty_data():
    assert _extract_rows(None, {}) == []
    assert _extract_rows({}, {}) == []
