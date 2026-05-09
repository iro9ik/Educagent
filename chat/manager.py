"""
Chat Manager — CRUD operations for multi-chat system using PostgreSQL.
"""

import uuid
import json
from datetime import datetime, timezone

from api.database import SessionLocal, Chat, Message

class ChatManager:
    """Manages chat sessions with PostgreSQL persistence."""

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ----- CREATE -----
    def create_chat(
        self,
        title: str | None = None,
        search: bool = False,
        thinking: bool = False,
    ) -> dict:
        chat_id = uuid.uuid4().hex[:12]
        now = self._now()
        
        db = SessionLocal()
        try:
            db_chat = Chat(
                id=chat_id,
                title=title or f"Chat {chat_id[:6]}",
                search_enabled=search,
                thinking_enabled=thinking,
                created_at=now,
                updated_at=now
            )
            db.add(db_chat)
            db.commit()
            db.refresh(db_chat)
            return self._to_dict(db_chat)
        finally:
            db.close()

    # ----- READ -----
    def get_chat(self, chat_id: str) -> dict | None:
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                return None
            return self._to_dict(chat, include_messages=True)
        finally:
            db.close()

    def list_chats(self) -> list[dict]:
        db = SessionLocal()
        try:
            chats = db.query(Chat).order_by(Chat.updated_at.desc()).all()
            return [
                {
                    "chat_id": c.id,
                    "title": c.title,
                    "updated_at": c.updated_at,
                }
                for c in chats
            ]
        finally:
            db.close()

    # ----- UPDATE -----
    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        attached_files: list[str] | None = None,
    ) -> dict | None:
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                return None

            msg_id = uuid.uuid4().hex
            now = self._now()
            
            new_msg = Message(
                id=msg_id,
                chat_id=chat.id,
                role=role,
                content=content,
                timestamp=now,
                attached_files=json.dumps(attached_files or []),
            )
            db.add(new_msg)
            
            chat.updated_at = now
            
            # Auto-title from first user message
            user_messages = [m for m in chat.messages if m.role == "user"]
            if role == "user" and len(user_messages) == 0:
                chat.title = content[:50] + ("..." if len(content) > 50 else "")

            db.commit()
            db.refresh(new_msg)
            return {
                "id": new_msg.id,
                "role": new_msg.role,
                "content": new_msg.content,
                "timestamp": new_msg.timestamp,
                "attached_files": attached_files or [],
            }
        finally:
            db.close()

    def update_settings(self, chat_id: str, search: bool, thinking: bool) -> dict | None:
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                return None

            chat.search_enabled = search
            chat.thinking_enabled = thinking
            chat.updated_at = self._now()

            db.commit()
            return self._to_dict(chat)
        finally:
            db.close()

    def rename_chat(self, chat_id: str, title: str) -> bool:
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                return False
            chat.title = title
            chat.updated_at = self._now()
            db.commit()
            return True
        finally:
            db.close()

    # ----- DELETE -----
    def delete_chat(self, chat_id: str) -> bool:
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                return False
            db.delete(chat)
            db.commit()
            return True
        finally:
            db.close()

    # ----- HELPERS -----
    def get_history(self, chat_id: str, last_n: int = 10) -> list[dict]:
        db = SessionLocal()
        try:
            messages = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.timestamp.asc()).all()
            return [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                for m in messages[-last_n:]
                if m.status in ("completed", "streaming")  # skip failed/stopped from history context
            ]
        finally:
            db.close()

    def get_chat_files(self, chat_id: str) -> list[str]:
        """Return unique PDF filenames attached within a single chat."""
        db = SessionLocal()
        try:
            messages = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.timestamp.asc()).all()
            files: list[str] = []
            seen = set()
            for message in messages:
                for filename in self._json_list(getattr(message, "attached_files", None)):
                    if filename not in seen:
                        seen.add(filename)
                        files.append(filename)
            return files
        finally:
            db.close()

    def create_placeholder_message(
        self,
        chat_id: str,
        generation_id: str,
    ) -> dict:
        """Create a placeholder assistant message for streaming."""
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")

            msg_id = uuid.uuid4().hex
            now = self._now()

            new_msg = Message(
                id=msg_id,
                chat_id=chat_id,
                role="assistant",
                content="",
                timestamp=now,
                status="streaming",
                generation_id=generation_id,
            )
            db.add(new_msg)
            chat.updated_at = now
            db.commit()
            db.refresh(new_msg)

            return {
                "id": new_msg.id,
                "role": new_msg.role,
                "content": new_msg.content,
                "timestamp": new_msg.timestamp,
                "status": new_msg.status,
                "generation_id": new_msg.generation_id,
            }
        finally:
            db.close()

    def update_message_content(
        self,
        message_id: str,
        content: str,
        status: str,
        reasoning: str | None = None,
        sources: list[str] | None = None,
        agent_steps: list[dict] | None = None,
    ):
        """Update message content and status (called by generation task)."""
        db = SessionLocal()
        try:
            msg = db.query(Message).filter(Message.id == message_id).first()
            if msg:
                msg.content = content
                msg.status = status
                msg.timestamp = self._now()
                if reasoning is not None:
                    msg.reasoning = reasoning
                if sources is not None:
                    msg.sources = json.dumps(sources)
                if agent_steps is not None:
                    msg.agent_steps = json.dumps(agent_steps)

                # Also update the chat's updated_at
                chat = db.query(Chat).filter(Chat.id == msg.chat_id).first()
                if chat:
                    chat.updated_at = self._now()

                db.commit()
        finally:
            db.close()

    def update_message_trace(
        self,
        message_id: str,
        reasoning: str | None = None,
        sources: list[str] | None = None,
        agent_steps: list[dict] | None = None,
    ):
        """Persist trace metadata for a generated assistant message."""
        db = SessionLocal()
        try:
            msg = db.query(Message).filter(Message.id == message_id).first()
            if msg:
                if reasoning is not None:
                    msg.reasoning = reasoning
                if sources is not None:
                    msg.sources = json.dumps(sources)
                if agent_steps is not None:
                    msg.agent_steps = json.dumps(agent_steps)
                db.commit()
        finally:
            db.close()

    def _json_list(self, value: str | None) -> list:
        if not value:
            return []
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def _to_dict(self, chat: Chat, include_messages: bool = False) -> dict:
        res = {
            "chat_id": chat.id,
            "title": chat.title,
            "settings": {
                "search": chat.search_enabled,
                "thinking": chat.thinking_enabled,
            },
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
        }
        if include_messages:
            res["messages"] = [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "status": getattr(m, "status", "completed"),
                    "generation_id": getattr(m, "generation_id", None),
                    "reasoning": getattr(m, "reasoning", None),
                    "sources": self._json_list(getattr(m, "sources", None)),
                    "agent_steps": self._json_list(getattr(m, "agent_steps", None)),
                    "attached_files": self._json_list(getattr(m, "attached_files", None)),
                }
                for m in chat.messages
            ]
        else:
            res["messages"] = []
        return res

# Singleton instance
chat_manager = ChatManager()
