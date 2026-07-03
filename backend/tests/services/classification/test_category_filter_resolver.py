from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.services.classification.category_filter_resolver import resolve_category_filter_stages
from app.services.exceptions import NotFoundError


@dataclass
class _Region:
    label: str
    page_start: int
    page_end: int
    block_ids: list


@dataclass
class _Run:
    status: str
    parse_run_id: object


class _Repo:
    def __init__(self, run, regions):
        self._run = run
        self._regions = regions

    async def get(self, run_id):
        return self._run

    async def get_regions(self, run_id):
        return self._regions


def _stage(run_id, categories, granularity):
    return [{"stage": "category_filter", "config": {
        "classificationRunId": str(run_id), "categories": categories, "granularity": granularity}}]


@pytest.mark.asyncio
async def test_no_category_filter_stage_returns_none_summary():
    pre = [{"stage": "block_filter", "config": {"drop": ["header"]}}]
    resolved, summary = await resolve_category_filter_stages(pre, uuid4(), _Repo(None, []))
    assert resolved == pre
    assert summary is None


@pytest.mark.asyncio
async def test_page_mode_resolves_page_union():
    parse_id = uuid4()
    run = _Run(status="completed", parse_run_id=parse_id)
    regions = [_Region("fin", 1, 2, ["b"]), _Region("other", 5, 5, ["z"])]
    resolved, summary = await resolve_category_filter_stages(
        _stage(uuid4(), ["fin"], "page"), parse_id, _Repo(run, regions))
    cfg = resolved[0]["config"]
    assert cfg["keepPages"] == [1, 2]
    assert cfg["keepBlockIds"] == []
    assert summary["keptPages"] == 2 and summary["keptBlocks"] == 0


@pytest.mark.asyncio
async def test_block_mode_resolves_block_ids_with_page_fallback():
    parse_id = uuid4()
    run = _Run(status="completed", parse_run_id=parse_id)
    regions = [_Region("fin", 1, 1, ["b", "c"]), _Region("fin", 4, 5, [])]  # 2nd has no blocks
    resolved, _ = await resolve_category_filter_stages(
        _stage(uuid4(), ["fin"], "block"), parse_id, _Repo(run, regions))
    cfg = resolved[0]["config"]
    assert cfg["keepBlockIds"] == ["b", "c"]
    assert cfg["keepPages"] == [4, 5]


@pytest.mark.asyncio
async def test_missing_run_raises_not_found():
    with pytest.raises(NotFoundError):
        await resolve_category_filter_stages(
            _stage(uuid4(), ["fin"], "page"), uuid4(), _Repo(None, []))


@pytest.mark.asyncio
async def test_not_completed_raises_value_error():
    run = _Run(status="running", parse_run_id=uuid4())
    with pytest.raises(ValueError):
        await resolve_category_filter_stages(
            _stage(uuid4(), ["fin"], "page"), run.parse_run_id, _Repo(run, []))


@pytest.mark.asyncio
async def test_parse_run_mismatch_raises_value_error():
    run = _Run(status="completed", parse_run_id=uuid4())
    with pytest.raises(ValueError):
        await resolve_category_filter_stages(
            _stage(uuid4(), ["fin"], "page"), uuid4(), _Repo(run, []))


@pytest.mark.asyncio
async def test_empty_match_raises_value_error():
    parse_id = uuid4()
    run = _Run(status="completed", parse_run_id=parse_id)
    regions = [_Region("other", 1, 1, ["z"])]
    with pytest.raises(ValueError):
        await resolve_category_filter_stages(
            _stage(uuid4(), ["fin"], "page"), parse_id, _Repo(run, regions))
