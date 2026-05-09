"""
Feedback Agent — generates personalized study feedback based on memory.
"""

from agents.base import BaseAgent
from memory.store import memory_store


class FeedbackAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Feedback Agent",
            system_prompt=(
                "You are a personalized learning coach. Your job is to:\n"
                "1. Analyze the student's mistake history\n"
                "2. Identify patterns in their weak areas\n"
                "3. Provide specific, actionable study recommendations\n"
                "4. Be encouraging while being honest about areas for improvement\n"
                "5. Prioritize the most impactful areas to focus on\n\n"
                "Be supportive, specific, and constructive in your feedback."
            ),
        )

    def run(self, user_id: str, **kwargs) -> dict:
        """
        Generate personalized feedback for a user.
        Returns {weak_topics, total_mistakes, recommendations, summary}.
        """
        weak_topics = memory_store.get_weak_topics(user_id)
        total_mistakes = memory_store.get_total_mistakes(user_id)
        recent_mistakes = memory_store.get_mistakes(user_id, limit=10)

        if total_mistakes == 0:
            return {
                "user_id": user_id,
                "weak_topics": [],
                "total_mistakes": 0,
                "recommendations": ["Keep studying! No mistakes recorded yet."],
                "summary": "No learning data available yet. Start taking quizzes to get personalized feedback!",
            }

        # Format mistakes for LLM
        mistakes_text = "\n".join(
            f"- Topic: {m.get('topic', 'unknown')} | "
            f"Q: {m['question'][:80]} | "
            f"Given: {m['given_answer'][:50]} | "
            f"Correct: {m['correct_answer'][:50]}"
            for m in recent_mistakes
        )

        topics_text = ", ".join(
            f"{topic} ({count} mistakes)" for topic, count in weak_topics.items()
        )

        prompt = (
            f"Student Profile:\n"
            f"- Total mistakes: {total_mistakes}\n"
            f"- Weak topics: {topics_text}\n\n"
            f"Recent Mistakes:\n{mistakes_text}\n\n"
            "Provide:\n"
            "1. A brief encouraging summary (2-3 sentences)\n"
            "2. Top 3-5 specific study recommendations\n"
            "Keep it concise and actionable."
        )

        summary = super().run(prompt)

        # Extract recommendations (the LLM provides them in the summary)
        recommendations = [
            f"Focus on: {topic}" for topic in list(weak_topics.keys())[:5]
        ]

        return {
            "user_id": user_id,
            "weak_topics": list(weak_topics.keys()),
            "total_mistakes": total_mistakes,
            "recommendations": recommendations,
            "summary": summary,
        }


feedback_agent = FeedbackAgent()
