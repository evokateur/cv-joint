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
