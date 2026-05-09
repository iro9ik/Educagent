"""
Memory Agent — stores incorrect answers and weak topics.
"""

from agents.base import BaseAgent
from memory.store import memory_store


class MemoryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Memory Agent",
            system_prompt="You are a learning memory manager.",
        )

    def run(
        self,
        user_id: str,
        evaluations: list[dict],
        answers: list[dict],
        **kwargs,
    ) -> dict:
        """
        Store incorrect answers in memory.
        evaluations: list from EvaluationAgent
        answers: original answer submissions
        Returns summary of what was stored.
        """
        mistakes_added = 0

        for eval_result, answer in zip(evaluations, answers):
            if not eval_result.get("is_correct", True):
                memory_store.add_mistake(
                    user_id=user_id,
                    question=answer["question"],
                    given_answer=answer["given_answer"],
                    correct_answer=answer["correct_answer"],
                    topic=eval_result.get("topic", "general"),
                )
                mistakes_added += 1

        return {
            "user_id": user_id,
            "mistakes_added": mistakes_added,
            "total_mistakes": memory_store.get_total_mistakes(user_id),
            "weak_topics": memory_store.get_weak_topics(user_id),
        }

    def get_user_summary(self, user_id: str) -> dict:
        """Get a summary of the user's mistake history."""
        return {
            "user_id": user_id,
            "total_mistakes": memory_store.get_total_mistakes(user_id),
            "weak_topics": memory_store.get_weak_topics(user_id),
            "recent_mistakes": memory_store.get_mistakes(user_id, limit=10),
        }


memory_agent = MemoryAgent()
