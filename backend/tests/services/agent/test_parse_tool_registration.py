from app.services.agent.tools import get_tool, list_tools


def test_llamaparse_tool_registered_with_three_way_contract():
    tool = get_tool("parse.llamaparse")
    assert tool is not None
    assert tool.category == "parsing"
    assert tool.config_panel == "llamaparse"
    # runtime inputs: only the file; parser/config are design-time
    assert [f.key for f in tool.runtime_inputs] == ["source_document_id"]
    assert tool.runtime_inputs[0].widget == "source_document_picker"
    # outputs feed downstream nodes
    assert "parsed_document_id" in tool.outputs
    assert "parse_run_id" in tool.outputs


def test_all_tools_expose_contract_fields():
    for tool in list_tools():
        assert isinstance(tool.runtime_inputs, list)
        assert isinstance(tool.outputs, list)
        assert hasattr(tool, "config_panel")


def test_all_five_parsers_registered_with_bound_parser_type():
    import functools
    expected = {
        "parse.simple": ("simple", None),
        "parse.llamaparse": ("llamaparse", "llamaparse"),
        "parse.landing_ai": ("landing_ai", "landing_ai"),
        "parse.docling": ("docling", "docling"),
        "parse.custom_pipeline": ("custom_pipeline", "custom_pipeline"),
    }
    for slug, (parser_type, config_panel) in expected.items():
        tool = get_tool(slug)
        assert tool is not None, slug
        assert tool.category == "parsing"
        assert tool.config_panel == config_panel
        assert isinstance(tool.node_fn, functools.partial)
        assert tool.node_fn.keywords.get("parser_type") == parser_type
        assert [f.key for f in tool.runtime_inputs] == ["source_document_id"]
        assert "parsed_document_id" in tool.outputs
