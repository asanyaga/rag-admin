from app.services.agent.tools import get_tool


def _inputs(slug):
    return {f.key: f.source for f in get_tool(slug).runtime_inputs}


def test_extract_declares_form_inputs():
    assert _inputs("llamaextract") == {
        "document_id": "form", "extraction_schema_id": "form",
    }


def test_review_and_export_declare_upstream_extracted_data():
    assert _inputs("human-review") == {"extracted_data": "upstream"}
    assert _inputs("export") == {"extracted_data": "upstream"}


def test_parse_source_document_is_form():
    assert _inputs("parse.llamaparse") == {"source_document_id": "form"}
