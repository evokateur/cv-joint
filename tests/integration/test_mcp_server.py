import pytest
from config.settings import is_mcp_configured, get_mcp_config
from services.mcp_manager import McpManager


@pytest.fixture(autouse=True)
def clear_mcp_manager():
    """Clear MCP manager state before each test for isolation."""
    McpManager.clear()
    yield
    McpManager.clear()


@pytest.mark.integration
def test_mcp_configuration_check():
    """Test that MCP configuration check function works"""
    result = is_mcp_configured("rag-knowledge")
    assert isinstance(result, bool)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_manager_connection():
    """Test that McpManager can connect to the configured MCP server"""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    session = await McpManager.get_session("rag-knowledge")
    assert session is not None

    # Verify we can list tools
    tools = await session.list_tools()
    assert tools is not None
    assert hasattr(tools, "tools")

    # Verify expected tool is present
    mcp_config = get_mcp_config("rag-knowledge")
    tool_names = [tool.name for tool in tools.tools]
    expected_tool = mcp_config.tool_name
    assert expected_tool in tool_names, (
        f"Expected '{expected_tool}' tool, got: {tool_names}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_manager_caches_session():
    """Test that McpManager returns the same session on repeated calls"""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    session1 = await McpManager.get_session("rag-knowledge")
    session2 = await McpManager.get_session("rag-knowledge")

    assert session1 is session2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_manager_tool_name():
    """Test that McpManager.get_tool_name returns configured tool name"""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    tool_name = McpManager.get_tool_name("rag-knowledge")
    mcp_config = get_mcp_config("rag-knowledge")

    assert tool_name == mcp_config.tool_name


@pytest.mark.integration
def test_mcp_manager_unconfigured_server():
    """Test that McpManager raises for unconfigured server"""
    import asyncio

    with pytest.raises(ValueError, match="not configured"):
        asyncio.run(McpManager.get_session("nonexistent-server"))
