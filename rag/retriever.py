"""
RAG Retriever — query engine for retrieving relevant document chunks.
"""

from llama_index.core import VectorStoreIndex

from rag.indexer import load_existing_index


class RAGRetriever:
    """Wraps a LlamaIndex query engine for document retrieval."""

    def __init__(self):
        self._index: VectorStoreIndex | None = None

    @property
    def index(self) -> VectorStoreIndex | None:
        if self._index is None:
            self._index = load_existing_index()
        return self._index

    def refresh_index(self):
        """Force reload index from ChromaDB."""
        self._index = load_existing_index()

    @property
    def is_ready(self) -> bool:
        return self.index is not None

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        allowed_sources: list[str] | None = None,
    ) -> list[dict]:
        """
        Retrieve relevant chunks for a query.
        Returns list of {text, source, score}.
        """
        if not self.is_ready:
            return []

        filters = None
        if allowed_sources:
            from llama_index.core.vector_stores import MetadataFilters, MetadataFilter
            filter_list = [
                MetadataFilter(key="file_name", value=src)
                for src in allowed_sources
            ]
            filters = MetadataFilters(filters=filter_list, condition="or")

        try:
            retriever = self.index.as_retriever(
                similarity_top_k=top_k,
                filters=filters,
            )
            nodes = retriever.retrieve(query)
        except Exception as e:
            print(f"[RAG] Error during retrieval: {e}")
            return []

        results = []
        for node in nodes:
            source = node.metadata.get("file_name", "unknown")
            results.append({
                "text": node.get_text(),
                "source": source,
                "score": round(node.score, 4) if node.score else 0.0,
            })
        return results

    def query(self, query: str) -> str:
        """
        Full RAG query — retrieves + generates answer via LlamaIndex.
        """
        if not self.is_ready:
            return "No documents indexed yet. Please upload PDFs first."

        try:
            query_engine = self.index.as_query_engine(similarity_top_k=5)
            response = query_engine.query(query)
            return str(response)
        except Exception as e:
            print(f"[RAG] Error during query: {e}")
            return f"Error connecting to local embedding model: {e}"


# Singleton instance
rag_retriever = RAGRetriever()
