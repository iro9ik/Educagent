"""
RAG Indexer — loads PDFs, chunks them, and stores in ChromaDB.
"""

from pathlib import Path

from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore

from llama_index.core.embeddings import BaseEmbedding
from pydantic import PrivateAttr
from typing import Any, List, Optional

from config import DATA_DIR, CANCELLED_FILES, Settings

import threading

# Thread-local state to track which file is being processed by the current thread
indexing_state = threading.local()

class CancellationError(Exception):
    """Raised when indexing is cancelled by the user."""
    pass

class CancellableEmbeddingWrapper(BaseEmbedding):
    """Wraps an embedding model to check for cancellation before each batch."""
    _base: Any = PrivateAttr()

    def __init__(self, base_embed_model: Any, **kwargs: Any):
        super().__init__(
            model_name=getattr(base_embed_model, "model_name", "wrapped"),
            embed_batch_size=getattr(base_embed_model, "embed_batch_size", 1),
            callback_manager=getattr(base_embed_model, "callback_manager", None),
            **kwargs
        )
        self._base = base_embed_model

    def _check_cancellation(self):
        current_file = getattr(indexing_state, "current_file", None)
        if current_file and current_file in CANCELLED_FILES:
            raise CancellationError(f"Indexing cancelled for {current_file}")

    def _get_query_embedding(self, query: str) -> List[float]:
        self._check_cancellation()
        return self._base.get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        self._check_cancellation()
        return self._base.get_text_embedding(text)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        self._check_cancellation()
        return await self._base.aget_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        self._check_cancellation()
        return await self._base.aget_text_embedding(text)

def index_documents(files: list[Path] | None = None) -> tuple[VectorStoreIndex, int]:
    """
    Load specific PDFs, chunk, embed, and store in ChromaDB.
    """
    if files is None:
        # Default to all supported file types in the data directory
        extensions = ["*.pdf", "*.docx", "*.txt", "*.csv", "*.json", "*.md", "*.pptx"]
        files = []
        for ext in extensions:
            files.extend(DATA_DIR.glob(ext))

    # Load documents
    documents = []
    for file_path in files:
        if not file_path.exists():
            continue
        # Ensure it's not already cancelled before we even start
        if file_path.name in CANCELLED_FILES:
            print(f"[*] Skipping cancelled file: {file_path.name}")
            continue
            
        doc_loader = SimpleDirectoryReader(input_files=[str(file_path)])
        documents.extend(doc_loader.load_data())

    if not documents:
        return load_existing_index() or VectorStoreIndex.from_documents([]), 0

    # Setup storage
    from config import get_chroma_client, CHROMA_COLLECTION_NAME
    chroma_client = get_chroma_client()
    chroma_collection = chroma_client.get_or_create_collection(CHROMA_COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    from llama_index.core.node_parser import SentenceSplitter
    
    # Get existing index or create empty one
    index = load_existing_index()
    
    num_indexed = 0
    for doc in documents:
        fname = doc.metadata.get("file_name")
        indexing_state.current_file = fname # Set thread-local state
        
        try:
            if fname in CANCELLED_FILES:
                print(f"[*] Stopping indexing for cancelled file: {fname}")
                continue
            
            # If index doesn't exist, create it with the first doc
            if index is None:
                index = VectorStoreIndex.from_documents(
                    [doc],
                    storage_context=storage_context,
                    transformations=[SentenceSplitter(chunk_size=128, chunk_overlap=10)],
                    show_progress=True,
                )
            else:
                index.insert(doc)
            num_indexed += 1
        except CancellationError as e:
            print(f"[*] Interrupted: {e}")
            # Continue to next file (if any)
        finally:
            indexing_state.current_file = None

    return index, num_indexed


def load_existing_index() -> VectorStoreIndex | None:
    """
    Load an existing ChromaDB index (no re-embedding).
    Returns None if collection is empty.
    """
    try:
        from config import get_chroma_client, CHROMA_COLLECTION_NAME
        chroma_client = get_chroma_client()
        chroma_collection = chroma_client.get_or_create_collection(CHROMA_COLLECTION_NAME)

        if chroma_collection.count() == 0:
            return None

        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
        )
        return index
    except Exception as e:
        print(f"[!] Could not load existing index: {e}")
        return None


def build_index_if_needed() -> VectorStoreIndex | None:
    """
    Called on startup. If ChromaDB already has data, load it.
    If PDFs exist but no index, build it.
    """
    # Try loading existing index
    index = load_existing_index()
    if index is not None:
        print(f"[*] Loaded existing index from ChromaDB.")
        return index

    # Try building from uploaded documents
    extensions = ["*.pdf", "*.docx", "*.txt", "*.csv", "*.json", "*.md", "*.pptx"]
    has_files = any(DATA_DIR.glob(ext) for ext in extensions)
    if DATA_DIR.exists() and has_files:
        print("[*] Found documents without index. Building now...")
        index, count = index_documents()
        print(f"[+] Indexed {count} documents.")
        return index

    print("[-] No PDFs found. Upload documents to get started.")
    return None
