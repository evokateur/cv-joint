import pytest
from config.settings import is_mcp_configured


@pytest.mark.slow
@pytest.mark.integration
def test_knowledge_chat_service_instantiates():
    """Test that KnowledgeChatService can be instantiated when MCP is configured."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from services.knowledge_chat import KnowledgeChatService

    service = KnowledgeChatService()
    assert service is not None


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_context_returns_documents():
    """Test that fetch_context returns Documents with expected structure."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from services.knowledge_chat import KnowledgeChatService

    service = KnowledgeChatService()
    docs = await service.fetch_context("Python experience", top_k=2)

    assert isinstance(docs, list)
    assert len(docs) > 0

    for doc in docs:
        assert hasattr(doc, "page_content")
        assert hasattr(doc, "metadata")
        assert isinstance(doc.page_content, str)
        assert len(doc.page_content) > 0
        assert "source" in doc.metadata
        assert "score" in doc.metadata


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_queries_work():
    """Test that multiple queries can be made in sequence."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from services.knowledge_chat import KnowledgeChatService

    service = KnowledgeChatService()

    docs1 = await service.fetch_context("test query 1", top_k=1)
    assert len(docs1) > 0

    docs2 = await service.fetch_context("test query 2", top_k=1)
    assert len(docs2) > 0
