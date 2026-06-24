from uuid import uuid4
from app.adapters.extraction.chunking.merge import merge_outputs
from app.ports.data_extraction import ExtractionOutput, FieldCitation

_RUN = uuid4()
_SCHEMA = {
    "type": "object",
    "properties": {
        "currency": {"type": "string"},
        "products": {"type": "array", "items": {"type": "object",
            "properties": {"sku": {"type": "string"}, "price": {"type": "number"}}}},
    },
}


def _out(data, citations=None):
    return ExtractionOutput(
        structured_data=data, source_parse_run_id=_RUN,
        citations=citations or [], provider_response_raw=None,
        extraction_metadata={"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
    )


def test_arrays_concatenate_in_order():
    merged = merge_outputs(
        [_out({"products": [{"sku": "A"}]}), _out({"products": [{"sku": "B"}]})],
        _SCHEMA, dedupe_key=None,
    )
    assert [p["sku"] for p in merged.structured_data["products"]] == ["A", "B"]


def test_dedupe_key_removes_duplicate_records():
    merged = merge_outputs(
        [_out({"products": [{"sku": "A"}]}), _out({"products": [{"sku": "A"}, {"sku": "B"}]})],
        _SCHEMA, dedupe_key="sku",
    )
    assert [p["sku"] for p in merged.structured_data["products"]] == ["A", "B"]


def test_exact_record_dedupe_without_key():
    merged = merge_outputs(
        [_out({"products": [{"sku": "A"}]}), _out({"products": [{"sku": "A"}]})],
        _SCHEMA, dedupe_key=None,
    )
    assert merged.structured_data["products"] == [{"sku": "A"}]


def test_scalar_first_non_null_wins_and_records_conflict():
    merged = merge_outputs(
        [_out({"currency": None}), _out({"currency": "EUR"}), _out({"currency": "USD"})],
        _SCHEMA, dedupe_key=None,
    )
    assert merged.structured_data["currency"] == "EUR"
    conflicts = merged.extraction_metadata["scalarConflicts"]
    assert conflicts == [{"path": "currency", "kept": "EUR", "discarded": "USD"}]


def test_citations_repathed_to_merged_array_positions():
    c0 = FieldCitation(field_path="products[0].sku", page_index=1, block_ids=None, text_spans=None)
    c1 = FieldCitation(field_path="products[0].sku", page_index=4, block_ids=None, text_spans=None)
    merged = merge_outputs(
        [_out({"products": [{"sku": "A"}]}, [c0]),
         _out({"products": [{"sku": "B"}]}, [c1])],
        _SCHEMA, dedupe_key=None,
    )
    paths = sorted(c.field_path for c in merged.citations)
    assert paths == ["products[0].sku", "products[1].sku"]


def test_non_array_citations_pass_through():
    c = FieldCitation(field_path="currency", page_index=0, block_ids=None, text_spans=None)
    merged = merge_outputs([_out({"currency": "EUR"}, [c])], _SCHEMA, dedupe_key=None)
    assert [c.field_path for c in merged.citations] == ["currency"]


def test_usage_is_summed_and_chunk_count_recorded():
    merged = merge_outputs([_out({"products": []}), _out({"products": []})], _SCHEMA, dedupe_key=None)
    assert merged.extraction_metadata["usage"]["total_tokens"] == 6
    assert merged.extraction_metadata["chunkCount"] == 2


def test_no_conflicts_key_absent_when_consistent():
    merged = merge_outputs(
        [_out({"currency": "EUR"}), _out({"currency": "EUR"})], _SCHEMA, dedupe_key=None,
    )
    assert "scalarConflicts" not in merged.extraction_metadata


def test_model_provider_and_latency_propagated_from_chunks():
    def _chunk(latency_ms: int) -> ExtractionOutput:
        return ExtractionOutput(
            structured_data={}, source_parse_run_id=_RUN,
            citations=[], provider_response_raw=None,
            extraction_metadata={
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                "model": "claude-opus-4-7",
                "provider": "anthropic",
                "latency_ms": latency_ms,
            },
        )

    merged = merge_outputs([_chunk(1000), _chunk(2000)], _SCHEMA, dedupe_key=None)
    assert merged.extraction_metadata["model"] == "claude-opus-4-7"
    assert merged.extraction_metadata["provider"] == "anthropic"
    assert merged.extraction_metadata["latency_ms"] == 3000


def test_model_provider_absent_when_not_in_chunk_metadata():
    merged = merge_outputs([_out({}), _out({})], _SCHEMA, dedupe_key=None)
    assert "model" not in merged.extraction_metadata
    assert "provider" not in merged.extraction_metadata
    assert "latency_ms" not in merged.extraction_metadata
