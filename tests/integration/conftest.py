import pytest
from infrastructure import McpManager


@pytest.fixture(autouse=True)
def clear_mcp_manager():
    """Clear MCP manager state before and after each test for isolation."""
    McpManager.clear()
    yield
    McpManager.clear()
