"""
Knowledge base chat service - RAG-equipped chat using MCP server.
"""

import asyncio
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, convert_to_messages
from langchain_core.documents import Document

from config.settings import get_mcp_config, get_chat_config
from infrastructure import McpManager


class KnowledgeChatService:
    """Service for RAG-equipped chat using MCP server for knowledge retrieval."""

    def __init__(self, mcp_server_name: str = "rag-knowledge"):
        mcp_config = get_mcp_config(mcp_server_name)
        if mcp_config is None:
            raise ValueError(f"MCP server '{mcp_server_name}' not configured")

        self._server_name = mcp_server_name
        self._tool_name = mcp_config.tool_name

        # LLM setup
        chat_config = get_chat_config()
        self.llm = ChatOpenAI(
            temperature=chat_config["temperature"],
            model_name=chat_config["model"]
        )

        self.system_prompt_template = """
You are a knowledgeable assistant helping Wesley Hinkle with job search and career questions.
You have access to Wesley's professional knowledge base including past projects, skills, and experience.

Use the retrieved context below to answer questions about Wesley's experience, skills, and projects.
Be specific and cite relevant projects or experiences when possible.

If you don't know the answer or the context doesn't contain relevant information, say so honestly.

Retrieved Context:
{context}
"""

    async def fetch_context(self, question: str, top_k: int = 5) -> list[Document]:
        """
        Retrieve relevant context documents using MCP RAG server.

        Args:
            question: The question to retrieve context for
            top_k: Number of results to return

        Returns:
            List of relevant documents from the knowledge base
        """
        session = await McpManager.get_session(self._server_name)

        result = await session.call_tool(self._tool_name, {
            "params": {
                "query": question,
                "top_k": top_k,
                "response_format": "json"
            }
        })

        if result.isError:
            error_text = result.content[0].text if result.content else "Unknown error"
            raise RuntimeError(f"MCP search failed: {error_text}")

        # Parse JSON response
        response_text = result.content[0].text
        data = json.loads(response_text)

        # Convert to LangChain Documents
        documents = []
        for item in data.get("results", []):
            doc = Document(
                page_content=item["content"],
                metadata={
                    "id": item["id"],
                    "score": item["score"],
                    **item.get("metadata", {})
                }
            )
            documents.append(doc)

        return documents

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

    async def answer_question(
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
        docs = await self.fetch_context(combined)

        # Format context for system prompt
        context = "\n\n".join(doc.page_content for doc in docs)
        system_prompt = self.system_prompt_template.format(context=context)

        # Build message chain with history
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(convert_to_messages(history))
        messages.append(HumanMessage(content=question))

        # Get response (LLM invoke is sync, but we're in async context)
        response = await asyncio.to_thread(self.llm.invoke, messages)

        return response.content, docs
