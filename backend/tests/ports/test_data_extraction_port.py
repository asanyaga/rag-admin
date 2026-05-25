"""Tests for the DataExtractor port contract."""
from dataclasses import FrozenInstanceError
from uuid import UUID
import pytest
from app.ports.data_extraction import DataExtractor, ExtractionOutput, FieldCitation


class TestFieldCitation:
    def test_frozen(self):
        c = FieldCitation(field_path="total", page_index=1, block_ids=None, text_spans=None)
        with pytest.raises((FrozenInstanceError, TypeError)):
            c.page_index = 2  # type: ignore

    def test_page_index_can_be_none(self):
        c = FieldCitation(field_path="total", page_index=None, block_ids=None, text_spans=None)
        assert c.page_index is None

    def test_block_ids_list(self):
        c = FieldCitation(field_path="f", page_index=0, block_ids=["abc", "def"], text_spans=None)
        assert c.block_ids == ["abc", "def"]


class TestExtractionOutput:
    def test_frozen(self):
        run_id = UUID("00000000-0000-0000-0000-000000000001")
        o = ExtractionOutput(
            structured_data={}, source_parse_run_id=run_id,
            citations=None, provider_response_raw=None, extraction_metadata=None,
        )
        with pytest.raises((FrozenInstanceError, TypeError)):
            o.structured_data = {"x": 1}  # type: ignore

    def test_source_parse_run_id_required(self):
        with pytest.raises(TypeError):
            ExtractionOutput(structured_data={})  # type: ignore


class TestDataExtractorPort:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            DataExtractor()  # type: ignore

    def test_concrete_must_implement_extract_and_extractor_type(self):
        class Stub(DataExtractor):
            @property
            def extractor_type(self):
                return "stub"
            async def extract(self, parsed_document, schema, config=None):
                return None
        stub = Stub()
        assert stub.extractor_type == "stub"
        assert stub.display_name == "stub"
