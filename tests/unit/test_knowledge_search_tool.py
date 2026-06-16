import json
import pytest

from crews.tools.knowledge_search import KnowledgeSearchTool


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
    async def call_tool(self, name, args):
        return _ToolResult(FAKE_RESULT)


class FakeMcpManager:
    def __init__(self):
        self.closed = False

    async def get_session(self):
        return FakeMcpSession()

    async def close(self):
        self.closed = True


@pytest.fixture
def tool():
    return KnowledgeSearchTool(tool_name="rag_search_knowledge", manager=FakeMcpManager())


def test_knowledge_search_tool_returns_results(tool):
    result = tool._run("Python experience")
    data = json.loads(result)
    assert "results" in data


def test_knowledge_search_tool_multiple_calls(tool):
    """Two sequential calls on the same tool instance both return results."""
    result1 = tool._run("Python experience")
    result2 = tool._run("API development")

    assert "results" in json.loads(result1)
    assert "results" in json.loads(result2)


def test_knowledge_search_tool_closes_manager():
    manager = FakeMcpManager()
    tool = KnowledgeSearchTool(tool_name="rag_search_knowledge", manager=manager)

    tool.close()

    assert manager.closed is True
