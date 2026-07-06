import pytest
from types import SimpleNamespace
from app.cdm.models import ParsedDocument, Page
from app.models.parser_eval import ParserEvalDimension, ParserEvalRunStatus
from app.services.parser_eval import engine as engine_mod
from app.services.parser_eval.engine import run_evaluation


class _Repo:
    def __init__(self):
        self.status = None
        self.results = []

    async def set_run_status(self, run_id, status, error_message=None):
        self.status = status

    async def insert_result(self, run_id, eval_case_id, adapter, config, variant_key,
                            metrics, primary_metric, details, cost, latency_ms):
        self.results.append((adapter, variant_key, metrics, details))


def _case():
    return SimpleNamespace(id="c1", source_document_id="s1",
                           dimension=ParserEvalDimension.text, expected={"pages": ["hi"]})


@pytest.mark.asyncio
async def test_two_configs_of_one_adapter_yield_two_results(monkeypatch):
    async def fake_capture(*a, **k):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r", page_count=1,
                             pages=[Page(index=0, start_char=0, end_char=2)], blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 5
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    repo = _Repo()
    variants = [{"adapter": "custom_pipeline", "config": {"tool": "pdfplumber"}},
                {"adapter": "custom_pipeline", "config": {"tool": "fitz"}}]
    await run_evaluation(repo, object(), object(), run_id="run", cases=[_case()],
                         variants=variants, project_id="p",
                         _case_source=lambda c: ("s1", "uri", "f.pdf", "application/pdf"))
    assert repo.status == ParserEvalRunStatus.completed
    assert len(repo.results) == 2
    assert repo.results[0][1] != repo.results[1][1]  # distinct variant_key
    assert all(r[2]["similarity"] == 1.0 for r in repo.results)  # "hi" == "hi"


@pytest.mark.asyncio
async def test_capture_failure_writes_zero_primary(monkeypatch):
    async def fake_capture(*a, **k):
        return None, {}, None
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    repo = _Repo()
    await run_evaluation(repo, object(), object(), run_id="run", cases=[_case()],
                         variants=[{"adapter": "docling", "config": {}}], project_id="p",
                         _case_source=lambda c: ("s1", "uri", "f.pdf", "application/pdf"))
    assert repo.results[0][2] == {"similarity": 0.0}
    assert repo.results[0][3] == {"capture_failed": True}
    assert repo.status == ParserEvalRunStatus.completed
