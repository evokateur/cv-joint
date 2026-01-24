import pytest
from config.settings import is_mcp_configured, get_mcp_config


@pytest.mark.integration
def test_mcp_configuration_check():
    """Test that MCP configuration check function works"""
    result = is_mcp_configured("rag-knowledge")
    assert isinstance(result, bool)


@pytest.mark.integration
def test_mcp_server_connection():
    """Test that we can connect to the configured MCP server"""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    mcp_config = get_mcp_config("rag-knowledge")
    server_params = StdioServerParameters(
        command=mcp_config.command,
        args=mcp_config.args,
        env=mcp_config.env if mcp_config.env else None,
    )

    async def check_connection():
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return tools

    result = asyncio.run(check_connection())
    assert result is not None
    assert hasattr(result, "tools")

    tool_names = [tool.name for tool in result.tools]
    expected_tool = mcp_config.tool_name
    assert expected_tool in tool_names, (
        f"Expected '{expected_tool}' tool, got: {tool_names}"
    )
