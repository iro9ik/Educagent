"""
Redis client — singleton connection and stream buffer operations.

Used for:
- Active generation state storage
- Streaming token buffers with sequence numbers
- Pub/Sub broadcasting to SSE subscribers
- Reconnect synchronization
"""

import os
import json
import asyncio
from typing import Optional, AsyncGenerator
from datetime import datetime, timezone

import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Key prefixes
GEN_STATE_KEY = "gen:state:{gen_id}"       # Hash: generation metadata
GEN_CHUNKS_KEY = "gen:chunks:{gen_id}"     # List: ordered chunks
GEN_EVENTS_KEY = "gen:events:{gen_id}"     # List: ordered stream events
GEN_CHANNEL_KEY = "gen:channel:{gen_id}"   # Pub/Sub channel for live chunks
GEN_CONTENT_KEY = "gen:content:{gen_id}"   # String: accumulated full content
CHAT_ACTIVE_KEY = "chat:active:{chat_id}"  # String: active generation_id for a chat


class RedisClient:
    """Async Redis client wrapper for generation state management."""

    def __init__(self):
        self._pool: Optional[aioredis.Redis] = None
        self._available = False

    async def connect(self):
        """Initialize Redis connection pool."""
        try:
            self._pool = aioredis.from_url(
                REDIS_URL,
                decode_responses=True,
                max_connections=20,
            )
            # Test connection
            await self._pool.ping()
            self._available = True
            print("[+] Redis connected successfully.")
        except Exception as e:
            self._available = False
            print(f"[!] Redis not available ({e}). Falling back to in-memory state.")

    async def close(self):
        """Close the Redis connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available and self._pool is not None

    # ── Generation State ──────────────────────────────────────────────

    async def create_generation(
        self,
        generation_id: str,
        chat_id: str,
        message_id: str,
    ):
        """Create a new generation state entry."""
        if not self.available:
            return

        pipe = self._pool.pipeline()
        state_key = GEN_STATE_KEY.format(gen_id=generation_id)

        pipe.hset(state_key, mapping={
            "generation_id": generation_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "status": "streaming",
            "seq": "0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "error": "",
        })
        pipe.expire(state_key, 3600)  # 1 hour TTL

        # Set this as the active generation for the chat
        active_key = CHAT_ACTIVE_KEY.format(chat_id=chat_id)
        pipe.set(active_key, generation_id, ex=3600)

        # Initialize empty content
        content_key = GEN_CONTENT_KEY.format(gen_id=generation_id)
        pipe.set(content_key, "", ex=3600)

        await pipe.execute()

    async def append_chunk(self, generation_id: str, chunk: str) -> int:
        """Append a chunk and return its sequence number."""
        if not self.available:
            return 0

        state_key = GEN_STATE_KEY.format(gen_id=generation_id)
        seq = await self._pool.hincrby(state_key, "seq", 1)
        event = json.dumps({"type": "token", "chunk": chunk, "seq": seq})

        pipe = self._pool.pipeline()
        chunks_key = GEN_CHUNKS_KEY.format(gen_id=generation_id)
        events_key = GEN_EVENTS_KEY.format(gen_id=generation_id)
        content_key = GEN_CONTENT_KEY.format(gen_id=generation_id)
        channel_key = GEN_CHANNEL_KEY.format(gen_id=generation_id)

        # Append chunk to the ordered list
        pipe.rpush(chunks_key, chunk)
        # Append to full content
        pipe.append(content_key, chunk)
        pipe.rpush(events_key, event)
        # Publish to live subscribers
        pipe.publish(channel_key, event)

        await pipe.execute()
        return seq

    async def append_event(self, generation_id: str, event: dict):
        """Append and publish a non-token stream event."""
        if not self.available:
            return

        payload = json.dumps(event)
        pipe = self._pool.pipeline()
        events_key = GEN_EVENTS_KEY.format(gen_id=generation_id)
        channel_key = GEN_CHANNEL_KEY.format(gen_id=generation_id)
        pipe.rpush(events_key, payload)
        pipe.publish(channel_key, payload)
        await pipe.execute()

    async def complete_generation(self, generation_id: str, chat_id: str):
        """Mark generation as completed."""
        if not self.available:
            return

        pipe = self._pool.pipeline()
        state_key = GEN_STATE_KEY.format(gen_id=generation_id)
        channel_key = GEN_CHANNEL_KEY.format(gen_id=generation_id)
        active_key = CHAT_ACTIVE_KEY.format(chat_id=chat_id)

        pipe.hset(state_key, "status", "completed")
        pipe.publish(channel_key, json.dumps({"type": "completed"}))
        pipe.delete(active_key)

        # Set shorter TTL for completed generations (5 min cleanup)
        pipe.expire(state_key, 300)
        pipe.expire(GEN_CHUNKS_KEY.format(gen_id=generation_id), 300)
        pipe.expire(GEN_EVENTS_KEY.format(gen_id=generation_id), 300)
        pipe.expire(GEN_CONTENT_KEY.format(gen_id=generation_id), 300)

        await pipe.execute()

    async def fail_generation(self, generation_id: str, chat_id: str, error: str):
        """Mark generation as failed."""
        if not self.available:
            return

        pipe = self._pool.pipeline()
        state_key = GEN_STATE_KEY.format(gen_id=generation_id)
        channel_key = GEN_CHANNEL_KEY.format(gen_id=generation_id)
        active_key = CHAT_ACTIVE_KEY.format(chat_id=chat_id)

        pipe.hset(state_key, mapping={"status": "failed", "error": error})
        pipe.publish(channel_key, json.dumps({"type": "error", "error": error}))
        pipe.delete(active_key)
        pipe.expire(state_key, 300)

        await pipe.execute()

    async def stop_generation(self, generation_id: str, chat_id: str):
        """Mark generation as stopped (user-initiated)."""
        if not self.available:
            return

        pipe = self._pool.pipeline()
        state_key = GEN_STATE_KEY.format(gen_id=generation_id)
        channel_key = GEN_CHANNEL_KEY.format(gen_id=generation_id)
        active_key = CHAT_ACTIVE_KEY.format(chat_id=chat_id)

        pipe.hset(state_key, "status", "stopped")
        pipe.publish(channel_key, json.dumps({"type": "stopped"}))
        pipe.delete(active_key)
        pipe.expire(state_key, 300)

        await pipe.execute()

    # ── Query Methods ────────────────────────────────────────────────

    async def get_generation_state(self, generation_id: str) -> Optional[dict]:
        """Get the current state of a generation."""
        if not self.available:
            return None

        state_key = GEN_STATE_KEY.format(gen_id=generation_id)
        state = await self._pool.hgetall(state_key)
        return state if state else None

    async def get_chunks_from(self, generation_id: str, from_seq: int) -> list[str]:
        """Get all chunks starting from a sequence number."""
        if not self.available:
            return []

        chunks_key = GEN_CHUNKS_KEY.format(gen_id=generation_id)
        # Redis lists are 0-indexed, seq starts at 1
        chunks = await self._pool.lrange(chunks_key, from_seq, -1)
        return chunks

    async def get_events(self, generation_id: str) -> list[dict]:
        """Get all recorded stream events."""
        if not self.available:
            return []

        events_key = GEN_EVENTS_KEY.format(gen_id=generation_id)
        raw_events = await self._pool.lrange(events_key, 0, -1)
        events = []
        for raw in raw_events:
            try:
                events.append(json.loads(raw))
            except Exception:
                continue
        return events

    async def get_full_content(self, generation_id: str) -> str:
        """Get the accumulated full content."""
        if not self.available:
            return ""

        content_key = GEN_CONTENT_KEY.format(gen_id=generation_id)
        content = await self._pool.get(content_key)
        return content or ""

    async def get_active_generation(self, chat_id: str) -> Optional[str]:
        """Get the active generation_id for a chat, if any."""
        if not self.available:
            return None

        active_key = CHAT_ACTIVE_KEY.format(chat_id=chat_id)
        return await self._pool.get(active_key)

    async def subscribe_to_generation(
        self, generation_id: str
    ) -> AsyncGenerator[dict, None]:
        """Subscribe to live chunk events via Pub/Sub."""
        if not self.available:
            return

        channel_key = GEN_CHANNEL_KEY.format(gen_id=generation_id)
        pubsub = self._pool.pubsub()
        await pubsub.subscribe(channel_key)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield data
                    if data.get("type") in ("completed", "error", "stopped"):
                        break
        finally:
            await pubsub.unsubscribe(channel_key)
            await pubsub.close()


# Singleton instance
redis_client = RedisClient()
