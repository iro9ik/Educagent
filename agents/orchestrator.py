"""
Orchestrator Agent — central controller that routes requests to the appropriate pipeline.
"""

import time

from agents.base import BaseAgent, AgentTimeoutError, RateLimitError
from agents.rag_agent import rag_agent
from agents.search_agent import search_agent
from agents.thinking_agent import thinking_agent
from agents.fusion_agent import fusion_agent
from agents.explanation_agent import explanation_agent
from agents.checker_agent import checker_agent
from agents.quiz_agent import quiz_agent
from agents.evaluation_agent import evaluation_agent
from agents.memory_agent import memory_agent
from agents.feedback_agent import feedback_agent


class OrchestratorAgent(BaseAgent):
    """
    Central orchestrator that routes user requests based on intent and settings.

    Pipelines:
    - Question: RAG → (Search?) → Fusion → (Thinking?) → Explanation → Checker
    - Quiz: RAG → Quiz Agent
    - Evaluate: Evaluation → Memory → Feedback
    """

    def __init__(self):
        super().__init__(
            name="Orchestrator Agent",
            system_prompt=(
                "You are a request classifier. Classify the user's message into one of:\n"
                "- 'question': The user is asking a question or wants information\n"
                "- 'quiz': The user wants a quiz or to be tested\n"
                "- 'greeting': The user is greeting or making small talk\n\n"
                "Respond with ONLY one word: question, quiz, or greeting."
            ),
        )

    def classify_intent(self, message: str) -> str:
        """Classify user intent: question, quiz, or greeting."""
        raw = super().run(message).strip().lower()

        # Simple keyword matching as fallback
        quiz_keywords = ["quiz", "test me", "test my", "quiz me", "assess me", "questions"]
        if any(kw in message.lower() for kw in quiz_keywords):
            return "quiz"

        if raw in ("question", "quiz", "greeting"):
            return raw

        return "question"  # default

    def handle_question(
        self,
        query: str,
        search_enabled: bool = False,
        thinking_enabled: bool = False,
        history: str = "",
        allowed_sources: list[str] | None = None,
    ) -> dict:
        """
        Full question-answering pipeline.
        RAG → (Search?) → Fusion → (Thinking?) → Explanation → Checker
        """
        pipeline_log = []

        # Step 1: RAG retrieval
        pipeline_log.append("📚 RAG Agent: Retrieving relevant documents...")
        rag_result = rag_agent.run(query, allowed_sources=allowed_sources)
        rag_context = rag_result.get("context", "")
        sources = rag_result.get("sources", [])

        # Step 2: Search (optional)
        search_context = ""
        if search_enabled:
            pipeline_log.append("🔍 Search Agent: Searching the internet...")
            search_result = search_agent.run(query)
            search_context = search_result.get("summary", "")

        # Step 3: Fusion
        pipeline_log.append("🔗 Fusion Agent: Combining information sources...")
        fused_context = fusion_agent.run(
            query=query,
            rag_context=rag_context,
            search_context=search_context,
        )

        # Step 4: Thinking (optional)
        thinking_output = None
        if thinking_enabled:
            pipeline_log.append("🧠 Thinking Agent: Analyzing and reasoning...")
            thinking_output = thinking_agent.run(query=query, context=fused_context)
            final_context = f"{fused_context}\n\nAnalysis:\n{thinking_output}"
        else:
            final_context = fused_context

        # Step 5: Explanation
        pipeline_log.append("💡 Explanation Agent: Generating answer...")
        draft_answer = explanation_agent.run(
            query=query,
            context=final_context,
            history=history,
        )

        # Step 6: Checker (Q&A pipeline — reviews answer quality only, returns string)
        pipeline_log.append("✅ Checker Agent: Reviewing answer quality...")
        final_answer = checker_agent.run(query=query, draft_answer=draft_answer)

        return {
            "response": final_answer,
            "sources": sources,
            "thinking": thinking_output,
            "pipeline": pipeline_log,
        }

    def stream_question(
        self,
        query: str,
        search_enabled: bool = False,
        thinking_enabled: bool = False,
        history: str = "",
        allowed_sources: list[str] | None = None,
    ):
        """Stream chunks of the final answer."""
        # Step 1: RAG retrieval
        rag_result = rag_agent.run(query, allowed_sources=allowed_sources)
        rag_context = rag_result.get("context", "")

        # Step 2: Search (optional)
        search_context = ""
        if search_enabled:
            search_result = search_agent.run(query)
            search_context = search_result.get("summary", "")

        # Step 3: Fusion
        fused_context = fusion_agent.run(
            query=query,
            rag_context=rag_context,
            search_context=search_context,
        )

        # Step 4: Thinking (optional)
        thinking_output = None
        if thinking_enabled:
            thinking_output = thinking_agent.run(query=query, context=fused_context)
            final_context = f"{fused_context}\n\nAnalysis:\n{thinking_output}"
        else:
            final_context = fused_context

        # Step 5: Explanation (Streaming)
        # We skip the Checker for streaming to keep it responsive
        for chunk in explanation_agent.stream(
            query=query,
            context=final_context,
            history=history,
        ):
            yield chunk

    def stream_question_with_trace(
        self,
        query: str,
        search_enabled: bool = False,
        thinking_enabled: bool = False,
        history: str = "",
        allowed_sources: list[str] | None = None,
    ):
        """Yield structured events for the full agent pipeline."""
        # Step 1: RAG
        rag_context = ""
        sources = []
        if allowed_sources is None or len(allowed_sources) > 0:
            yield {"type": "agent_status", "agent": "rag", "status": "running", "label": "Reading the files..."}
            t0 = time.time()
            try:
                rag_result = rag_agent.run(query, allowed_sources=allowed_sources)
                rag_context = rag_result.get("context", "")
                sources = rag_result.get("sources", [])
                duration = int((time.time() - t0) * 1000)
                yield {"type": "agent_status", "agent": "rag", "status": "completed", "duration_ms": duration}
                if sources:
                    yield {"type": "sources", "files": sources}
            except (AgentTimeoutError, RateLimitError) as e:
                yield {"type": "agent_status", "agent": "rag", "status": "error", "detail": str(e)}
                yield {"type": "error", "error": str(e)}
                return
            except Exception as e:
                yield {"type": "agent_status", "agent": "rag", "status": "error", "detail": str(e)}
            
        # Step 2: Search (optional)
        search_context = ""
        if search_enabled:
            yield {"type": "agent_status", "agent": "search", "status": "running", "label": "Searching the web..."}
            t0 = time.time()
            try:
                search_result = search_agent.run(query)
                search_context = search_result.get("summary", "")
                duration = int((time.time() - t0) * 1000)
                yield {"type": "agent_status", "agent": "search", "status": "completed", "duration_ms": duration}
            except (AgentTimeoutError, RateLimitError) as e:
                yield {"type": "agent_status", "agent": "search", "status": "error", "detail": str(e)}
                yield {"type": "error", "error": str(e)}
                return
            except Exception as e:
                yield {"type": "agent_status", "agent": "search", "status": "error", "detail": str(e)}

        # Step 3: Fusion
        yield {"type": "agent_status", "agent": "fusion", "status": "running", "label": "Combining sources..."}
        t0 = time.time()
        try:
            fused_context = fusion_agent.run(
                query=query,
                rag_context=rag_context,
                search_context=search_context,
            )
            duration = int((time.time() - t0) * 1000)
            yield {"type": "agent_status", "agent": "fusion", "status": "completed", "duration_ms": duration}
        except (AgentTimeoutError, RateLimitError) as e:
            yield {"type": "agent_status", "agent": "fusion", "status": "error", "detail": str(e)}
            yield {"type": "error", "error": str(e)}
            return
        except Exception as e:
            yield {"type": "agent_status", "agent": "fusion", "status": "error", "detail": str(e)}
            fused_context = f"{rag_context}\n\n{search_context}"

        # Step 4: Thinking (optional)
        final_context = fused_context
        if thinking_enabled:
            yield {"type": "agent_status", "agent": "thinking", "status": "running", "label": "Analyzing and reasoning..."}
            t0 = time.time()
            try:
                thinking_output = thinking_agent.run(query=query, context=fused_context)
                duration = int((time.time() - t0) * 1000)
                yield {"type": "reasoning", "content": thinking_output}
                yield {"type": "agent_status", "agent": "thinking", "status": "completed", "duration_ms": duration}
                final_context = f"{fused_context}\n\nAnalysis:\n{thinking_output}"
            except (AgentTimeoutError, RateLimitError) as e:
                yield {"type": "agent_status", "agent": "thinking", "status": "error", "detail": str(e)}
                yield {"type": "error", "error": str(e)}
                return
            except Exception as e:
                yield {"type": "agent_status", "agent": "thinking", "status": "error", "detail": str(e)}

        # Step 5: Explanation (Streaming)
        yield {"type": "agent_status", "agent": "explanation", "status": "running", "label": "Generating response..."}
        try:
            for chunk in explanation_agent.stream(
                query=query,
                context=final_context,
                history=history,
            ):
                yield {"type": "token", "chunk": chunk}
            yield {"type": "agent_status", "agent": "explanation", "status": "completed"}
        except (AgentTimeoutError, RateLimitError) as e:
            yield {"type": "agent_status", "agent": "explanation", "status": "error", "detail": str(e)}
            yield {"type": "error", "error": str(e)}
            return
        except Exception as e:
            yield {"type": "agent_status", "agent": "explanation", "status": "error", "detail": str(e)}
            yield {"type": "error", "error": str(e)}

    def handle_quiz(
        self,
        topic: str = "general",
        num_questions: int = 5,
        allowed_sources: list[str] | None = None,
    ) -> dict:
        """
        Quiz generation pipeline.
        RAG → Quiz Agent
        """
        return quiz_agent.run(
            topic=topic,
            num_questions=num_questions,
            allowed_sources=allowed_sources,
        )

    def handle_evaluation(
        self,
        user_id: str,
        answers: list[dict],
    ) -> dict:
        """
        Hardened 3-layer evaluation pipeline.

        Layer 1 — VALIDATION + EVALUATION (EvaluationAgent)
          Fails fast if any correct_answer is missing.
          Returns locked {verdict, score, is_correct} per question.

        Layer 2 — EXPLANATION (CheckerAgent, read-only)
          May only improve explanation text.
          Cannot modify verdict, score, or is_correct.

        Layer 3 — PRESENTATION (this method)
          Builds the final markdown feedback from locked results.

        Returns dict with status='FAILED_VALIDATION' if validation fails,
        or full result dict on success.
        """
        # ── Layer 1: Validate + Evaluate (DECISION LOCK) ──────────────────
        eval_result = evaluation_agent.run(answers=answers)

        # Hard stop on validation failure — propagate up to route handler
        if eval_result["status"] == "FAILED_VALIDATION":
            return eval_result

        evaluations = eval_result["evaluations"]   # contains locked verdict/score
        summary = eval_result["summary"] or ""
        recommendations = eval_result["recommendations"]
        total_score = eval_result["total_score"]
        max_score = eval_result["max_score"]
        percentage = eval_result["percentage"]

        # ── Layer 2: Improve explanations (EXPLANATION ONLY, scores immutable) ──
        for eval_item, ans in zip(evaluations, answers):
            improved = checker_agent.improve_explanation(
                question=ans["question"],
                given_answer=ans["given_answer"],
                correct_answer=ans["correct_answer"],
                verdict=eval_item["verdict"],      # read-only
                score=eval_item["score"],          # read-only
                draft_explanation=eval_item["explanation"],
            )
            # Only update explanation — verdict/score/is_correct are untouched
            eval_item["explanation"] = improved

        # ── Layer 3: Store mistakes in memory ────────────────────────────
        memory_result = memory_agent.run(
            user_id=user_id,
            evaluations=evaluations,
            answers=answers,
        )

        # ── Layer 3: Build markdown feedback (PRESENTATION) ──────────────
        feedback_md = f"{summary}\n\n"
        feedback_md += "### 📝 Per-Question Feedback\n\n"

        for i, (eval_item, ans) in enumerate(zip(evaluations, answers), 1):
            verdict = eval_item["verdict"]
            score = eval_item["score"]
            is_correct = eval_item["is_correct"]

            if verdict == "CORRECT":
                icon = "✅"
            elif verdict == "PARTIAL":
                icon = "⚠️"
            elif verdict == "NO_ATTEMPT":
                icon = "⬜"
            else:
                icon = "❌"

            q_text = str(ans["question"]).strip().strip("* ")
            feedback_md += f"### Q{i}. {q_text}\n\n"
            feedback_md += f"**Your Answer:** {ans['given_answer'] or '*No answer provided*'} {icon}\n"

            if not is_correct and score < 1.0:
                # correct_answer is guaranteed non-empty by the validation gate
                feedback_md += f"**Correct Answer:** {ans['correct_answer']} ✅\n"

            feedback_md += f"\n**Explanation:** {eval_item['explanation']}\n\n"

        if recommendations:
            feedback_md += "### 📚 Study Recommendations\n"
            for rec in recommendations:
                # Recommendations are guaranteed to be plain strings by evaluation_agent
                feedback_md += f"- {rec}\n"
            feedback_md += "\n"

        return {
            "status": "SUCCESS",
            "total_score": round(total_score, 2),
            "max_score": max_score,
            "percentage": round(percentage, 1),
            "evaluations": evaluations,
            "feedback": feedback_md.strip(),
            "weak_topics": memory_result.get("weak_topics", {}),
        }

    def handle_feedback(self, user_id: str) -> dict:
        """Get personalized feedback for a user."""
        return feedback_agent.run(user_id=user_id)


# Singleton instance
orchestrator = OrchestratorAgent()
