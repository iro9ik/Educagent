"""
Checker Agent — explanation quality reviewer (EXPLANATION LAYER ONLY).

PIPELINE CONTRACT
-----------------
This agent operates in Layer 2 (Explanation) of the evaluation pipeline.

It receives LOCKED evaluation results from Layer 1 (EvaluationAgent):
  - verdict    → IMMUTABLE (CORRECT | INCORRECT | PARTIAL | NO_ATTEMPT)
  - is_correct → IMMUTABLE
  - score      → IMMUTABLE

It may ONLY improve the explanation text.

It MUST NOT:
  - return is_correct
  - return score
  - return verdict
  - suggest any change to the locked grading decision

Downstream (orchestrator) will ignore any score/is_correct/verdict it attempts to return.

For the Q&A pipeline (non-quiz), this agent continues to review answer quality as before.
"""

import json
import re

from agents.base import BaseAgent


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


class CheckerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Checker Agent",
            system_prompt=(
                "You are a quality assurance reviewer for educational explanations. "
                "You receive a graded answer (verdict and score are ALREADY LOCKED and cannot change). "
                "Your ONLY job is to improve the explanation text so it is:\n"
                "1. Accurate and grounded in the Correct Answer.\n"
                "2. Constructive: if wrong, use hint scaffolding (guide, don't give away the answer).\n"
                "3. Concise and encouraging in tone.\n\n"
                "You MUST respond with valid JSON and ONLY JSON:\n"
                '{"explanation": "Your improved explanation text..."}\n\n'
                "STRICT RULES:\n"
                "- Do NOT include 'is_correct', 'score', or 'verdict' in your response.\n"
                "- Do NOT suggest the verdict is wrong. It is final.\n"
                "- Return ONLY the JSON object. No preamble, no trailing text."
            ),
        )

    def run_for_qa(self, query: str, draft_answer: str, **kwargs) -> str:
        """
        Review a Q&A draft answer for quality and coherence (non-quiz pipeline).
        Returns the improved answer as a plain string.
        """
        prompt = (
            f"Query: {query}\n\n"
            f"Draft Answer:\n{draft_answer}\n\n"
            "Review for accuracy, clarity, and completeness. "
            "If the answer is good, return it unchanged. "
            "If it has issues, return an improved version. "
            "Return ONLY the final answer text, no commentary."
        )
        return super().run(prompt)

    def run(self, query: str, draft_answer: str, **kwargs) -> str:
        """
        Backwards-compatible alias: used by orchestrator for Q&A pipeline.
        Returns a plain string (the improved answer).
        """
        return self.run_for_qa(query, draft_answer)

    def improve_explanation(
        self,
        question: str,
        given_answer: str,
        correct_answer: str,
        verdict: str,
        score: float,
        draft_explanation: str,
    ) -> str:
        """
        Improve the explanation text for a LOCKED evaluation result.

        Returns only the improved explanation string.
        The locked verdict/score are passed as read-only context — they CANNOT be changed.
        """
        prompt = (
            f"Question: {question}\n"
            f"Student's Answer: {given_answer or '[No answer provided]'}\n"
            f"Correct Answer: {correct_answer}\n"
            f"Grading Verdict: {verdict} (score: {score}) — THIS IS LOCKED, DO NOT CHANGE IT.\n\n"
            f"Current Explanation:\n{draft_explanation}\n\n"
            "Improve the explanation if needed. "
            "If the verdict is INCORRECT/NO_ATTEMPT: use hint scaffolding, guide the student, don't just give the answer. "
            "If the verdict is CORRECT: briefly confirm why and optionally add an insight. "
            "Respond with JSON only: {\"explanation\": \"...\"}"
        )

        raw_response = super().run(prompt)

        try:
            data = _extract_json(raw_response)
            improved = str(data.get("explanation", "")).strip()
            return improved if improved else draft_explanation
        except Exception:
            # If parsing fails, fall back to original — never corrupt explanation
            return draft_explanation


checker_agent = CheckerAgent()
