import asyncio
import json
import pytest
import anyio

from infrastructure import McpManager


FAKE_RESULT = json.dumps({
    "query": "test",
    "results_count": 1,
    "results": [
        {"id": "doc_1", "content": "Python experience", "score": 0.9, "metadata": {"source": "test.md"}}
    ]
})


class _TextContent:
    def __init__(self, text):
        self.text = text


class _ToolResult:
    def __init__(self, text):
        self.isError = False
        self.content = [_TextContent(text)]


class FakeMcpSession:
    """Simulates a real MCP session's event loop lifecycle.

    A real session's underlying streams are closed when the event loop that
    created them is closed (e.g. by asyncio.run()). This fake replicates that
    by raising ClosedResourceError when called from a different loop.
    """

    def __init__(self):
        self._loop = asyncio.get_running_loop()

    async def call_tool(self, name, args):
        if asyncio.get_running_loop() is not self._loop:
            raise anyio.ClosedResourceError()
        return _ToolResult(FAKE_RESULT)


@pytest.fixture(autouse=True)
def fake_mcp_manager(monkeypatch):
    _cache = {}

    async def fake_get_session(server_name):
        if server_name not in _cache:
            _cache[server_name] = FakeMcpSession()
        return _cache[server_name]

    monkeypatch.setattr(McpManager, "get_session", fake_get_session)
    monkeypatch.setattr(McpManager, "get_tool_name", lambda name: "rag_search_knowledge")


def test_knowledge_search_tool_returns_results():
    from crews.tools.knowledge_search import KnowledgeSearchTool

    tool = KnowledgeSearchTool()
    result = tool._run("Python experience")

    data = json.loads(result)
    assert "results" in data


def test_knowledge_search_tool_multiple_calls():
    """Regression: second call must not fail when the first asyncio.run() closed the event loop."""
    from crews.tools.knowledge_search import KnowledgeSearchTool

    tool = KnowledgeSearchTool()
    result1 = tool._run("Python experience")
    result2 = tool._run("API development")

    assert "results" in json.loads(result1)
    assert "results" in json.loads(result2)
