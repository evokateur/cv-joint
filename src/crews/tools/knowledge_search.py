"""
Knowledge base search tool for CrewAI agents.

Uses a shared McpManager instance to search the knowledge base.
"""

import asyncio
from pydantic import PrivateAttr
from crewai.tools import BaseTool
from connectors import McpManager

_loop = asyncio.new_event_loop()


class KnowledgeSearchTool(BaseTool):
    """
    Search the knowledge base for information about the candidate's
    experience, skills, and projects.
    """

    name: str = "knowledge_search"
    description: str = (
        "Search the knowledge base for information about the candidate's "
        "experience, skills, and projects. Use this to find evidence for "
        "CV optimization recommendations. Input should be a search query string."
    )

    _tool_name: str = PrivateAttr()
    _manager: McpManager = PrivateAttr()

    def __init__(self, tool_name: str, manager: McpManager, **data):
        super().__init__(**data)
        self._tool_name = tool_name
        self._manager = manager

    def _run(self, query: str) -> str:
        """Search the knowledge base for relevant experience."""
        return _loop.run_until_complete(self._async_search(query))

    async def _async_search(self, query: str) -> str:
        """Async implementation of the search."""
        session = await self._manager.get_session()

        result = await session.call_tool(self._tool_name, {
            "params": {
                "query": query,
                "top_k": 5,
                "response_format": "json"
            }
        })

        if result.isError:
            error_text = result.content[0].text if result.content else "Unknown error"
            return f"Search failed: {error_text}"

        return result.content[0].text
