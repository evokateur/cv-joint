"""
Knowledge base search tool for CrewAI agents.

Uses the shared MCP session from McpManager to search the knowledge base.
"""

import asyncio
from crewai.tools import BaseTool
from infrastructure import McpManager


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

    def _run(self, query: str) -> str:
        """Search the knowledge base for relevant experience."""
        return asyncio.run(self._async_search(query))

    async def _async_search(self, query: str) -> str:
        """Async implementation of the search."""
        session = await McpManager.get_session("rag-knowledge")
        tool_name = McpManager.get_tool_name("rag-knowledge")

        result = await session.call_tool(tool_name, {
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
