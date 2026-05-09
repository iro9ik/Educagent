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
            # Use thinking output as enhanced context
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

        # Step 6: Checker
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
        if allowed_sources:
            yield {"type": "agent_status", "agent": "rag", "status": "running", "label": "Reading chat files..."}
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
        Evaluation pipeline.
        Evaluation → Memory → Feedback
        """
        # Step 1: Evaluate answers
        evaluations = evaluation_agent.run(answers=answers)

        # Step 2: Store mistakes in memory
        memory_result = memory_agent.run(
            user_id=user_id,
            evaluations=evaluations,
            answers=answers,
        )

        # Step 3: Generate feedback
        feedback_result = feedback_agent.run(user_id=user_id)

        # Compute scores
        total_score = sum(e.get("score", 0) for e in evaluations)
        max_score = float(len(answers))
        percentage = (total_score / max_score * 100) if max_score > 0 else 0

        return {
            "total_score": round(total_score, 2),
            "max_score": max_score,
            "percentage": round(percentage, 1),
            "evaluations": evaluations,
            "feedback": feedback_result.get("summary", ""),
            "weak_topics": memory_result.get("weak_topics", {}),
        }

    def handle_feedback(self, user_id: str) -> dict:
        """Get personalized feedback for a user."""
        return feedback_agent.run(user_id=user_id)


# Singleton instance
orchestrator = OrchestratorAgent()
