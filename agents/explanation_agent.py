"""
Explanation Agent — produces final user-friendly answers.
"""

from agents.base import BaseAgent


class ExplanationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Explanation Agent",
            system_prompt=(
                "You are an expert educational explainer. Your job is to:\n"
                "1. Take the provided context and query\n"
                "2. Create a clear, student-friendly explanation\n"
                "3. Use simple language while maintaining accuracy\n"
                "4. Include relevant examples when helpful\n"
                "5. Structure the answer with headings and bullet points if appropriate\n"
                "6. Make complex topics accessible\n\n"
                "Your answer should be comprehensive yet easy to understand for a student."
            ),
        )

    def run(self, query: str, context: str = "", history: str = "", **kwargs) -> str:
        """
        Generate a student-friendly answer from the provided context.
        """
        prompt = self._build_prompt(query, context, history)
        return super().run(prompt)

    def stream(self, query: str, context: str = "", history: str = "", **kwargs):
        """Stream chunks of the explanation."""
        prompt = self._build_prompt(query, context, history)
        return super().stream(prompt)

    def _build_prompt(self, query: str, context: str = "", history: str = "") -> str:
        prompt_parts = [f"Student's Question: {query}"]

        if context:
            prompt_parts.append(f"\nAvailable Information:\n{context}")

        if history:
            prompt_parts.append(f"\nConversation History:\n{history}")

        prompt_parts.append(
            "\nProvide a clear, well-structured educational answer. "
            "Use examples and analogies where helpful."
        )
        return "\n".join(prompt_parts)


explanation_agent = ExplanationAgent()
