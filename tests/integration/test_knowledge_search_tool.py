import json
import pytest
from config.settings import is_mcp_configured


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_search_tool_instantiates():
    """Test that KnowledgeSearchTool can be instantiated."""
    from crews.tools.knowledge_search import KnowledgeSearchTool

    tool = KnowledgeSearchTool()
    assert tool is not None
    assert tool.name == "knowledge_search"
    assert "knowledge base" in tool.description.lower()


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_search_tool_returns_results():
    """Test that KnowledgeSearchTool returns search results."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from crews.tools.knowledge_search import KnowledgeSearchTool

    tool = KnowledgeSearchTool()
    result = tool._run("Python experience")

    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_search_tool_result_is_json():
    """Test that search results are valid JSON with expected structure."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from crews.tools.knowledge_search import KnowledgeSearchTool

    tool = KnowledgeSearchTool()
    result = tool._run("software development experience")

    data = json.loads(result)
    assert "results" in data
    assert isinstance(data["results"], list)


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_search_tool_multiple_calls():
    """Test that the tool works across multiple sequential calls.

    Regression test: asyncio.run() closes the event loop after each call,
    killing the MCP server process. The McpManager must not cache a session
    that belongs to a closed event loop.
    """
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from crews.tools.knowledge_search import KnowledgeSearchTool

    tool = KnowledgeSearchTool()
    result1 = tool._run("Python experience")
    result2 = tool._run("API development")

    data1 = json.loads(result1)
    data2 = json.loads(result2)
    assert "results" in data1
    assert "results" in data2
