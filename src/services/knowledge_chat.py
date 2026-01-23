"""
Knowledge base chat service - RAG-equipped chat for exploring candidate knowledge base.
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, convert_to_messages
from langchain_core.documents import Document
from config.settings import get_chat_config


class KnowledgeChatService:
    """Service for RAG-equipped chat about candidate's knowledge base."""

    def __init__(self):
        chat_config = get_chat_config()

        # Use configured chat model
        self.llm = ChatOpenAI(
            temperature=chat_config["temperature"], model_name=chat_config["model"]
        )

        # System prompt contextualized for job search / career exploration
        self.system_prompt_template = """
You are a knowledgeable assistant helping Wesley Hinkle with job search and career questions.
You have access to Wesley's professional knowledge base including past projects, skills, and experience.

Use the retrieved context below to answer questions about Wesley's experience, skills, and projects.
Be specific and cite relevant projects or experiences when possible.

If you don't know the answer or the context doesn't contain relevant information, say so honestly.

Retrieved Context:
{context}
"""

    def fetch_context(self, question: str) -> list[Document]:
        """
        Retrieve relevant context documents for a question.

        Args:
            question: The question to retrieve context for

        Returns:
            List of relevant documents from the knowledge base
        """
        # return self.retriever.invoke(question)

    def combined_question(self, question: str, history: list[dict] = None) -> str:
        """
        Combine conversation history into a single search query.

        Args:
            question: Current question
            history: Previous conversation messages

        Returns:
            Combined query string for better context retrieval
        """
        if not history:
            return question

        prior = "\n".join(m["content"] for m in history if m["role"] == "user")
        return prior + "\n" + question

    def answer_question(
        self, question: str, history: list[dict] = None
    ) -> tuple[str, list[Document]]:
        """
        Answer a question using RAG with conversation history.

        Args:
            question: The user's question
            history: Previous conversation messages (optional)

        Returns:
            Tuple of (answer_text, context_documents)
        """
        history = history or []

        # Combine question with history for better retrieval
        combined = self.combined_question(question, history)
        docs = self.fetch_context(combined)

        # Format context for system prompt
        context = "\n\n".join(doc.page_content for doc in docs)
        system_prompt = self.system_prompt_template.format(context=context)

        # Build message chain with history
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(convert_to_messages(history))
        messages.append(HumanMessage(content=question))

        # Get response
        response = self.llm.invoke(messages)

        return response.content, docs
