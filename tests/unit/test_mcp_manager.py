import pytest

from config.settings import McpServerSettings
from connectors import McpManager
from connectors import mcp_manager


class FakeClientContext:
    def __init__(self):
        self.exited = False

    async def __aenter__(self):
        return "read", "write"

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.exited = True


class FailingSession:
    async def initialize(self):
        raise RuntimeError("initialize failed")


class FakeSessionContext:
    def __init__(self):
        self.exited = False

    async def __aenter__(self):
        return FailingSession()

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.exited = True


@pytest.mark.asyncio
async def test_get_session_cleans_up_partial_startup(monkeypatch):
    client_context = FakeClientContext()
    session_context = FakeSessionContext()

    monkeypatch.setattr(mcp_manager, "stdio_client", lambda params: client_context)
    monkeypatch.setattr(mcp_manager, "ClientSession", lambda read, write: session_context)

    manager = McpManager(
        McpServerSettings(
            command="uvx",
            args=[],
            env={},
            tool_name="rag_search",
        )
    )

    with pytest.raises(RuntimeError, match="initialize failed"):
        await manager.get_session()

    assert session_context.exited is True
    assert client_context.exited is True
    assert manager._session is None
    assert manager._session_cm is None
    assert manager._client_cm is None
