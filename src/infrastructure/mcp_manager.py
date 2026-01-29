"""
MCP server connection manager - provides shared sessions for MCP servers.

Lazy-starts connections on first access. Multiple consumers (KB chat, CrewAI tools)
can share the same session.
"""

from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config.settings import get_mcp_config


class McpManager:
    """
    Manages MCP server connections as lazy-started singletons.

    Usage:
        session = await McpManager.get_session("rag-knowledge")
        result = await session.call_tool("search", {...})
    """

    _sessions: dict[str, ClientSession] = {}
    _client_cms: dict[str, Any] = {}
    _session_cms: dict[str, Any] = {}
    _read_write: dict[str, tuple] = {}

    @classmethod
    def clear(cls, server_name: Optional[str] = None) -> None:
        """
        Clear cached session state without proper cleanup.
        Useful for test isolation when event loops change between tests.
        """
        if server_name:
            cls._sessions.pop(server_name, None)
            cls._session_cms.pop(server_name, None)
            cls._client_cms.pop(server_name, None)
            cls._read_write.pop(server_name, None)
        else:
            cls._sessions.clear()
            cls._session_cms.clear()
            cls._client_cms.clear()
            cls._read_write.clear()

    @classmethod
    async def get_session(cls, server_name: str) -> ClientSession:
        """
        Get or create an MCP session for the named server.

        Lazy-starts the connection on first access.
        """
        if server_name in cls._sessions:
            return cls._sessions[server_name]

        mcp_config = get_mcp_config(server_name)
        if mcp_config is None:
            raise ValueError(f"MCP server '{server_name}' not configured")

        server_params = StdioServerParameters(
            command=mcp_config.command,
            args=mcp_config.args,
            env=mcp_config.env if mcp_config.env else None,
        )

        client_cm = stdio_client(server_params)
        read, write = await client_cm.__aenter__()
        cls._client_cms[server_name] = client_cm
        cls._read_write[server_name] = (read, write)

        session_cm = ClientSession(read, write)
        session = await session_cm.__aenter__()
        cls._session_cms[server_name] = session_cm

        await session.initialize()
        cls._sessions[server_name] = session

        return session

    @classmethod
    def get_tool_name(cls, server_name: str) -> Optional[str]:
        """Get the configured tool name for an MCP server."""
        mcp_config = get_mcp_config(server_name)
        if mcp_config is None:
            return None
        return mcp_config.tool_name

    @classmethod
    async def close(cls, server_name: str) -> None:
        """Close a specific MCP connection."""
        if server_name not in cls._sessions:
            return

        try:
            if server_name in cls._session_cms:
                await cls._session_cms[server_name].__aexit__(None, None, None)
            if server_name in cls._client_cms:
                await cls._client_cms[server_name].__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            cls._sessions.pop(server_name, None)
            cls._session_cms.pop(server_name, None)
            cls._client_cms.pop(server_name, None)
            cls._read_write.pop(server_name, None)

    @classmethod
    async def close_all(cls) -> None:
        """Close all MCP connections."""
        for server_name in list(cls._sessions.keys()):
            await cls.close(server_name)
