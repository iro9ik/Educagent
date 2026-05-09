"""
Quiz Agent — generates quiz questions from indexed content.
"""

import json

from agents.base import BaseAgent
from agents.rag_agent import rag_agent


class QuizAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Quiz Agent",
            system_prompt=(
                "You are a quiz generator for educational content. Your job is to:\n"
                "1. Create quiz questions based on the provided content\n"
                "2. Generate a mix of multiple-choice (MCQ) and open-ended questions\n"
                "3. Provide correct answers for each question\n"
                "4. Make questions that test understanding, not just memorization\n\n"
                "You MUST respond with valid JSON and nothing else. Format:\n"
                '{"topic": "...", "questions": [\n'
                '  {"question": "...", "options": ["A", "B", "C", "D"], "answer": "A", "question_type": "mcq"},\n'
                '  {"question": "...", "options": null, "answer": "...", "question_type": "open_ended"}\n'
                "]}"
            ),
        )

    def run(self, topic: str = "general", num_questions: int = 5, **kwargs) -> dict:
        """
        Generate quiz questions from RAG content.
        Returns parsed quiz dict.
        """
        # Get relevant content from RAG
        allowed_sources = kwargs.get("allowed_sources")
        rag_result = rag_agent.run(
            topic,
            top_k=8,
            allowed_sources=allowed_sources,
        )
        context = rag_result.get("context", "")

        if not context or "No documents" in context:
            return {
                "topic": topic,
                "questions": [],
                "error": "No content available for this chat. Attach a PDF to this chat first.",
            }

        prompt = (
            f"Generate exactly {num_questions} quiz questions about: {topic}\n\n"
            f"Content to base questions on:\n{context}\n\n"
            f"Create {num_questions} questions (mix of MCQ and open-ended). "
            "Respond with valid JSON only."
        )

        raw_response = super().run(prompt)

        # Parse JSON response
        try:
            # Try to extract JSON from the response
            response_text = raw_response.strip()

            # Handle cases where LLM wraps JSON in code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            quiz_data = json.loads(response_text)
            return quiz_data
        except (json.JSONDecodeError, IndexError):
            # Fallback: return raw response wrapped
            return {
                "topic": topic,
                "questions": [],
                "raw_response": raw_response,
                "error": "Failed to parse quiz JSON. Raw response included.",
            }


quiz_agent = QuizAgent()
