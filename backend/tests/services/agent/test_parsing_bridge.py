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
    from uuid import UUID

    # The real ORM ParsedDocument keys on parse_run_id (its primary key); it has
    # NO `id` column. Use the real model so the fake can't drift back into
    # claiming an `id` attribute the row does not have.
    from app.models.parsed_document import ParsedDocument as ParsedDocumentORM

    PDOC_PK = UUID("99999999-9999-9999-9999-999999999999")

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

    parsed_row = ParsedDocumentORM(
        parse_run_id=PDOC_PK,
        source_document_id=UUID("88888888-8888-8888-8888-888888888888"),
        page_count=4, block_count=3, content={},
    )

    async def fake_get_by_run(self, run_id):
        return parsed_row

    monkeypatch.setattr(
        "app.repositories.parsed_document_repository.ParsedDocumentRepository.get_by_run",
        fake_get_by_run,
    )

    outcome = await pb.run_parse(
        session=object(), service=FakeService(), source=object(),
        file_path="/tmp/x.pdf", representation_kind="extract_rich",
        config={"parser": "simple"}, project_id="33333333-3333-3333-3333-333333333333",
    )
    assert outcome.parse_run_id == "run-123"
    # The parsed-document handle is its parse_run_id under the current 1:1 schema.
    assert outcome.parsed_document_id == str(PDOC_PK)
    assert outcome.page_count == 4
    assert outcome.text_len == len("hello world")
    assert outcome.failed_page_count == 1
    assert outcome.block_count == 3
