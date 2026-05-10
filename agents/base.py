"""
Base Agent — shared foundation for all agents.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import queue
import threading

import config


class AgentTimeoutError(Exception):
    """Raised when an agent exceeds its time limit."""
    pass

class RateLimitError(Exception):
    """Raised when the provider returns 429."""
    pass

class BaseAgent:
    """
    Base class for all EducAgent agents.
    Each agent has a role, a system prompt, and uses the shared LLM.
    """
    TIMEOUT_SECONDS = 300  # Max time for any single agent call

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt

    @property
    def llm(self):
        """Dynamically return the current LLM from config."""
        return config.config.llm

    def run(self, user_input: str, **kwargs) -> str:
        """
        Run the agent with the given input and timeout protection.
        """
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temporal_prompt = f"{self.system_prompt}\n\nCurrent Date and Time: {now}"
        messages = [
            SystemMessage(content=temporal_prompt),
            HumanMessage(content=user_input),
        ]

        try:
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(
                lambda: self.llm.invoke(messages, config={"timeout": self.TIMEOUT_SECONDS})
            )
            try:
                response = future.result(timeout=self.TIMEOUT_SECONDS)
            except FutureTimeoutError:
                future.cancel()
                raise AgentTimeoutError(f"{self.name}: Timed out after {self.TIMEOUT_SECONDS}s")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            return self._clean_response(response.content)
        except Exception as e:
            raise self._normalize_error(e)

    def stream(self, user_input: str, **kwargs):
        """Stream chunks of the response with timeout on first chunk."""
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temporal_prompt = f"{self.system_prompt}\n\nCurrent Date and Time: {now}"
        messages = [
            SystemMessage(content=temporal_prompt),
            HumanMessage(content=user_input),
        ]

        chunk_queue: queue.Queue = queue.Queue()

        def read_stream():
            try:
                for chunk in self.llm.stream(messages, config={"timeout": self.TIMEOUT_SECONDS}):
                    chunk_queue.put(chunk.content)
            except Exception as exc:
                chunk_queue.put(exc)
            finally:
                chunk_queue.put(None)

        thread = threading.Thread(target=read_stream, daemon=True)
        thread.start()

        first_chunk_received = False
        try:
            while True:
                try:
                    item = chunk_queue.get(timeout=self.TIMEOUT_SECONDS)
                except queue.Empty:
                    if first_chunk_received:
                        raise AgentTimeoutError(f"{self.name}: Stream stalled for {self.TIMEOUT_SECONDS}s")
                    raise AgentTimeoutError(f"{self.name}: No response from provider within {self.TIMEOUT_SECONDS}s")

                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item

                first_chunk_received = True
                yield item
        except Exception as e:
            raise self._normalize_error(e, first_chunk_received=first_chunk_received)

    def _clean_response(self, text: str) -> str:
        """Remove thinking tags if present (Qwen3 thinking mode)."""
        import re
        # Remove <think>...</think> blocks from Qwen3 output
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return cleaned.strip()

    def _normalize_error(self, error: Exception, first_chunk_received: bool = True) -> Exception:
        if isinstance(error, (AgentTimeoutError, RateLimitError)):
            return error

        error_str = str(error)
        
        # Try to extract more details if it's an API error
        if hasattr(error, "response") and hasattr(error.response, "text"):
            error_str += f" | {error.response.text}"
        elif hasattr(error, "body"):
            error_str += f" | {error.body}"

        error_str_lower = error_str.lower()
        if "429" in error_str_lower or "rate limit" in error_str_lower or "rate limited" in error_str_lower:
            return RateLimitError(f"{self.name}: Rate limited by provider. ({error_str})")
        if "connection error" in error_str_lower or "connecterror" in error_str_lower or "connection refused" in error_str_lower:
            return ConnectionError(
                f"{self.name}: Could not connect to the configured model provider. "
                "Check the API base URL, API key, and model name. "
                f"Details: {error_str}"
            )
        if "timeout" in error_str_lower or "timed out" in error_str_lower:
            if first_chunk_received:
                return AgentTimeoutError(f"{self.name}: Timed out after {self.TIMEOUT_SECONDS}s. Details: {error_str}")
            return AgentTimeoutError(f"{self.name}: No response from provider within {self.TIMEOUT_SECONDS}s. Details: {error_str}")
        
        # Return a standard Exception with the enhanced error string
        return Exception(f"{self.name} Error: {error_str}")

    def __repr__(self):
        return f"<{self.__class__.__name__}(name={self.name!r})>"
