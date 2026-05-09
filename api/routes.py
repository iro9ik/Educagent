"""
API Routes — all FastAPI endpoint definitions.
"""

import shutil
import json
import asyncio
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.models import (
    ChatCreate,
    ChatDetail,
    ChatListResponse,
    ChatMessage,
    ChatSummary,
    EvaluateRequest,
    EvaluateResponse,
    EvaluationDetail,
    FeedbackResponse,
    GenerateRequest,
    MessageRequest,
    MessageResponse,
    GlobalSettings,
    GlobalSettingsUpdate,
    QuizRequest,
    QuizResponse,
    QuizQuestion,
    RenameRequest,
    SettingsUpdate,
    UploadResponse,
)
from chat.manager import chat_manager
from config import DATA_DIR

router = APIRouter()


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------
@router.post("/chat", response_model=ChatDetail, tags=["Chat"])
async def create_chat(body: ChatCreate):
    """Create a new chat session."""
    chat = chat_manager.create_chat(
        title=body.title,
        search=body.settings.search,
        thinking=body.settings.thinking,
    )
    return ChatDetail(
        chat_id=chat["chat_id"],
        title=chat["title"],
        messages=[],
        settings=body.settings,
        created_at=chat["created_at"],
        updated_at=chat["updated_at"],
    )


@router.get("/chats", response_model=ChatListResponse, tags=["Chat"])
async def list_chats():
    """List all chat sessions."""
    chats = chat_manager.list_chats()
    return ChatListResponse(
        chats=[ChatSummary(**c) for c in chats]
    )


@router.get("/chat/{chat_id}", response_model=ChatDetail, tags=["Chat"])
async def get_chat(chat_id: str):
    """Get a specific chat with full message history."""
    chat = chat_manager.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    return ChatDetail(
        chat_id=chat["chat_id"],
        title=chat["title"],
        messages=[ChatMessage(**m) for m in chat["messages"]],
        settings=chat["settings"],
        created_at=chat["created_at"],
        updated_at=chat["updated_at"],
    )


@router.delete("/chat/{chat_id}", tags=["Chat"])
async def delete_chat(chat_id: str):
    """Delete a chat session."""
    if not chat_manager.delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"message": "Chat deleted", "chat_id": chat_id}


@router.put("/chat/{chat_id}/rename", tags=["Chat"])
async def rename_chat(chat_id: str, body: RenameRequest):
    """Rename a chat session."""
    if not chat_manager.rename_chat(chat_id, body.title):
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"message": "Chat renamed", "chat_id": chat_id, "title": body.title}


@router.put("/chat/{chat_id}/settings", tags=["Chat"])
async def update_chat_settings(chat_id: str, body: SettingsUpdate):
    """Update chat settings (search/thinking toggles)."""
    chat = chat_manager.update_settings(
        chat_id=chat_id,
        search=body.settings.search,
        thinking=body.settings.thinking,
    )
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"message": "Settings updated", "settings": chat["settings"]}


# ---------------------------------------------------------------------------
# Legacy Message endpoint (non-streaming, kept as fallback)
# ---------------------------------------------------------------------------
@router.post("/chat/{chat_id}/message", response_model=MessageResponse, tags=["Chat"])
async def send_message(chat_id: str, body: MessageRequest):
    """Send a message and get an AI response (non-streaming fallback)."""
    chat = chat_manager.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat_manager.add_message(chat_id, "user", body.content)

    search_enabled = body.search_enabled
    thinking_enabled = body.thinking_enabled

    history_messages = chat_manager.get_history(chat_id, last_n=6)
    history = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history_messages
    )

    from agents.orchestrator import orchestrator

    intent = orchestrator.classify_intent(body.content)

    if intent == "quiz":
        topic = body.content.replace("quiz", "").replace("test", "").strip() or "general"
        result = orchestrator.handle_quiz(topic=topic)

        if result.get("questions"):
            quiz_text = f"📝 **Quiz: {result.get('topic', 'General')}**\n\n"
            for i, q in enumerate(result["questions"], 1):
                quiz_text += f"**Q{i}.** {q['question']}\n"
                if q.get("options"):
                    for opt in q["options"]:
                        quiz_text += f"  - {opt}\n"
                quiz_text += "\n"
            response_text = quiz_text
        else:
            response_text = result.get("error", "Could not generate quiz.")

        chat_manager.add_message(chat_id, "assistant", response_text)
        return MessageResponse(response=response_text)

    elif intent == "greeting":
        greeting = (
            "Hello! 👋 I'm EducAgent, your AI study assistant. "
            "I can help you with:\n\n"
            "📖 **Answer questions** from your course materials\n"
            "📝 **Generate quizzes** to test your knowledge\n"
            "📊 **Track your progress** and give personalized feedback\n\n"
            "Upload PDFs to get started, then ask me anything!"
        )
        chat_manager.add_message(chat_id, "assistant", greeting)
        return MessageResponse(response=greeting)

    else:
        result = orchestrator.handle_question(
            query=body.content,
            search_enabled=search_enabled,
            thinking_enabled=thinking_enabled,
            history=history,
        )

        response_text = result["response"]
        chat_manager.add_message(chat_id, "assistant", response_text)

        return MessageResponse(
            response=response_text,
            sources=result.get("sources"),
            thinking=result.get("thinking"),
        )


# ---------------------------------------------------------------------------
# NEW: Persistent Generation endpoints
# ---------------------------------------------------------------------------
@router.post("/chat/{chat_id}/generate", tags=["Generation"])
async def start_generation(chat_id: str, body: GenerateRequest):
    """
    Start an AI generation for a chat.

    This returns immediately with a generation_id.
    The actual AI generation runs in a background task.
    Use /stream/{generation_id} to subscribe to the token stream.
    """
    from api.generation import generation_manager

    chat = chat_manager.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    result = await generation_manager.start_generation(
        chat_id=chat_id,
        user_message=body.content,
        search_enabled=body.search_enabled,
        thinking_enabled=body.thinking_enabled,
        attached_files=body.attached_files,
    )

    return {
        "generation_id": result.generation_id,
        "message_id": result.message_id,
        "chat_id": result.chat_id,
    }


@router.get("/stream/{generation_id}", tags=["Generation"])
async def stream_generation(generation_id: str, last_seq: int = 0):
    """
    SSE endpoint to subscribe to a generation's token stream.

    Query params:
    - last_seq: Last received sequence number (for reconnect). Default 0.

    Events:
    - token: { type: "token", chunk: "hello", seq: 1 }
    - completed: { type: "completed", seq: N }
    - stopped: { type: "stopped", seq: N }
    - error: { type: "error", error: "...", seq: N }
    """
    from api.generation import generation_manager

    state = await generation_manager.get_generation_state(generation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    async def event_generator():
        try:
            async for event in generation_manager.subscribe(generation_id, last_seq):
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            # Client disconnected — that's fine, generation continues
            pass
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stream/{generation_id}/stop", tags=["Generation"])
async def stop_generation(generation_id: str):
    """Stop an active generation. Partial content is saved."""
    from api.generation import generation_manager

    success = await generation_manager.stop_generation(generation_id)
    if not success:
        raise HTTPException(status_code=404, detail="No active generation found")

    return {"message": "Generation stopped", "generation_id": generation_id}


@router.get("/chat/{chat_id}/active-generation", tags=["Generation"])
async def get_active_generation(chat_id: str):
    """
    Check if a chat has an active (streaming) generation.
    Used by frontend on page load to auto-reconnect.
    """
    from api.generation import generation_manager

    state = await generation_manager.get_active_generation(chat_id)
    if state:
        return state
    return {"active": False}


# ---------------------------------------------------------------------------
# Legacy streaming endpoint (kept for backward compatibility)
# ---------------------------------------------------------------------------
@router.post("/chat/{chat_id}/message/stream", tags=["Chat"])
async def send_message_stream(chat_id: str, body: MessageRequest):
    """Send a message and get a streaming AI response (legacy)."""
    chat = chat_manager.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat_manager.add_message(chat_id, "user", body.content)

    search_enabled = body.search_enabled
    thinking_enabled = body.thinking_enabled

    history_messages = chat_manager.get_history(chat_id, last_n=6)
    history = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history_messages
    )

    from agents.orchestrator import orchestrator

    async def event_generator():
        full_response = ""
        try:
            for chunk in orchestrator.stream_question(
                query=body.content,
                search_enabled=search_enabled,
                thinking_enabled=thinking_enabled,
                history=history,
            ):
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            chat_manager.add_message(chat_id, "assistant", full_response)
            yield "data: [DONE]\n\n"
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_pdfs(files: list[UploadFile] = File(...)):
    """Upload PDF files and index them for RAG."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    saved_files = []
    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            continue

        dest = DATA_DIR / file.filename
        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)
        saved_files.append(file.filename)

    if not saved_files:
        raise HTTPException(status_code=400, detail="No valid PDF files found")

    from rag.indexer import index_documents
    from rag.retriever import rag_retriever

    try:
        index, num_docs = index_documents()
        rag_retriever.refresh_index()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

    return UploadResponse(
        files_indexed=saved_files,
        total_chunks=num_docs,
        message=f"Successfully indexed {len(saved_files)} PDF(s) with {num_docs} document chunks.",
    )


@router.get("/files", tags=["Documents"])
async def list_uploaded_files():
    """List uploaded PDF files."""
    files = sorted(f.name for f in DATA_DIR.glob("*.pdf") if f.is_file())
    return {"files": files}


# ---------------------------------------------------------------------------
# Quiz endpoint
# ---------------------------------------------------------------------------
@router.post("/quiz", response_model=QuizResponse, tags=["Assessment"])
async def generate_quiz(body: QuizRequest):
    """Generate a quiz from indexed content."""
    from agents.orchestrator import orchestrator
    from agents.base import AgentTimeoutError, RateLimitError

    allowed_sources = []
    if body.chat_id:
        allowed_sources = chat_manager.get_chat_files(body.chat_id)
    for filename in body.attached_files:
        if filename not in allowed_sources:
            allowed_sources.append(filename)
    if body.chat_id and body.attached_files:
        chat_manager.add_message(
            body.chat_id,
            "user",
            f"/quiz {body.topic or 'general'}",
            attached_files=body.attached_files,
        )

    try:
        result = orchestrator.handle_quiz(
            topic=body.topic or "general",
            num_questions=body.num_questions,
            allowed_sources=allowed_sources,
        )
    except (AgentTimeoutError, RateLimitError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    questions = []
    for q in result.get("questions", []):
        questions.append(QuizQuestion(
            question=q.get("question", ""),
            options=q.get("options"),
            answer=q.get("answer", ""),
            question_type=q.get("question_type", "mcq"),
        ))

    return QuizResponse(
        topic=result.get("topic", body.topic or "general"),
        questions=questions,
    )


# ---------------------------------------------------------------------------
# Evaluate endpoint
# ---------------------------------------------------------------------------
@router.post("/evaluate", response_model=EvaluateResponse, tags=["Assessment"])
async def evaluate_answers(body: EvaluateRequest):
    """Evaluate student answers and provide feedback."""
    from agents.orchestrator import orchestrator

    answers = [
        {
            "question": a.question,
            "given_answer": a.given_answer,
            "correct_answer": a.correct_answer,
        }
        for a in body.answers
    ]

    result = orchestrator.handle_evaluation(
        user_id=body.user_id,
        answers=answers,
    )

    details = []
    for eval_item, answer in zip(result["evaluations"], answers):
        details.append(EvaluationDetail(
            question=answer["question"],
            given_answer=answer["given_answer"],
            correct_answer=answer["correct_answer"],
            is_correct=eval_item.get("is_correct", False),
            score=eval_item.get("score", 0.0),
            explanation=eval_item.get("explanation", ""),
        ))

    return EvaluateResponse(
        total_score=result["total_score"],
        max_score=result["max_score"],
        percentage=result["percentage"],
        details=details,
        feedback=result["feedback"],
    )


# ---------------------------------------------------------------------------
# Feedback endpoint
# ---------------------------------------------------------------------------
@router.get("/feedback/{user_id}", response_model=FeedbackResponse, tags=["Assessment"])
async def get_feedback(user_id: str):
    """Get personalized study feedback for a user."""
    from agents.orchestrator import orchestrator

    result = orchestrator.handle_feedback(user_id=user_id)

    return FeedbackResponse(
        user_id=result["user_id"],
        weak_topics=result.get("weak_topics", []),
        total_mistakes=result.get("total_mistakes", 0),
        recommendations=result.get("recommendations", []),
        summary=result.get("summary", "No data available."),
    )

@router.get("/health/ollama", tags=["Health"])
async def check_ollama_health():
    """Check if local Ollama is running and the configured model is available."""
    import httpx
    from config import config

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{config.OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_available = any(
                name == config.LLM_MODEL or name.startswith(f"{config.LLM_MODEL}:")
                for name in models
            )
            if not model_available:
                return {
                    "status": "error",
                    "message": f"Ollama is running, but {config.LLM_MODEL} is not installed",
                }
            return {"status": "ok", "message": "Ollama model is available"}
    except Exception as e:
        return {"status": "error", "message": "Ollama is not accessible"}

# ---------------------------------------------------------------------------
# Global Settings endpoints
# ---------------------------------------------------------------------------
@router.get("/settings", response_model=GlobalSettings, tags=["Settings"])
async def get_global_settings():
    """Get current global LLM settings."""
    from config import config
    return GlobalSettings(
        provider=config.LLM_PROVIDER,
        base_url=config.API_BASE_URL,
        api_key=config.API_KEY,
        model=config.LLM_MODEL,
        embed_model=config.EMBED_MODEL,
    )


@router.post("/settings", tags=["Settings"])
async def update_global_settings(body: GlobalSettingsUpdate):
    """Update global LLM settings at runtime."""
    from config import config
    config.update(
        provider=body.settings.provider,
        base_url=body.settings.base_url,
        api_key=body.settings.api_key,
        model=body.settings.model,
        embed_model=body.settings.embed_model,
    )
    return {"message": "Global settings updated successfully"}
