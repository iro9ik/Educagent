"""
Checker Agent — reviews generated output for coherence and consistency.
"""

from agents.base import BaseAgent


class CheckerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Checker Agent",
            system_prompt=(
                "You are a quality assurance reviewer for educational content. Your job is to:\n"
                "1. Review the provided answer for accuracy\n"
                "2. Check for logical coherence and consistency\n"
                "3. Verify the answer addresses the original question\n"
                "4. Ensure clarity and completeness\n"
                "5. Fix any issues found\n\n"
                "If the answer is good, return it as-is. "
                "If it needs improvements, return the corrected version. "
                "Always return ONLY the final answer — do not include meta-commentary about the review process."
            ),
        )

    def run(self, query: str, draft_answer: str, **kwargs) -> str:
        """
        Review and optionally revise a draft answer.
        Returns the approved/revised answer.
        """
        prompt = (
            f"Original Question: {query}\n\n"
            f"Draft Answer:\n{draft_answer}\n\n"
            "Review this answer. If correct, clear, and complete, return it unchanged. "
            "If there are issues, fix them and return the improved version. "
            "Return ONLY the final answer."
        )

        return super().run(prompt)


checker_agent = CheckerAgent()
