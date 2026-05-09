"""
Memory Store — persists user mistakes and weak topics as JSON.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from config import MEMORY_DIR


class MemoryStore:
    """Per-user JSON storage for mistakes and weak areas."""

    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or MEMORY_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _user_path(self, user_id: str) -> Path:
        return self.storage_dir / f"{user_id}.json"

    def _load(self, user_id: str) -> dict:
        path = self._user_path(user_id)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"user_id": user_id, "mistakes": [], "weak_topics": {}}

    def _save(self, user_id: str, data: dict):
        with open(self._user_path(user_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_mistake(
        self,
        user_id: str,
        question: str,
        given_answer: str,
        correct_answer: str,
        topic: str = "general",
    ):
        """Record an incorrect answer."""
        data = self._load(user_id)

        data["mistakes"].append({
            "question": question,
            "given_answer": given_answer,
            "correct_answer": correct_answer,
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Update weak topics count
        data["weak_topics"][topic] = data["weak_topics"].get(topic, 0) + 1

        self._save(user_id, data)

    def get_mistakes(self, user_id: str, limit: int = 20) -> list[dict]:
        """Get recent mistakes."""
        data = self._load(user_id)
        return data["mistakes"][-limit:]

    def get_weak_topics(self, user_id: str) -> dict[str, int]:
        """Get weak topics sorted by mistake count (descending)."""
        data = self._load(user_id)
        return dict(sorted(data["weak_topics"].items(), key=lambda x: x[1], reverse=True))

    def get_total_mistakes(self, user_id: str) -> int:
        data = self._load(user_id)
        return len(data["mistakes"])

    def clear(self, user_id: str):
        """Clear all memory for a user."""
        data = {"user_id": user_id, "mistakes": [], "weak_topics": {}}
        self._save(user_id, data)


# Singleton instance
memory_store = MemoryStore()
