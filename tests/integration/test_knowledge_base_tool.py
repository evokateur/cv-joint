import pytest
from optimizer.agents import CustomAgents


@pytest.mark.integration
@pytest.mark.slow
def test_knowledge_base_tool_returns_sources():
    """Test that knowledge base tool returns source paths"""
    agents = CustomAgents()
    tool = agents.get_knowledge_base_tool()
    result = tool._run("PHP")
    assert "Sources:" in result
    assert "/knowledge-base/" in result
    assert len(result.strip()) > 0