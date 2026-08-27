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
