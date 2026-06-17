import pytest
from config.root import get_settings
from connectors import McpManager


def _get_mcp_settings(server_name: str):
    return get_settings().mcpServers.get(server_name)


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_manager_connection():
    """Test that McpManager can connect to the configured MCP server."""
    settings = _get_mcp_settings("rag-knowledge")
    if settings is None:
        pytest.skip("MCP server 'rag-knowledge' not configured")

    manager = McpManager(settings)
    try:
        session = await manager.get_session()
        assert session is not None

        tools = await session.list_tools()
        assert tools is not None
        assert hasattr(tools, "tools")

        tool_names = [tool.name for tool in tools.tools]
        assert settings.tool_name in tool_names, (
            f"Expected '{settings.tool_name}' tool, got: {tool_names}"
        )
    finally:
        await manager.close()


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_manager_caches_session():
    """Test that McpManager returns the same session on repeated calls."""
    settings = _get_mcp_settings("rag-knowledge")
    if settings is None:
        pytest.skip("MCP server 'rag-knowledge' not configured")

    manager = McpManager(settings)
    try:
        session1 = await manager.get_session()
        session2 = await manager.get_session()

        assert session1 is session2
    finally:
        await manager.close()
