"""
Session Memory Manager — manages context between agent executions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import SessionMemory


class MemoryManager:
    """Manages session-scoped memory for inter-agent communication."""

    def __init__(self, db: AsyncSession, session_id: uuid.UUID):
        self.db = db
        self.session_id = session_id

    async def store(
        self,
        key: str,
        value: str,
        memory_type: str = "context",
        metadata: dict | None = None,
    ) -> SessionMemory:
        """Store a memory entry."""
        entry = SessionMemory(
            session_id=self.session_id,
            memory_type=memory_type,
            key=key,
            value=value,
            metadata_extra=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()
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
