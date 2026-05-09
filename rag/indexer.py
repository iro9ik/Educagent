"""
RAG Indexer — loads PDFs, chunks them, and stores in ChromaDB.
"""

from pathlib import Path

from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore

from config import DATA_DIR, chroma_client, CHROMA_COLLECTION_NAME


def index_documents(directory: Path | None = None) -> tuple[VectorStoreIndex, int]:
    """
    Load all PDFs from *directory*, chunk, embed, and store in ChromaDB.
    Returns (index, num_chunks).
    """
    target_dir = directory or DATA_DIR

    if not target_dir.exists() or not any(target_dir.iterdir()):
        raise FileNotFoundError(f"No files found in {target_dir}")

    # Load documents
    documents = SimpleDirectoryReader(
        input_dir=str(target_dir),
        recursive=True,
        required_exts=[".pdf"],
    ).load_data()

    if not documents:
        raise ValueError("No PDF documents found in the upload directory.")

    # ChromaDB collection + vector store
    chroma_collection = chroma_client.get_or_create_collection(CHROMA_COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Build index (chunks + embeddings stored automatically)
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )

    return index, len(documents)


def load_existing_index() -> VectorStoreIndex | None:
    """
    Load an existing ChromaDB index (no re-embedding).
    Returns None if collection is empty.
    """
    try:
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

    # Try building from uploaded PDFs
    if DATA_DIR.exists() and any(DATA_DIR.glob("*.pdf")):
        print("[*] Found PDFs without index. Building now...")
        index, count = index_documents()
        print(f"[+] Indexed {count} documents.")
        return index

    print("[-] No PDFs found. Upload documents to get started.")
    return None
