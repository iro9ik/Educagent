"""
Global configuration for EducAgent.
Initializes shared LLM, embeddings, ChromaDB, and LlamaIndex settings from PostgreSQL.
"""

import os
from pathlib import Path
from typing import Optional

import chromadb
from dotenv import load_dotenv

from llama_index.core import Settings
from langchain_ollama import ChatOllama

from api.database import SessionLocal, GlobalConfig

load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
CHATS_DIR = STORAGE_DIR / "chats"
DATA_DIR = STORAGE_DIR / "uploads"
CHROMA_DIR = STORAGE_DIR / "chroma_db"
MEMORY_DIR = STORAGE_DIR / "user_memory"

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
CHATS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    def __init__(self):
        self._load_from_db()
        
        self.llm = None
        self.llama_llm = None
        self.embed_model = None
        
        self.initialize()
        
    def _load_from_db(self):
        db = SessionLocal()
        try:
            config = db.query(GlobalConfig).filter(GlobalConfig.id == "default").first()
            if not config:
                config = GlobalConfig(
                    id="default",
                    provider="ollama",
                    base_url="",
                    api_key="",
                    model="qwen3:8b",
                    embed_model="nomic-embed-text"
                )
                db.add(config)
                db.commit()
                db.refresh(config)
            
            self.LLM_PROVIDER = config.provider
            self.API_BASE_URL = config.base_url or os.getenv("API_BASE_URL", "http://localhost:11434/v1")
            self.API_KEY = config.api_key or os.getenv("API_KEY", "ollama")
            self.LLM_MODEL = config.model
            self.EMBED_MODEL = config.embed_model
            self.OLLAMA_BASE_URL = self.API_BASE_URL.replace("/v1", "") if self.LLM_PROVIDER == "custom" else os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        finally:
            db.close()

    def _save_to_db(self):
        db = SessionLocal()
        try:
            config = db.query(GlobalConfig).filter(GlobalConfig.id == "default").first()
            if not config:
                config = GlobalConfig(id="default")
                db.add(config)
            
            config.provider = self.LLM_PROVIDER
            config.base_url = self.API_BASE_URL
            config.api_key = self.API_KEY
            config.model = self.LLM_MODEL
            config.embed_model = self.EMBED_MODEL
            db.commit()
        finally:
            db.close()


    def initialize(self):
        if self.LLM_PROVIDER == "custom" or self.LLM_PROVIDER == "openai":
            from langchain_openai import ChatOpenAI
            from llama_index.llms.openai import OpenAI as LlamaIndexOpenAI

            self.llm = ChatOpenAI(
                model=self.LLM_MODEL,
                base_url=self.API_BASE_URL,
                api_key=self.API_KEY,
                temperature=0.7,
            )

            self.llama_llm = LlamaIndexOpenAI(
                model=self.LLM_MODEL,
                base_url=self.API_BASE_URL,
                api_key=self.API_KEY,
                temperature=0.7,
                request_timeout=120.0,
            )
        else:
            from llama_index.llms.ollama import Ollama as LlamaIndexOllama
            self.llm = ChatOllama(
                model=self.LLM_MODEL,
                base_url=self.OLLAMA_BASE_URL,
                temperature=0.7,
                num_ctx=8192,
            )

            self.llama_llm = LlamaIndexOllama(
                model=self.LLM_MODEL,
                base_url=self.OLLAMA_BASE_URL,
                temperature=0.7,
                request_timeout=120.0,
            )

        # Embedding model selection with proactive health check
        use_ollama = False
        if self.LLM_PROVIDER == "ollama":
            import requests
            try:
                # Quick synchronous check
                resp = requests.get(self.OLLAMA_BASE_URL, timeout=1.0)
                if resp.status_code == 200:
                    use_ollama = True
            except Exception:
                use_ollama = False

        def load_local_hf_embedding():
            try:
                from llama_index.embeddings.huggingface import HuggingFaceEmbedding
                return HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
            except Exception as e:
                print(f"[!] Warning: Could not initialize HuggingFace embeddings: {e}")
                return None

        if use_ollama:
            try:
                from llama_index.embeddings.ollama import OllamaEmbedding
                self.embed_model = OllamaEmbedding(
                    model_name=self.EMBED_MODEL,
                    base_url=self.OLLAMA_BASE_URL,
                )
            except Exception:
                self.embed_model = load_local_hf_embedding()
        else:
            self.embed_model = load_local_hf_embedding()

        if self.LLM_PROVIDER == "custom" or self.LLM_PROVIDER == "openai":
            # For custom providers (like OpenRouter), default to local HF embeddings
            # to avoid requiring the user to have Ollama installed/running just for RAG.
            self.embed_model = load_local_hf_embedding()

        # Update LlamaIndex global settings
        Settings.llm = self.llama_llm
        if self.embed_model is not None:
            Settings.embed_model = self.embed_model
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50

    def update(self, provider: str, base_url: str, api_key: Optional[str], model: str, embed_model: str):
        self.LLM_PROVIDER = provider
        self.API_BASE_URL = base_url
        self.API_KEY = api_key
        self.LLM_MODEL = model
        self.EMBED_MODEL = embed_model
        self._save_to_db()
        self.initialize()

# Singleton instance
config = Config()

# Export for backward compatibility
def get_llm():
    return config.llm

def get_llama_llm():
    return config.llama_llm

def get_embed_model():
    return config.embed_model

# ChromaDB client (persistent)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
CHROMA_COLLECTION_NAME = "educagent_docs"
