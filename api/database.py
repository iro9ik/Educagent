import os
from dotenv import load_dotenv

load_dotenv()

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, ForeignKey, Text, Float, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

DB_NAME = os.getenv("POSTGRES_DB", "agent")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

# 1. Ensure the database exists
try:
    # Connect to the default 'postgres' database to create our target database
    conn = psycopg2.connect(
        dbname="postgres",
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_NAME}'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Warning: Could not automatically verify/create database '{DB_NAME}'. Error: {e}")

# 2. Setup SQLAlchemy Engine
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 3. Define Models
class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, index=True)
    search_enabled = Column(Boolean, default=False)
    thinking_enabled = Column(Boolean, default=False)
    created_at = Column(String)
    updated_at = Column(String)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.timestamp")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey("chats.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    timestamp = Column(String)
    status = Column(String, default="completed")  # pending, streaming, completed, stopped, failed
    generation_id = Column(String, nullable=True, index=True)
    reasoning = Column(Text, nullable=True)
    sources = Column(Text, nullable=True)
    agent_steps = Column(Text, nullable=True)
    attached_files = Column(Text, nullable=True)

    chat = relationship("Chat", back_populates="messages")

class GlobalConfig(Base):
    __tablename__ = "global_config"
    
    id = Column(String, primary_key=True) # Always "default"
    provider = Column(String, default="ollama")
    base_url = Column(String, default="")
    api_key = Column(String, default="")
    model = Column(String, default="qwen3:8b")
    embed_model = Column(String, default="nomic-embed-text")

# 4. Create Tables
Base.metadata.create_all(bind=engine)

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS reasoning TEXT"))
    conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS sources TEXT"))
    conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS agent_steps TEXT"))
    conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS attached_files TEXT"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
