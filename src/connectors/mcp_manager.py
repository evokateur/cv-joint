"""
MCP server connection manager - provides a session for a single MCP server.

Lazy-starts the connection on first access.
"""

from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config.settings import McpServerSettings


class McpManager:
    """
    Manages a single MCP server connection with a lazy-started session.

    Usage:
        manager = McpManager(settings)
        session = await manager.get_session()
        result = await session.call_tool("search", {...})
    """

    def __init__(self, settings: McpServerSettings) -> None:
        self._settings = settings
        self._session: Optional[ClientSession] = None
        self._client_cm: Any = None
        self._session_cm: Any = None

    def clear(self) -> None:
        """Clear cached session state without cleanup. For test isolation."""
        self._session = None
        self._client_cm = None
        self._session_cm = None

    async def get_session(self) -> ClientSession:
        """Get or create the MCP session. Lazy-starts the connection on first access."""
        if self._session is not None:
            return self._session

        server_params = StdioServerParameters(
            command=self._settings.command,
            args=self._settings.args,
            env=self._settings.env if self._settings.env else None,
        )

        client_cm = stdio_client(server_params)
        read, write = await client_cm.__aenter__()
        self._client_cm = client_cm

        session_cm = ClientSession(read, write)
        session = await session_cm.__aenter__()
        self._session_cm = session_cm

        await session.initialize()
        self._session = session

        return session

    async def close(self) -> None:
        """Close the MCP connection."""
        if self._session is None:
            return
        try:
            if self._session_cm is not None:
                await self._session_cm.__aexit__(None, None, None)
            if self._client_cm is not None:
                await self._client_cm.__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            self._session = None
            self._session_cm = None
            self._client_cm = None
