"""
Quiz Agent — generates quiz questions from indexed content.

QUIZ SCHEMA VALIDITY GATE
--------------------------
Every question returned by this agent MUST satisfy ALL of the following:
  1. 'question' is a non-empty string
  2. 'answer' is a non-empty string
  3. 'question_type' is one of: 'mcq', 'open_ended'
  4. For MCQ: 'options' is a list of 2–6 non-empty strings
  5. For MCQ: 'answer' must be one of the option strings (or a valid prefix letter)

Any question that fails validation is DROPPED.
If 0 valid questions remain, the agent returns an error — it does NOT return a partial
or malformed quiz.
"""

import json
import re

from agents.base import BaseAgent
from agents.rag_agent import rag_agent

# ─── Validation helpers ────────────────────────────────────────────────────

VALID_QUESTION_TYPES = {"mcq", "open_ended"}


class QuizValidationError(Exception):
    """Raised when the LLM output cannot produce a valid quiz."""
    pass


def _validate_question(q: dict, index: int) -> tuple[bool, str]:
    """
    Validate a single question dict.
    Returns (is_valid, reason_if_invalid).
    """
    if not isinstance(q, dict):
        return False, f"Q{index+1}: not a dict"

    question_text = str(q.get("question", "")).strip()
    answer_text = str(q.get("correct_answer", "")).strip()
    q_type = str(q.get("question_type", "")).strip().lower()

    if not question_text:
        return False, f"Q{index+1}: 'question' is empty"

    if not answer_text:
        return False, f"Q{index+1}: 'correct_answer' is empty — cannot grade without a correct answer"

    if q_type not in VALID_QUESTION_TYPES:
        # Be lenient: treat unknown type as open_ended rather than dropping it
        q["question_type"] = "open_ended"
        q_type = "open_ended"

    if q_type == "mcq":
        options = q.get("options")
        if not isinstance(options, list) or len(options) < 2:
            return False, f"Q{index+1}: MCQ must have at least 2 options, got {options!r}"
        # Ensure all options are non-empty strings
        cleaned_options = [str(o).strip() for o in options if str(o).strip()]
        if len(cleaned_options) < 2:
            return False, f"Q{index+1}: MCQ has fewer than 2 non-empty options after cleaning"
        q["options"] = cleaned_options
        # Normalize answer: it must be one of the options (exact match)
        # Some LLMs return "A", "B", etc. — expand those to the actual option text
        if answer_text not in cleaned_options:
            # Try single-letter mapping: "A" → options[0], "B" → options[1], etc.
            letter_map = {chr(65 + i): opt for i, opt in enumerate(cleaned_options)}
            resolved = letter_map.get(answer_text.upper())
            if resolved:
                q["correct_answer"] = resolved
            else:
                # Last resort: check if any option starts with the answer letter
                # If still not resolvable, drop the question
                return False, (
                    f"Q{index+1}: MCQ answer '{answer_text}' is not in options {cleaned_options} "
                    "and cannot be resolved from letter mapping"
                )

    return True, ""


def _validate_quiz(data: dict, topic: str) -> dict:
    """
    Validate the full quiz dict produced by the LLM.

    Returns a clean dict with only valid questions.
    Raises QuizValidationError if 0 valid questions remain.
    """
    if not isinstance(data, dict):
        raise QuizValidationError("LLM output is not a JSON object")

    raw_questions = data.get("questions", [])
    if not isinstance(raw_questions, list):
        raise QuizValidationError("'questions' field is not a list")

    valid_questions = []
    drop_reasons = []

    for i, q in enumerate(raw_questions):
        # Deep-copy so we can mutate (normalize options/answer) safely
        q_copy = dict(q) if isinstance(q, dict) else {}
        is_valid, reason = _validate_question(q_copy, i)
        if is_valid:
            valid_questions.append(q_copy)
        else:
            drop_reasons.append(reason)

    if not valid_questions:
        raise QuizValidationError(
            f"Quiz schema validation failed — 0 valid questions out of "
            f"{len(raw_questions)} generated. Reasons: {'; '.join(drop_reasons)}"
        )

    return {
        "topic": str(data.get("topic", topic)).strip() or topic,
        "questions": valid_questions,
        "_dropped": drop_reasons,  # surfaced for logging; stripped by routes.py
    }


def _extract_json(raw: str) -> dict:
    """Robustly extract the first JSON object from raw LLM output."""
    text = raw.strip()

    # Strip markdown code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Find the outermost { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    return json.loads(text)


# ─── Agent ────────────────────────────────────────────────────────────────

class QuizAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Quiz Agent",
            system_prompt=(
                "You are a quiz generator for educational content.\n\n"
                "OUTPUT FORMAT — respond with ONLY valid JSON, nothing else:\n"
                '{"topic": "...", "questions": [\n'
                '  {"question": "...", "options": ["A. Option text", "B. Option text", "C. Option text", "D. Option text"], '
                '"correct_answer": "A. Option text", "question_type": "mcq"},\n'
                '  {"question": "...", "options": null, "correct_answer": "Full correct answer text", "question_type": "open_ended"}\n'
                "]}\n\n"
                "STRICT RULES:\n"
                "1. Every question MUST have a non-empty 'correct_answer' field — this is the ground truth for grading.\n"
                "2. For MCQ: 'correct_answer' MUST be the full text of one of the options, not just the letter.\n"
                "3. For MCQ: provide exactly 4 options as full strings (e.g. 'A. Paris', not just 'Paris').\n"
                "4. For open_ended: 'options' must be null.\n"
                "5. Do NOT leave 'correct_answer' empty, null, or as a placeholder.\n"
                "6. Test understanding, not just memorization.\n"
                "7. Respond with valid JSON ONLY. No explanations, no preamble, no trailing text."
            ),
        )

    def run(self, topic: str = "general", num_questions: int = 5, **kwargs) -> dict:
        """
        Generate quiz questions from RAG content.

        Returns a validated quiz dict:
          {"topic": str, "questions": [...], "error": None}

        Or on failure:
          {"topic": str, "questions": [], "error": "<reason>"}
        """
        allowed_sources = kwargs.get("allowed_sources")
        rag_result = rag_agent.run(topic, top_k=8, allowed_sources=allowed_sources)
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
            f"Rules:\n"
            f"- Generate exactly {num_questions} questions (mix of MCQ and open_ended).\n"
            f"- For MCQ: 'correct_answer' MUST be the full option text (e.g. 'A. Paris'), NOT just 'A'.\n"
            f"- Every question MUST have a non-empty 'correct_answer'.\n"
            f"Respond with valid JSON ONLY."
        )

        raw_response = super().run(prompt)

        # ── Parse ────────────────────────────────────────────────────────
        try:
            data = _extract_json(raw_response)
        except (json.JSONDecodeError, IndexError, AttributeError) as exc:
            return {
                "topic": topic,
                "questions": [],
                "error": f"Failed to parse quiz JSON from LLM response: {exc}",
            }

        # ── Validate (schema gate) ────────────────────────────────────────
        try:
            validated = _validate_quiz(data, topic)
        except QuizValidationError as exc:
            return {
                "topic": topic,
                "questions": [],
                "error": str(exc),
            }

        dropped = validated.pop("_dropped", [])
        if dropped:
            # Log silently — caller does not see dropped reasons unless debugging
            print(f"[QuizAgent] Dropped {len(dropped)} invalid question(s): {dropped}")

        return validated


quiz_agent = QuizAgent()
