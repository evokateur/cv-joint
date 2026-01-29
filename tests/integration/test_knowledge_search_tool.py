import pytest
from config.settings import is_mcp_configured
from services.mcp_manager import McpManager


@pytest.fixture(autouse=True)
def clear_mcp_manager():
    """Clear MCP manager state before each test for isolation."""
    McpManager.clear()
    yield
    McpManager.clear()


@pytest.mark.integration
def test_knowledge_search_tool_instantiates():
    """Test that KnowledgeSearchTool can be instantiated."""
    from crews.tools.knowledge_search import KnowledgeSearchTool

    tool = KnowledgeSearchTool()
    assert tool is not None
    assert tool.name == "knowledge_search"
    assert "knowledge base" in tool.description.lower()


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


@pytest.mark.integration
def test_knowledge_search_tool_uses_shared_session():
    """Test that KnowledgeSearchTool uses the shared McpManager session."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from crews.tools.knowledge_search import KnowledgeSearchTool

    # No session yet
    assert "rag-knowledge" not in McpManager._sessions

    tool = KnowledgeSearchTool()
    tool._run("test query")

    # Session should now be cached in manager
    assert "rag-knowledge" in McpManager._sessions


@pytest.mark.integration
def test_knowledge_search_tool_result_contains_content():
    """Test that search results contain actual content."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from crews.tools.knowledge_search import KnowledgeSearchTool
    import json

    tool = KnowledgeSearchTool()
    result = tool._run("software development experience")

    # Result should be JSON with results array
    data = json.loads(result)
    assert "results" in data
    assert isinstance(data["results"], list)
