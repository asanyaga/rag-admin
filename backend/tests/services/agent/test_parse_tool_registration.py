from app.services.agent.tools import get_tool, list_tools


def test_parse_tool_is_registered_under_parsing_category():
    tool = get_tool("parse")
    assert tool is not None
    assert tool.category == "parsing"
    assert "source_document_id" in tool.input_keys
    assert "parse_run_id" in tool.output_keys
    assert "parsed_document_id" in tool.output_keys


def test_parse_tool_listed():
    slugs = {t.slug for t in list_tools()}
    assert "parse" in slugs
