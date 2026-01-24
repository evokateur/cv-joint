import pytest
from config.settings import is_mcp_configured


@pytest.mark.integration
def test_knowledge_chat_service_instantiates():
    """Test that KnowledgeChatService can be instantiated when MCP is configured."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from services.knowledge_chat import KnowledgeChatService

    service = KnowledgeChatService()
    assert service is not None
    assert service._session is None  # Lazy init, not connected yet


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_context_returns_documents():
    """Test that fetch_context returns Documents with expected structure."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from services.knowledge_chat import KnowledgeChatService

    service = KnowledgeChatService()
    try:
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
    finally:
        await service.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connection_persists_across_calls():
    """Test that MCP connection is reused across multiple fetch_context calls."""
    if not is_mcp_configured("rag-knowledge"):
        pytest.skip("MCP server 'rag-knowledge' not configured")

    from services.knowledge_chat import KnowledgeChatService

    service = KnowledgeChatService()
    try:
        # First call establishes connection
        await service.fetch_context("test query 1", top_k=1)
        session_after_first = service._session
        assert session_after_first is not None

        # Second call reuses connection
        await service.fetch_context("test query 2", top_k=1)
        session_after_second = service._session
        assert session_after_second is session_after_first
    finally:
        await service.close()
