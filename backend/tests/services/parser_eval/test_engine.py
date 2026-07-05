import pytest
from types import SimpleNamespace
from app.cdm.models import ParsedDocument, Page
from app.models.parser_eval import ParserEvalDimension, ParserEvalRunStatus
from app.services.parser_eval import engine as engine_mod


class _RepoSpy:
    def __init__(self): self.results = []; self.status = None
    async def upsert_result(self, run_id, case_id, parser, dimension, score, details, cost, latency_ms):
        self.results.append((parser, dimension, score))
    async def set_run_status(self, run_id, status, error_message=None):
        self.status = status


def _case():
    target = SimpleNamespace(dimension=ParserEvalDimension.text, expected={"pages": ["hi"]})
    return SimpleNamespace(id="c1", targets=[target])


@pytest.mark.asyncio
async def test_run_evaluation_scores_each_parser(monkeypatch):
    async def fake_capture(*args, **kwargs):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                             page_count=1, pages=[Page(index=0, start_char=0, end_char=2)],
                             blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 10
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    repo = _RepoSpy()
    await engine_mod.run_evaluation(
        repo, parsing_service=None, storage=None, run_id="run1",
        cases=[_case()], parsers=["docling", "simple"], project_id="p1",
        _case_source=lambda c: ("src", "uri", "a.pdf", "application/pdf"))
    assert repo.status == ParserEvalRunStatus.completed
    assert {r[0] for r in repo.results} == {"docling", "simple"}
    assert all(r[2] == 1.0 for r in repo.results)   # "hi" == "hi"


@pytest.mark.asyncio
async def test_capture_failure_records_zero(monkeypatch):
    async def fake_capture(*args, **kwargs):
        return None, {}, None
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    repo = _RepoSpy()
    await engine_mod.run_evaluation(
        repo, parsing_service=None, storage=None, run_id="run1",
        cases=[_case()], parsers=["docling"], project_id="p1",
        _case_source=lambda c: ("src", "uri", "a.pdf", "application/pdf"))
    assert repo.results == [("docling", ParserEvalDimension.text, 0.0)]
    assert repo.status == ParserEvalRunStatus.completed
