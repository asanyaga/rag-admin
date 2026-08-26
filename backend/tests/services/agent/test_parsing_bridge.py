import pytest
from app.services.agent import parsing_bridge as pb


def test_parser_provider_maps_known_parsers():
    assert pb.parser_provider("llamaparse") == "llama_cloud"
    assert pb.parser_provider("landing_ai") == "landing_ai"
    assert pb.parser_provider("simple") is None
    assert pb.parser_provider("docling") is None


def test_parse_outcome_as_state_exposes_output_keys():
    outcome = pb.ParseOutcome(
        parse_run_id="r1", parsed_document_id="d1",
        page_count=3, text_len=42, failed_page_count=0, block_count=7,
    )
    assert outcome.as_state() == {
        "parse_run_id": "r1", "parsed_document_id": "d1",
        "page_count": 3, "text_len": 42,
        "failed_page_count": 0, "block_count": 7,
    }


@pytest.mark.asyncio
async def test_run_parse_shapes_outcome_from_service(monkeypatch):
    class FakeRun:
        id = "run-123"
        failed_pages = ["p2"]

    class FakeDoc:
        page_count = 4
        full_text = "hello world"
        blocks = [1, 2, 3]

    class FakeService:
        async def parse_and_persist(self, **kwargs):
            return FakeRun(), FakeDoc()

    class FakeParsedDocRow:
        id = "pdoc-9"

    async def fake_get_by_run(self, run_id):
        return FakeParsedDocRow()

    monkeypatch.setattr(
        "app.repositories.parsed_document_repository.ParsedDocumentRepository.get_by_run",
        fake_get_by_run,
    )

    outcome = await pb.run_parse(
        session=object(), service=FakeService(), source=object(),
        file_path="/tmp/x.pdf", representation_kind="extract_rich",
        config={"parser": "simple"}, project_id="proj-1",
    )
    assert outcome.parse_run_id == "run-123"
    assert outcome.parsed_document_id == "pdoc-9"
    assert outcome.page_count == 4
    assert outcome.text_len == len("hello world")
    assert outcome.failed_page_count == 1
    assert outcome.block_count == 3
