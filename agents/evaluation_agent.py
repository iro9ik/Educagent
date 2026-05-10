"""
Evaluation Agent — deterministic, decision-locked quiz grading.

PIPELINE CONTRACT
-----------------
Layer 1 (this agent): EVALUATION
  - Validates inputs: ALL questions must have a non-empty correct_answer.
    If ANY correct_answer is missing → return FAILED_VALIDATION immediately.
    No LLM call. No score. No explanation.
  - Calls the LLM to compare user answers to the ground truth.
  - Returns locked {verdict, score} per question.
  - These values are IMMUTABLE — no downstream agent may modify them.

Layer 2 (checker_agent): EXPLANATION ONLY
  - Receives locked verdicts/scores as read-only context.
  - May only improve explanation text.
  - Cannot change is_correct or score.

Layer 3 (orchestrator): PRESENTATION
  - Builds markdown from locked results + explanations.
"""

import json
import re

from agents.base import BaseAgent

# Status constants
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED_VALIDATION = "FAILED_VALIDATION"

# Verdict constants — immutable once set
VERDICT_CORRECT = "CORRECT"
VERDICT_INCORRECT = "INCORRECT"
VERDICT_PARTIAL = "PARTIAL"
VERDICT_NO_ATTEMPT = "NO_ATTEMPT"


def _validate_answers(answers: list[dict]) -> tuple[bool, str]:
    """
    Hard validation gate.
    Returns (passed, reason_if_failed).
    Fails fast on the FIRST missing correct_answer.
    """
    for i, a in enumerate(answers):
        correct = str(a.get("correct_answer", "") or "").strip()
        if not correct:
            return False, f"Missing answer key for question {i + 1}: '{a.get('question', '?')}'"
    return True, ""


def _parse_verdict(is_correct: bool, score: float) -> str:
    """Convert LLM is_correct/score into an immutable verdict string."""
    if score <= 0.0:
        given = str(is_correct)
        # Treat explicit False or score=0 as INCORRECT,
        # but distinguish NO_ATTEMPT by checking the caller context
        return VERDICT_INCORRECT
    if score >= 1.0:
        return VERDICT_CORRECT
    return VERDICT_PARTIAL


def _extract_json(raw: str) -> dict:
    """Robustly extract the first JSON object from raw LLM output."""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


class EvaluationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Evaluation Agent",
            system_prompt=(
                "You are an expert educational evaluator. Your job is to compare student answers to correct answers and assign verdicts.\n\n"
                "You MUST respond with valid JSON in this exact format:\n"
                "{\n"
                '  "summary": "Honest, encouraging summary speaking DIRECTLY to the user (e.g. \'You struggled with...\', \'Great job on...\').",\n'
                '  "evaluations": [\n'
                "    {\n"
                '      "reasoning": "Step-by-step comparison of the student\'s answer to the Correct Answer.",\n'
                '      "is_correct": true,\n'
                '      "score": 1.0,\n'
                '      "explanation": "Why it is correct, or hint scaffolding if incorrect. Never just give away the answer.",\n'
                '      "topic": "Subject area of this question"\n'
                "    }\n"
                "  ],\n"
                '  "recommendations": [\n'
                '    "Topic: What to review - How to practice"\n'
                "  ]\n"
                "}\n\n"
                "STRICT RULES:\n"
                "1. TRUTH SOURCE: 'Correct Answer' is the absolute truth. Evaluate ONLY against it.\n"
                "2. DECISION LOCKING: Write 'reasoning' FIRST. Then set 'is_correct' and 'score' to match your reasoning. They must be consistent.\n"
                "3. SCORE VALUES: 1.0 = fully correct, 0.5 = partially correct, 0.0 = incorrect or no attempt.\n"
                "4. If answer is empty/blank/'idk': score=0.0, is_correct=false. Provide encouraging hint scaffolding.\n"
                "5. If correct: briefly explain WHY and optionally add an insight.\n"
                "6. If incorrect: explain WHY based on the Correct Answer. Use hint scaffolding — do NOT just state the answer.\n"
                "7. RECOMMENDATIONS: 3 max. Only for concepts the student got wrong. Never for mastered concepts.\n"
                "8. SPEAK DIRECTLY to the user ('You', not 'The student').\n"
                "9. Return ONLY the JSON object. No preamble, no trailing text."
            ),
        )

    def run(self, answers: list[dict], custom_prompt: str = None, **kwargs) -> dict:
        """
        Evaluate a list of answer submissions.

        Input:  [{"question": str, "given_answer": str, "correct_answer": str}, ...]

        Output (SUCCESS):
          {
            "status": "SUCCESS",
            "reason": None,
            "evaluations": [{
                "question_id": int,
                "verdict": "CORRECT"|"INCORRECT"|"PARTIAL"|"NO_ATTEMPT",
                "is_correct": bool,
                "score": float,
                "explanation": str,
                "topic": str,
                "reasoning": str,
            }],
            "summary": str,
            "recommendations": list[str],
            "total_score": float,
            "max_score": float,
            "percentage": float,
          }

        Output (FAILED_VALIDATION):
          {
            "status": "FAILED_VALIDATION",
            "reason": "Missing answer key for question X",
            "evaluations": [],
            "summary": None,
            "recommendations": [],
            "total_score": 0,
            "max_score": 0,
            "percentage": 0,
          }
        """
        # ── Guard: empty answers ──────────────────────────────────────────
        if not answers:
            return {
                "status": STATUS_FAILED_VALIDATION,
                "reason": "No answers submitted",
                "evaluations": [],
                "summary": None,
                "recommendations": [],
                "total_score": 0,
                "max_score": 0,
                "percentage": 0,
            }

        # ── HARD VALIDATION GATE ──────────────────────────────────────────
        passed, reason = _validate_answers(answers)
        if not passed:
            return {
                "status": STATUS_FAILED_VALIDATION,
                "reason": reason,
                "evaluations": [],
                "summary": None,
                "recommendations": [],
                "total_score": 0,
                "max_score": 0,
                "percentage": 0,
            }

        # ── Build prompt ──────────────────────────────────────────────────
        answers_text = "\n".join(
            f"Q{i+1}: {a['question']}\n"
            f"  Student's Answer: {a['given_answer'] or '[No answer provided]'}\n"
            f"  Correct Answer: {a['correct_answer']}\n"
            for i, a in enumerate(answers)
        )

        if not custom_prompt:
            prompt = (
                f"Evaluate these {len(answers)} student answers:\n\n"
                f"{answers_text}\n\n"
                f"STRICT REQUIREMENT: You MUST provide exactly {len(answers)} evaluations in the 'evaluations' list, one for each question (Q1 to Q{len(answers)}).\n"
                "Analyze each answer carefully. Write reasoning first, then assign is_correct and score. "
                "Provide a summary, per-question evaluations, and targeted study recommendations ONLY for mistakes. "
                "Respond with valid JSON ONLY. No preamble or trailing text."
            )
        else:
            prompt = custom_prompt

        raw_response = super().run(prompt)
        
        # Log for debugging (visible in uvicorn terminal)
        print(f"\n[EvaluationAgent] Raw LLM Response:\n{raw_response}\n")

        # ── Parse LLM response ────────────────────────────────────────────
        try:
            data = _extract_json(raw_response)
        except (json.JSONDecodeError, IndexError, AttributeError, ValueError) as exc:
            # HARD FAIL: do not guess scores, do not fallback
            return {
                "status": STATUS_FAILED_VALIDATION,
                "reason": f"Evaluation agent returned unparseable output: {exc}",
                "evaluations": [],
                "summary": None,
                "recommendations": [],
                "total_score": 0,
                "max_score": 0,
                "percentage": 0,
            }

        raw_evals = data.get("evaluations", [])
        
        # Handle cases where LLM returns a dictionary of evaluations instead of a list
        if isinstance(raw_evals, dict):
            try:
                sorted_keys = sorted(raw_evals.keys(), key=lambda x: int(re.search(r"\d+", str(x)).group()))
                raw_evals = [raw_evals[k] for k in sorted_keys]
            except (ValueError, AttributeError, TypeError):
                raw_evals = list(raw_evals.values())

        # --- RETRY LOGIC for mismatch ---
        if len(raw_evals) != len(answers) and kwargs.get("_is_retry") is not True:
            print(f"[EvaluationAgent] Mismatch detected ({len(raw_evals)} vs {len(answers)}). Retrying...")
            # Use the original prompt as base, but add the error correction
            base_prompt = prompt if not custom_prompt else custom_prompt
            retry_prompt = (
                f"{base_prompt}\n\n"
                f"CRITICAL ERROR IN PREVIOUS RESPONSE: You only provided {len(raw_evals)} evaluations, but I need EXACTLY {len(answers)}. "
                f"DO NOT SKIP ANY QUESTIONS. Evaluate Q1 through Q{len(answers)}."
            )
            return self.run(answers, custom_prompt=retry_prompt, _is_retry=True, **kwargs)

        if len(raw_evals) != len(answers):
            # Mismatch: safer to fail than to silently misalign answers
            return {
                "status": STATUS_FAILED_VALIDATION,
                "reason": (
                    f"Evaluation agent returned {len(raw_evals)} evaluations "
                    f"for {len(answers)} questions — mismatch rejected. "
                    "Please try submitting again."
                ),
                "evaluations": [],
                "summary": None,
                "recommendations": [],
                "total_score": 0,
                "max_score": 0,
                "percentage": 0,
            }

        # ── Lock evaluations ──────────────────────────────────────────────
        locked_evaluations = []
        total_score = 0.0

        for i, (raw_eval, ans) in enumerate(zip(raw_evals, answers)):
            is_correct = bool(raw_eval.get("is_correct", False))
            score = float(raw_eval.get("score", 0.0))
            score = max(0.0, min(1.0, score))  # clamp to [0, 1]

            # Enforce logical consistency: is_correct must match score
            if is_correct and score < 0.5:
                # Reasoning says correct but score says wrong — trust score
                is_correct = False
            if not is_correct and score >= 1.0:
                # Reasoning says wrong but score says perfect — trust is_correct
                score = 0.0

            # Determine verdict
            given = str(ans.get("given_answer", "")).strip().lower()
            if not given or given in ("", "idk", "i don't know", "no answer"):
                verdict = VERDICT_NO_ATTEMPT
                is_correct = False
                score = 0.0
            else:
                verdict = _parse_verdict(is_correct, score)

            total_score += score

            locked_evaluations.append({
                "question_id": i,
                "verdict": verdict,          # IMMUTABLE
                "is_correct": is_correct,    # IMMUTABLE
                "score": score,              # IMMUTABLE
                "explanation": str(raw_eval.get("explanation", "")).strip(),
                "topic": str(raw_eval.get("topic", "general")).strip(),
                "reasoning": str(raw_eval.get("reasoning", "")).strip(),
            })

        max_score = float(len(answers))
        percentage = round((total_score / max_score) * 100, 1) if max_score > 0 else 0.0

        # ── Normalize recommendations ─────────────────────────────────────
        raw_recs = data.get("recommendations", [])
        recommendations = [
            str(r).strip() for r in raw_recs
            if isinstance(r, str) and str(r).strip()
        ][:3]  # cap at 3

        return {
            "status": STATUS_SUCCESS,
            "reason": None,
            "evaluations": locked_evaluations,
            "summary": str(data.get("summary", "")).strip(),
            "recommendations": recommendations,
            "total_score": round(total_score, 2),
            "max_score": max_score,
            "percentage": percentage,
        }


evaluation_agent = EvaluationAgent()
