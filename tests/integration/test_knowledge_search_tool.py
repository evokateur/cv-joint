import json
import pytest
from config.root import get_settings
from connectors import McpManager


def _make_tool():
    settings = get_settings().mcpServers.get("rag-knowledge")
    if settings is None:
        pytest.skip("MCP server 'rag-knowledge' not configured")
    from crews.tools.knowledge_search import KnowledgeSearchTool

    return KnowledgeSearchTool(
        tool_name=settings.tool_name, manager=McpManager(settings)
    )


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_search_tool_instantiates():
    """Test that KnowledgeSearchTool can be instantiated."""
    tool = _make_tool()
    assert tool is not None
    assert tool.name == "knowledge_search"
    assert "knowledge base" in tool.description.lower()


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_search_tool_returns_results():
    """Test that KnowledgeSearchTool returns search results."""
    tool = _make_tool()
    try:
        result = tool._run("Python experience")
    finally:
        tool.close()

    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_search_tool_result_is_json():
    """Test that search results are valid JSON with expected structure."""
    tool = _make_tool()
    try:
        result = tool._run("software development experience")
    finally:
        tool.close()

    data = json.loads(result)
    assert "results" in data
    assert isinstance(data["results"], list)


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_search_tool_multiple_calls():
    """Sequential searches reuse the cached MCP session.

    The module-level event loop stays alive between calls so the session
    can serve the second search.
    """
    tool = _make_tool()
    try:
        result1 = tool._run("Python experience")
        session = tool._manager._session
        result2 = tool._run("API development")
        assert session is not None
        assert tool._manager._session is session
    finally:
        tool.close()

    data1 = json.loads(result1)
    data2 = json.loads(result2)
    assert "results" in data1
    assert "results" in data2
