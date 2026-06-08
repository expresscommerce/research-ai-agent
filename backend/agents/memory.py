"""
Session Memory Manager — manages context between agent executions.
"""

from __future__ import annotations

import uuid
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.models.memory import SessionMemory


logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages session-scoped memory for inter-agent communication."""

    def __init__(self, db: AsyncSession, session_id: uuid.UUID):
        self.db = db
        self.session_id = session_id
        # Initialize Qdrant Client (pointing to the internal Docker service host name "qdrant" on port 6333)
        try:
            self.qdrant = QdrantClient(url="http://qdrant:6333", timeout=5)
            self._init_qdrant_collection()
        except Exception as e:
            logger.warning(f"Failed to initialize Qdrant client: {e}")
            self.qdrant = None

    def _init_qdrant_collection(self):
        if self.qdrant:
            try:
                collections = self.qdrant.get_collections().collections
                exists = any(c.name == "research_memories" for c in collections)
                if not exists:
                    self.qdrant.create_collection(
                        collection_name="research_memories",
                        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
                    )
                    logger.info("Created Qdrant collection: research_memories")
            except Exception as e:
                logger.warning(f"Error checking/creating Qdrant collection: {e}")

    def _generate_pseudo_vector(self, text: str) -> list[float]:
        """Generate a lightweight, deterministic 1536-dimensional pseudo-vector from text.
        Avoids external embedding API dependencies and local neural network packages."""
        vector = [0.0] * 1536
        if not text:
            return vector
        h = hashlib.sha256(text.encode("utf-8")).digest()
        for i in range(1536):
            val = (h[i % 32] * (i + 1)) % 1000
            vector[i] = float(val) / 1000.0
        sq_sum = sum(x*x for x in vector)
        if sq_sum > 0:
            norm = sq_sum ** 0.5
            vector = [x / norm for x in vector]
        return vector

    async def store(
        self,
        key: str,
        value: str,
        memory_type: str = "context",
        metadata: dict | None = None,
    ) -> SessionMemory:
        """Store a memory entry in SQL and Qdrant."""
        entry = SessionMemory(
            session_id=self.session_id,
            memory_type=memory_type,
            key=key,
            value=value,
            metadata_extra=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()

        # Write to Qdrant safely
        if self.qdrant:
            try:
                vector = self._generate_pseudo_vector(value)
                point_id = str(uuid.uuid4())
                self.qdrant.upsert(
                    collection_name="research_memories",
                    points=[
                        PointStruct(
                            id=point_id,
                            vector=vector,
                            payload={
                                "session_id": str(self.session_id),
                                "memory_type": memory_type,
                                "key": key,
                                "value": value,
                                "metadata": metadata or {},
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to store memory in Qdrant: {e}")

        return entry

    async def recall(self, memory_type: Optional[str] = None) -> list[dict]:
        """Recall memories, optionally filtered by type."""
        query = select(SessionMemory).where(
            SessionMemory.session_id == self.session_id
        )
        if memory_type:
            query = query.where(SessionMemory.memory_type == memory_type)
        query = query.order_by(SessionMemory.created_at.desc())

        result = await self.db.execute(query)
        entries = result.scalars().all()
        return [
            {
                "key": e.key,
                "value": e.value,
                "type": e.memory_type,
                "metadata": e.metadata_extra,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]

    async def recall_as_context(self, limit: int = 20) -> list[dict]:
        """Get memory formatted for agent context injection."""
        query = (
            select(SessionMemory)
            .where(SessionMemory.session_id == self.session_id)
            .order_by(SessionMemory.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return [
            {"key": e.key, "value": e.value, "type": e.memory_type}
            for e in result.scalars().all()
        ]
