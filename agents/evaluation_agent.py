"""
Evaluation Agent — evaluates user answers and assigns scores.
"""

import json

from agents.base import BaseAgent


class EvaluationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Evaluation Agent",
            system_prompt=(
                "You are an answer evaluation specialist. Your job is to:\n"
                "1. Compare the student's answer to the correct answer\n"
                "2. Determine if the answer is correct, partially correct, or incorrect\n"
                "3. Assign a score (0.0 to 1.0)\n"
                "4. Provide a brief explanation of why the score was given\n"
                "5. Identify the topic area of each question\n\n"
                "You MUST respond with valid JSON. Format:\n"
                '{"evaluations": [\n'
                '  {"is_correct": true/false, "score": 0.0-1.0, "explanation": "...", "topic": "..."}\n'
                "]}"
            ),
        )

    def run(self, answers: list[dict], **kwargs) -> list[dict]:
        """
        Evaluate a list of answer submissions.
        Each answer: {question, given_answer, correct_answer}
        Returns list of evaluations.
        """
        if not answers:
            return []

        answers_text = "\n".join(
            f"Q{i+1}: {a['question']}\n"
            f"  Student's Answer: {a['given_answer']}\n"
            f"  Correct Answer: {a['correct_answer']}\n"
            for i, a in enumerate(answers)
        )

        prompt = (
            f"Evaluate these {len(answers)} student answers:\n\n"
            f"{answers_text}\n\n"
            "For each question, determine correctness, assign a score (0.0-1.0), "
            "provide an explanation, and identify the topic. "
            "Respond with valid JSON only."
        )

        raw_response = super().run(prompt)

        # Parse JSON
        try:
            response_text = raw_response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            data = json.loads(response_text)
            evaluations = data.get("evaluations", [])

            # Ensure we have the right number of evaluations
            while len(evaluations) < len(answers):
                evaluations.append({
                    "is_correct": False,
                    "score": 0.0,
                    "explanation": "Could not evaluate this answer.",
                    "topic": "unknown",
                })

            return evaluations[:len(answers)]

        except (json.JSONDecodeError, IndexError):
            # Fallback: simple string matching
            return [
                {
                    "is_correct": a["given_answer"].strip().lower() == a["correct_answer"].strip().lower(),
                    "score": 1.0 if a["given_answer"].strip().lower() == a["correct_answer"].strip().lower() else 0.0,
                    "explanation": raw_response[:200] if raw_response else "Evaluation failed.",
                    "topic": "unknown",
                }
                for a in answers
            ]


evaluation_agent = EvaluationAgent()
