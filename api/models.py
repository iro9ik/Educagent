"""
Pydantic models for API request/response schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
class ChatSettings(BaseModel):
    search: bool = Field(default=False, description="Enable Search Agent")
    thinking: bool = Field(default=False, description="Enable Thinking Agent")


class ChatCreate(BaseModel):
    title: Optional[str] = Field(default=None, description="Chat title (auto-generated if empty)")
    settings: ChatSettings = Field(default_factory=ChatSettings)


class ChatSummary(BaseModel):
    chat_id: str
    title: str
    updated_at: str

class RenameRequest(BaseModel):
    title: str


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    status: str = "completed"  # pending, streaming, completed, stopped, failed
    generation_id: Optional[str] = None
    reasoning: Optional[str] = None
    sources: Optional[list[str]] = None
    agent_steps: Optional[list[dict]] = None
    attached_files: Optional[list[str]] = None


class ChatDetail(BaseModel):
    chat_id: str
    title: str
    messages: list[ChatMessage]
    settings: ChatSettings
    created_at: str
    updated_at: str


class ChatListResponse(BaseModel):
    chats: list[ChatSummary]


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="User message content")
    search_enabled: bool = Field(default=False, description="Enable Search Agent")
    thinking_enabled: bool = Field(default=False, description="Enable Thinking Agent")
    attached_files: list[str] = Field(default_factory=list, description="PDF files attached to the user message")


class GenerateRequest(MessageRequest):
    pass


class MessageResponse(BaseModel):
    response: str
    sources: Optional[list[str]] = None
    thinking: Optional[str] = None


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
class UploadResponse(BaseModel):
    files_indexed: list[str]
    total_chunks: int
    message: str


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------
class QuizRequest(BaseModel):
    topic: Optional[str] = Field(default=None, description="Topic to quiz on")
    num_questions: int = Field(default=5, ge=1, le=20)
    chat_id: Optional[str] = Field(default=None, description="Chat for context")
    attached_files: list[str] = Field(default_factory=list, description="PDF files attached for this quiz")


class QuizQuestion(BaseModel):
    question: str
    options: Optional[list[str]] = None
    answer: str
    question_type: str = "mcq"  # "mcq" or "open_ended"


class QuizResponse(BaseModel):
    topic: str
    questions: list[QuizQuestion]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
class AnswerSubmission(BaseModel):
    question: str
    given_answer: str
    correct_answer: str


class EvaluateRequest(BaseModel):
    user_id: str = Field(default="default_user")
    answers: list[AnswerSubmission]


class EvaluationDetail(BaseModel):
    question: str
    given_answer: str
    correct_answer: str
    is_correct: bool
    score: float
    explanation: str


class EvaluateResponse(BaseModel):
    total_score: float
    max_score: float
    percentage: float
    details: list[EvaluationDetail]
    feedback: str


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
class FeedbackResponse(BaseModel):
    user_id: str
    weak_topics: list[str]
    total_mistakes: int
    recommendations: list[str]
    summary: str


# ---------------------------------------------------------------------------
# Settings Update
# ---------------------------------------------------------------------------
class SettingsUpdate(BaseModel):
    settings: ChatSettings


class GlobalSettings(BaseModel):
    provider: str = Field(default="ollama", description="'ollama' or 'custom'")
    base_url: str = Field(default="")
    api_key: str = Field(default="")
    model: str = Field(default="qwen3:8b")
    embed_model: str = Field(default="nomic-embed-text")


class GlobalSettingsUpdate(BaseModel):
    settings: GlobalSettings
