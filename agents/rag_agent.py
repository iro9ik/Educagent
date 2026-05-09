"""
RAG Agent — retrieves relevant content from indexed PDFs via ChromaDB.
"""

from agents.base import BaseAgent
from rag.retriever import rag_retriever


class RAGAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="RAG Agent",
            system_prompt="You are a document retrieval specialist.",
        )

    def run(
        self,
        query: str,
        top_k: int = 5,
        allowed_sources: list[str] | None = None,
        **kwargs,
    ) -> dict:
        """
        Retrieve relevant document chunks for the query.
        Returns {chunks: [...], context: str, sources: [...]}.
        """
        if allowed_sources is not None and len(allowed_sources) == 0:
            return {
                "chunks": [],
                "context": "",
                "sources": [],
            }

        if not rag_retriever.is_ready:
            return {
                "chunks": [],
                "context": "No documents have been indexed yet. Please upload PDFs first.",
                "sources": [],
            }

        chunks = rag_retriever.retrieve(
            query,
            top_k=top_k,
            allowed_sources=allowed_sources,
        )

        context = "\n\n---\n\n".join(
            f"[Source: {c['source']}] (Relevance: {c['score']})\n{c['text']}"
            for c in chunks
        )

        sources = list(set(c["source"] for c in chunks))

        return {
            "chunks": chunks,
            "context": context,
            "sources": sources,
        }


rag_agent = RAGAgent()
