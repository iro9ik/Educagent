"""
Generation Manager — abstract task layer for AI generation lifecycle.

This module provides:
1. GenerationManager: Abstract base class defining the generation interface
2. AsyncioGenerationManager: Implementation using asyncio background tasks + Redis
3. InMemoryFallback: Fallback when Redis is unavailable

The abstraction ensures the architecture can later migrate to:
- Celery workers
- Redis Queue (RQ)
- Temporal workflows
- Kubernetes job workers
without rewriting application logic.

IMPORTANT: Pure asyncio tasks are process-local. If the FastAPI process restarts,
active generations are lost. The Redis state allows detection of orphaned generations.
For production at scale, swap AsyncioGenerationManager for a distributed implementation.
"""

import asyncio
import uuid
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Callable, Any
from dataclasses import dataclass, field

from api.redis_client import redis_client
from chat.manager import chat_manager


@dataclass
class GenerationResult:
    """Result returned when starting a generation."""
    generation_id: str
    message_id: str
    chat_id: str


class GenerationManager(ABC):
    """
    Abstract base for generation lifecycle management.

    Implementations must handle:
    - Starting generation as a background process
    - Streaming chunks to subscribers
    - Stopping generation on demand
    - Persisting final content to the database
    - Cleaning up resources
    """

    @abstractmethod
    async def start_generation(
        self,
        chat_id: str,
        user_message: str,
        search_enabled: bool = False,
        thinking_enabled: bool = False,
        attached_files: Optional[list[str]] = None,
    ) -> GenerationResult:
        """
        Start an AI generation for a chat.

        1. Save user message to DB
        2. Create placeholder assistant message (status=streaming)
        3. Launch background generation task
        4. Return immediately with generation metadata
        """
        ...

    @abstractmethod
    async def stop_generation(self, generation_id: str) -> bool:
        """
        Stop an active generation.

        1. Signal the generation task to cancel
        2. Save partial content to DB
        3. Update status to 'stopped'
        4. Return True if successfully stopped
        """
        ...

    @abstractmethod
    async def get_active_generation(self, chat_id: str) -> Optional[dict]:
        """
        Check if a chat has an active generation.

        Returns dict with generation_id, message_id, status, seq
        or None if no active generation.
        """
        ...

    @abstractmethod
    async def get_generation_state(self, generation_id: str) -> Optional[dict]:
        """Get the current state of a specific generation."""
        ...

    @abstractmethod
    async def cleanup(self):
        """Clean up resources on shutdown."""
        ...


# ─── In-memory fallback for when Redis is not available ──────────────

@dataclass
class InMemoryGeneration:
    """Tracks a single generation in memory."""
    generation_id: str
    chat_id: str
    message_id: str
    status: str = "streaming"  # streaming | completed | stopped | failed
    chunks: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    trace_events: list[dict] = field(default_factory=list)
    full_content: str = ""
    seq: int = 0
    reasoning: str = ""
    sources: list[str] = field(default_factory=list)
    agent_steps: list[dict] = field(default_factory=list)
    error: str = ""
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    new_chunk_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: Optional[asyncio.Task] = None
    created_at: str = ""


class AsyncioGenerationManager(GenerationManager):
    """
    Generation manager using asyncio background tasks + Redis shared state.

    Falls back to in-memory dicts if Redis is unavailable.
    """

    def __init__(self):
        self._generations: dict[str, InMemoryGeneration] = {}
        self._chat_to_gen: dict[str, str] = {}  # chat_id -> generation_id
        self._lock = asyncio.Lock()

    async def start_generation(
        self,
        chat_id: str,
        user_message: str,
        search_enabled: bool = False,
        thinking_enabled: bool = False,
        attached_files: Optional[list[str]] = None,
    ) -> GenerationResult:
        generation_id = uuid.uuid4().hex[:16]

        # Save user message to DB
        chat_manager.add_message(
            chat_id,
            "user",
            user_message,
            attached_files=attached_files or [],
        )

        # Create placeholder assistant message
        msg_result = chat_manager.create_placeholder_message(
            chat_id=chat_id,
            generation_id=generation_id,
        )
        message_id = msg_result["id"]

        # Create in-memory tracking
        gen = InMemoryGeneration(
            generation_id=generation_id,
            chat_id=chat_id,
            message_id=message_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        async with self._lock:
            # Cancel any existing generation for this chat
            old_gen_id = self._chat_to_gen.get(chat_id)
            if old_gen_id and old_gen_id in self._generations:
                old_gen = self._generations[old_gen_id]
                old_gen.cancel_event.set()
                if old_gen.task and not old_gen.task.done():
                    old_gen.task.cancel()

            self._generations[generation_id] = gen
            self._chat_to_gen[chat_id] = generation_id

        # Create Redis state
        if redis_client.available:
            await redis_client.create_generation(generation_id, chat_id, message_id)

        # Launch background task
        task = asyncio.create_task(
            self._run_generation(
                gen,
                user_message,
                search_enabled=search_enabled,
                thinking_enabled=thinking_enabled,
                attached_files=attached_files or [],
            )
        )
        gen.task = task

        # Fire-and-forget cleanup when task completes
        task.add_done_callback(
            lambda t: asyncio.create_task(self._on_task_done(generation_id))
        )

        return GenerationResult(
            generation_id=generation_id,
            message_id=message_id,
            chat_id=chat_id,
        )

    async def _run_generation(
        self,
        gen: InMemoryGeneration,
        user_message: str,
        search_enabled: bool = False,
        thinking_enabled: bool = False,
        attached_files: Optional[list[str]] = None,
    ):
        """Background task that runs the AI pipeline and streams chunks."""
        from agents.orchestrator import orchestrator

        chat_id = gen.chat_id
        generation_id = gen.generation_id

        try:
            # Get chat context
            chat = chat_manager.get_chat(chat_id)
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")

            # Build conversation history
            history_messages = chat_manager.get_history(chat_id, last_n=6)
            history = "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in history_messages
            )
            chat_files = chat_manager.get_chat_files(chat_id)
            for filename in attached_files or []:
                if filename not in chat_files:
                    chat_files.append(filename)

            # Use a queue to pass chunks from the blocking generator thread
            # to the async event loop without blocking it
            chunk_queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def _blocking_stream():
                """Run the synchronous generator in a separate thread."""
                try:
                    for event in orchestrator.stream_question_with_trace(
                        query=user_message,
                        search_enabled=search_enabled,
                        thinking_enabled=thinking_enabled,
                        history=history,
                        allowed_sources=chat_files,
                    ):
                        if gen.cancel_event.is_set():
                            break
                        if not event:
                            continue
                        if event.get("type") == "token":
                            # Clean thinking tags from chunks
                            cleaned = re.sub(
                                r"<think>.*?</think>", "", event.get("chunk", ""), flags=re.DOTALL
                            )
                            if cleaned:
                                event["chunk"] = cleaned
                                loop.call_soon_threadsafe(chunk_queue.put_nowait, event)
                        else:
                            loop.call_soon_threadsafe(chunk_queue.put_nowait, event)
                except Exception as e:
                    loop.call_soon_threadsafe(
                        chunk_queue.put_nowait, Exception(str(e))
                    )
                finally:
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

            # Start the blocking stream in a thread
            thread_future = loop.run_in_executor(None, _blocking_stream)

            # Consume chunks from the queue asynchronously
            flush_counter = 0
            while True:
                item = await chunk_queue.get()

                if item is None:
                    # Stream ended
                    break

                if isinstance(item, Exception):
                    raise item

                event = item
                event_type = event.get("type")

                if event_type == "token":
                    cleaned = event.get("chunk", "")
                    if not cleaned:
                        continue

                    # Update in-memory state
                    gen.seq += 1
                    event["seq"] = gen.seq
                    gen.chunks.append(cleaned)
                    gen.full_content += cleaned

                    # Update Redis
                    if redis_client.available:
                        await redis_client.append_chunk(generation_id, cleaned)

                    # Periodic DB flush (every 5 chunks for faster recovery)
                    flush_counter += 1
                    if flush_counter % 5 == 0:
                        chat_manager.update_message_content(
                            gen.message_id,
                            gen.full_content,
                            "streaming",
                            reasoning=gen.reasoning or None,
                            sources=gen.sources,
                            agent_steps=gen.agent_steps,
                        )
                elif event_type == "agent_status":
                    self._merge_agent_step(gen, event)
                    gen.trace_events.append(dict(event))
                    if redis_client.available:
                        await redis_client.append_event(generation_id, event)
                    chat_manager.update_message_trace(
                        gen.message_id,
                        reasoning=gen.reasoning or None,
                        sources=gen.sources,
                        agent_steps=gen.agent_steps,
                    )
                elif event_type == "reasoning":
                    gen.reasoning = event.get("content", "")
                    gen.trace_events.append(dict(event))
                    if redis_client.available:
                        await redis_client.append_event(generation_id, event)
                    chat_manager.update_message_trace(
                        gen.message_id,
                        reasoning=gen.reasoning,
                        sources=gen.sources,
                        agent_steps=gen.agent_steps,
                    )
                elif event_type == "sources":
                    gen.sources = event.get("files", []) or []
                    gen.trace_events.append(dict(event))
                    if redis_client.available:
                        await redis_client.append_event(generation_id, event)
                    chat_manager.update_message_trace(
                        gen.message_id,
                        reasoning=gen.reasoning or None,
                        sources=gen.sources,
                        agent_steps=gen.agent_steps,
                    )
                elif event_type == "error":
                    gen.trace_events.append(dict(event))
                    gen.events.append(dict(event))
                    gen.new_chunk_event.set()
                    gen.new_chunk_event.clear()
                    raise Exception(event.get("error", "Generation failed"))
                else:
                    gen.trace_events.append(dict(event))
                    if redis_client.available:
                        await redis_client.append_event(generation_id, event)

                # Signal waiting subscribers
                gen.events.append(dict(event))
                gen.new_chunk_event.set()
                gen.new_chunk_event.clear()

            # Wait for thread to finish
            await asyncio.wrap_future(thread_future)

            # Final state
            if gen.cancel_event.is_set():
                gen.status = "stopped"
                chat_manager.update_message_content(
                    gen.message_id,
                    gen.full_content,
                    "stopped",
                    reasoning=gen.reasoning or None,
                    sources=gen.sources,
                    agent_steps=gen.agent_steps,
                )
                if redis_client.available:
                    await redis_client.stop_generation(generation_id, chat_id)
            else:
                gen.status = "completed"
                chat_manager.update_message_content(
                    gen.message_id,
                    gen.full_content,
                    "completed",
                    reasoning=gen.reasoning or None,
                    sources=gen.sources,
                    agent_steps=gen.agent_steps,
                )
                if redis_client.available:
                    await redis_client.complete_generation(generation_id, chat_id)

        except asyncio.CancelledError:
            gen.status = "stopped"
            chat_manager.update_message_content(
                gen.message_id,
                gen.full_content,
                "stopped",
                reasoning=gen.reasoning or None,
                sources=gen.sources,
                agent_steps=gen.agent_steps,
            )
            if redis_client.available:
                await redis_client.stop_generation(generation_id, chat_id)

        except Exception as e:
            error_msg = str(e)
            gen.status = "failed"
            gen.error = error_msg

            # Save error as the message content
            error_content = gen.full_content or f"Error: {error_msg}"
            chat_manager.update_message_content(
                gen.message_id,
                error_content,
                "failed",
                reasoning=gen.reasoning or None,
                sources=gen.sources,
                agent_steps=gen.agent_steps,
            )
            if redis_client.available:
                await redis_client.fail_generation(generation_id, chat_id, error_msg)

    def _merge_agent_step(self, gen: InMemoryGeneration, event: dict):
        agent = event.get("agent")
        if not agent:
            return

        existing = next((step for step in gen.agent_steps if step.get("agent") == agent), None)
        if existing is None:
            existing = {"agent": agent, "startedAt": int(datetime.now(timezone.utc).timestamp() * 1000)}
            gen.agent_steps.append(existing)

        existing.update({
            "status": event.get("status", existing.get("status", "running")),
            "label": event.get("label") or existing.get("label") or agent.title(),
        })
        if event.get("detail"):
            existing["detail"] = event["detail"]
        if event.get("duration_ms") is not None:
            existing["duration_ms"] = event["duration_ms"]

    async def _on_task_done(self, generation_id: str):
        """Cleanup callback when a generation task finishes."""
        # Schedule removal after 5 minutes to allow reconnects
        await asyncio.sleep(300)
        async with self._lock:
            gen = self._generations.pop(generation_id, None)
            if gen:
                self._chat_to_gen.pop(gen.chat_id, None)

    async def stop_generation(self, generation_id: str) -> bool:
        gen = self._generations.get(generation_id)
        if not gen or gen.status != "streaming":
            return False

        gen.cancel_event.set()

        # Wait briefly for task to notice cancellation
        if gen.task and not gen.task.done():
            try:
                await asyncio.wait_for(asyncio.shield(gen.task), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                gen.task.cancel()

        return True

    async def get_active_generation(self, chat_id: str) -> Optional[dict]:
        # Try Redis first (multi-instance safe)
        if redis_client.available:
            gen_id = await redis_client.get_active_generation(chat_id)
            if gen_id:
                state = await redis_client.get_generation_state(gen_id)
                if state and state.get("status") == "streaming":
                    return state
                return None

        # Fall back to in-memory
        gen_id = self._chat_to_gen.get(chat_id)
        if gen_id:
            gen = self._generations.get(gen_id)
            if gen and gen.status == "streaming":
                return {
                    "generation_id": gen.generation_id,
                    "chat_id": gen.chat_id,
                    "message_id": gen.message_id,
                    "status": gen.status,
                    "seq": str(gen.seq),
                }
        return None

    async def get_generation_state(self, generation_id: str) -> Optional[dict]:
        # Try Redis first
        if redis_client.available:
            state = await redis_client.get_generation_state(generation_id)
            if state:
                return state

        # Fall back to in-memory
        gen = self._generations.get(generation_id)
        if gen:
            return {
                "generation_id": gen.generation_id,
                "chat_id": gen.chat_id,
                "message_id": gen.message_id,
                "status": gen.status,
                "seq": str(gen.seq),
                "error": gen.error,
            }
        return None

    async def subscribe(self, generation_id: str, last_seq: int = 0):
        """
        Async generator that yields chunks for SSE.
        Replays missed chunks from last_seq, then streams live ones.
        """
        gen = self._generations.get(generation_id)

        # Replay missed chunks
        if redis_client.available:
            events = await redis_client.get_events(generation_id)
            for event in events:
                if event.get("type") == "token" and int(event.get("seq", 0)) <= last_seq:
                    continue
                yield event
        elif gen:
            for event in gen.events:
                if event.get("type") == "token" and int(event.get("seq", 0)) <= last_seq:
                    continue
                yield event

        # Check if already done
        state = await self.get_generation_state(generation_id)
        if not state or state.get("status") != "streaming":
            status = state.get("status", "completed") if state else "completed"
            yield {"type": status, "seq": int(state.get("seq", 0)) if state else 0}
            return

        # Live stream via Redis Pub/Sub if available
        if redis_client.available:
            current_seq = int(state.get("seq", 0))
            async for event in redis_client.subscribe_to_generation(generation_id):
                if event["type"] == "token":
                    current_seq = int(event.get("seq", current_seq + 1))
                    yield event
                else:
                    event["seq"] = current_seq
                    yield event
                    return
        elif gen:
            # In-memory fallback: event-driven with timeout
            current_event_index = len(gen.events)
            while gen.status == "streaming":
                if len(gen.events) > current_event_index:
                    for event in gen.events[current_event_index:]:
                        yield event
                    current_event_index = len(gen.events)
                else:
                    # Wait for new chunks with a timeout
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(gen.new_chunk_event.wait()),
                            timeout=0.1,
                        )
                    except asyncio.TimeoutError:
                        pass

            # Yield any remaining chunks
            if len(gen.events) > current_event_index:
                for event in gen.events[current_event_index:]:
                    yield event

            yield {"type": gen.status, "seq": gen.seq}

    async def cleanup(self):
        """Cancel all active generation tasks."""
        async with self._lock:
            for gen in self._generations.values():
                if gen.task and not gen.task.done():
                    gen.cancel_event.set()
                    gen.task.cancel()
            self._generations.clear()
            self._chat_to_gen.clear()


# Singleton
generation_manager = AsyncioGenerationManager()
