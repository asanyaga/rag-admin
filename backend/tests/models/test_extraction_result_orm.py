"""Tests for ExtractionResult ORM model — new provenance columns."""
import pytest
from app.models.extraction_result import ExtractionResult


class TestExtractionResultColumns:
    def test_has_source_parse_run_id_column(self):
        columns = {c.name for c in ExtractionResult.__table__.columns}
        assert "source_parse_run_id" in columns

    def test_has_citations_column(self):
        columns = {c.name for c in ExtractionResult.__table__.columns}
        assert "citations" in columns

    def test_has_provider_response_raw_column(self):
        columns = {c.name for c in ExtractionResult.__table__.columns}
        assert "provider_response_raw" in columns

    def test_source_parse_run_id_is_nullable(self):
        col = ExtractionResult.__table__.columns["source_parse_run_id"]
        assert col.nullable is True

    def test_citations_is_nullable(self):
        col = ExtractionResult.__table__.columns["citations"]
        assert col.nullable is True

    def test_provider_response_raw_is_nullable(self):
        col = ExtractionResult.__table__.columns["provider_response_raw"]
        assert col.nullable is True
