"""Tests for extraction result Pydantic schemas — provenance fields."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.schemas.extraction_result import (
    RunExtractionRequest,
    ExtractionResultResponse,
)
from app.models.extraction_result import ExtractionResultStatus


class TestRunExtractionRequest:
    def test_accepts_parse_run_id(self):
        run_id = uuid4()
        req = RunExtractionRequest(
            parseRunId=str(run_id),
            extractionSchemaId=str(uuid4()),
            extractionMethod="ollama",
        )
        assert req.parse_run_id == run_id

    def test_rejects_document_id_field(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            RunExtractionRequest(
                documentId=str(uuid4()),    # old field — must not be accepted
                extractionSchemaId=str(uuid4()),
                extractionMethod="ollama",
            )
        assert any(e["loc"] == ("parseRunId",) for e in exc_info.value.errors())


class TestExtractionResultResponse:
    def _make_mock_orm(self, **kwargs):
        from unittest.mock import MagicMock
        obj = MagicMock()
        obj.id = kwargs.get("id", uuid4())
        obj.document_id = kwargs.get("document_id", uuid4())
        obj.source_parse_run_id = kwargs.get("source_parse_run_id", uuid4())
        obj.extraction_schema_id = kwargs.get("extraction_schema_id", uuid4())
        obj.schema_definition_snapshot = kwargs.get("schema_definition_snapshot", {})
        obj.extraction_method = kwargs.get("extraction_method", "ollama")
        obj.config = kwargs.get("config", None)
        obj.structured_data = kwargs.get("structured_data", None)
        obj.citations = kwargs.get("citations", None)
        obj.provider_response_raw = kwargs.get("provider_response_raw", None)
        obj.extraction_metadata = kwargs.get("extraction_metadata", None)
        obj.status = kwargs.get("status", ExtractionResultStatus.pending)
        obj.status_message = kwargs.get("status_message", None)
        obj.started_at = kwargs.get("started_at", None)
        obj.created_by = kwargs.get("created_by", uuid4())
        obj.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        obj.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
        return obj

    def test_source_parse_run_id_in_response(self):
        run_id = uuid4()
        obj = self._make_mock_orm(source_parse_run_id=run_id)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.source_parse_run_id == run_id

    def test_citations_in_response(self):
        citations = [{"field_path": "total", "page_index": 1, "block_ids": None, "text_spans": None}]
        obj = self._make_mock_orm(citations=citations)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.citations == citations

    def test_provider_response_raw_in_response(self):
        raw = {"data": {"x": 1}}
        obj = self._make_mock_orm(provider_response_raw=raw)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.provider_response_raw == raw

    def test_null_provenance_fields_accepted(self):
        obj = self._make_mock_orm(citations=None, provider_response_raw=None, source_parse_run_id=None)
        resp = ExtractionResultResponse.from_orm_model(obj)
        assert resp.citations is None
        assert resp.provider_response_raw is None


class TestRunExtractionRequestLLMFields:
    def test_accepts_llm_config_camelcase(self):
        from app.schemas.extraction_result import RunExtractionRequest
        body = RunExtractionRequest.model_validate({
            "parseRunId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "extractionSchemaId": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            "extractionMethod": "llm",
            "llmConfig": {
                "provider": "ollama_local",
                "model": "llama3.2:8b",
                "temperature": 0.0,
            },
            "userPromptTemplate": "Extract: {schema_json}",
        })
        assert body.llm_config is not None
        assert body.llm_config.provider == "ollama_local"
        assert body.user_prompt_template == "Extract: {schema_json}"

    def test_llm_config_and_template_are_optional(self):
        from app.schemas.extraction_result import RunExtractionRequest
        body = RunExtractionRequest.model_validate({
            "parseRunId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "extractionSchemaId": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            "extractionMethod": "llamaextract",
        })
        assert body.llm_config is None
        assert body.user_prompt_template is None
