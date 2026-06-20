__all__ = ["ApplicationService", "KnowledgeChatService"]


def __getattr__(name):
    if name == "ApplicationService":
        from .application import ApplicationService

        return ApplicationService
    if name == "KnowledgeChatService":
        from .knowledge_chat import KnowledgeChatService

        return KnowledgeChatService
    raise AttributeError(name)
