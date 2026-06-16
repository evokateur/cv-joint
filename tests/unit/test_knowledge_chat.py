from types import SimpleNamespace
from unittest.mock import Mock

from config.settings import McpServerSettings
from connectors import McpManager


def test_knowledge_chat_service_uses_root_settings(monkeypatch):
    from services import knowledge_chat

    llm = Mock()
    monkeypatch.setattr(knowledge_chat, "ChatOpenAI", Mock(return_value=llm))
    monkeypatch.setattr(
        knowledge_chat,
        "get_settings",
        Mock(
            return_value=SimpleNamespace(
                chat=SimpleNamespace(model="test-chat-model", temperature=0.3),
                mcpServers={
                    "rag-knowledge": McpServerSettings(
                        command="uvx",
                        args=[],
                        env={},
                        tool_name="rag_search",
                    )
                },
            )
        ),
    )

    service = knowledge_chat.KnowledgeChatService()

    assert service._tool_name == "rag_search"
    assert isinstance(service._manager, McpManager)
    knowledge_chat.ChatOpenAI.assert_called_once_with(
        temperature=0.3,
        model_name="test-chat-model",
    )
