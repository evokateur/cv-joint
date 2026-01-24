"""
Knowledge base chat service - RAG-equipped chat using MCP server.
"""

import asyncio
import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, convert_to_messages
from langchain_core.documents import Document
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config.settings import get_mcp_config, get_chat_config


class KnowledgeChatService:
    """Service for RAG-equipped chat using MCP server for knowledge retrieval."""

    def __init__(self, mcp_server_name: str = "rag-knowledge"):
        mcp_config = get_mcp_config(mcp_server_name)
        if mcp_config is None:
            raise ValueError(f"MCP server '{mcp_server_name}' not configured")

        self._mcp_config = mcp_config
        self._tool_name = mcp_config.tool_name
        self._server_params = StdioServerParameters(
            command=mcp_config.command,
            args=mcp_config.args,
            env=mcp_config.env if mcp_config.env else None,
        )

        # Connection state (lazy initialization)
        self._session: Optional[ClientSession] = None
        self._client_cm = None
        self._session_cm = None
        self._read = None
        self._write = None

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


    async def _ensure_connected(self) -> ClientSession:
        """Ensure MCP connection is established, connecting if needed."""
        if self._session is not None:
            return self._session

        # Manually enter the async context managers
        self._client_cm = stdio_client(self._server_params)
        self._read, self._write = await self._client_cm.__aenter__()

        self._session_cm = ClientSession(self._read, self._write)
        self._session = await self._session_cm.__aenter__()

        await self._session.initialize()
        return self._session

    async def close(self) -> None:
        """Close the MCP connection."""
        if self._session is None:
            return

        try:
            if self._session_cm:
                await self._session_cm.__aexit__(None, None, None)
            if self._client_cm:
                await self._client_cm.__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            self._session = None
            self._session_cm = None
            self._client_cm = None
            self._read = None
            self._write = None

    async def fetch_context(self, question: str, top_k: int = 5) -> list[Document]:
        """
        Retrieve relevant context documents using MCP RAG server.

        Args:
            question: The question to retrieve context for
            top_k: Number of results to return

        Returns:
            List of relevant documents from the knowledge base
        """
        session = await self._ensure_connected()

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
