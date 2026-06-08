"""
Research service — manages research session lifecycle and orchestration.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Callable

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agents.conductor import Conductor
from app.config import settings
from app.core.encryption import decrypt_value
from app.models.agent_execution import AgentExecution
from app.models.log import ExecutionLog
from app.models.report import Report
from app.models.research_session import ResearchSession
from app.models.source import ResearchSource
from app.models.user import User
from app.database import async_session

logger = logging.getLogger(__name__)


class ResearchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user: User,
        query: str,
        model: Optional[str] = None,
        max_iterations: Optional[int] = None,
        quality_threshold: Optional[int] = None,
    ) -> ResearchSession:
        """Create a new research session."""
        config = {
            "model": model or settings.DEFAULT_MODEL,
            "max_iterations": max_iterations or settings.MAX_ITERATIONS,
            "quality_threshold": quality_threshold or settings.QUALITY_THRESHOLD,
        }

        session = ResearchSession(
            user_id=user.id,
            title=query[:100],  # Temporary title, will be updated by planner
            query=query,
            status="pending",
            config=config,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Optional[ResearchSession]:
        """Get a session by ID, scoped to user."""
        result = await self.db.execute(
            select(ResearchSession).where(
                ResearchSession.id == session_id,
                ResearchSession.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_sessions(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> tuple[list[ResearchSession], int]:
        """List all sessions for a user."""
        count_result = await self.db.execute(
            select(func.count()).select_from(ResearchSession).where(
                ResearchSession.user_id == user_id
            )
        )
        total = count_result.scalar()

        result = await self.db.execute(
            select(ResearchSession)
            .where(ResearchSession.user_id == user_id)
            .order_by(desc(ResearchSession.created_at))
            .limit(limit)
            .offset(offset)
        )
        sessions = list(result.scalars().all())
        return sessions, total

    async def delete_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a session."""
        session = await self.get_session(session_id, user_id)
        if not session:
            return False
        await self.db.delete(session)
        await self.db.flush()
        return True

    async def get_executions(self, session_id: uuid.UUID) -> list[AgentExecution]:
        """Get all agent executions for a session."""
        result = await self.db.execute(
            select(AgentExecution)
            .where(AgentExecution.session_id == session_id)
            .order_by(AgentExecution.started_at)
        )
        return list(result.scalars().all())

    async def get_report(self, session_id: uuid.UUID) -> Optional[Report]:
        """Get the latest report for a session."""
        result = await self.db.execute(
            select(Report)
            .where(Report.session_id == session_id)
            .order_by(desc(Report.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_sources(self, session_id: uuid.UUID) -> list[ResearchSource]:
        """Get all sources for a session."""
        result = await self.db.execute(
            select(ResearchSource)
            .where(ResearchSource.session_id == session_id)
            .order_by(desc(ResearchSource.relevance_score))
        )
        return list(result.scalars().all())

    async def get_logs(self, session_id: uuid.UUID, level: Optional[str] = None) -> list[ExecutionLog]:
        """Get execution logs for a session."""
        query = select(ExecutionLog).where(
            ExecutionLog.session_id == session_id
        )
        if level:
            query = query.where(ExecutionLog.level == level.upper())
        query = query.order_by(ExecutionLog.created_at)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _decrypt_user_keys(self, user: User) -> dict[str, str]:
        """Decrypt user's stored API keys."""
        decrypted = {}
        for provider, encrypted_key in (user.api_keys or {}).items():
            try:
                decrypted[provider] = decrypt_value(encrypted_key)
            except Exception:
                logger.warning(f"Failed to decrypt key for provider {provider}")
        return decrypted


async def run_research_in_background(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    progress_callback: Optional[Callable] = None,
):
    """
    Run the research workflow in a background task.
    Creates its own database session to avoid sharing across threads.
    """
    async with async_session() as db:
        try:
            # Load session and user
            result = await db.execute(
                select(ResearchSession).where(ResearchSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                logger.error(f"Session {session_id} not found")
                return

            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"User {user_id} not found")
                return

            # Decrypt API keys
            service = ResearchService(db)
            api_keys = service._decrypt_user_keys(user)

            if not api_keys:
                session.status = "failed"
                log = ExecutionLog(
                    session_id=session.id,
                    level="ERROR",
                    agent_type="conductor",
                    message="No API keys configured. Please add at least one LLM provider key in Settings.",
                )
                db.add(log)
                await db.commit()
                if progress_callback:
                    await progress_callback({
                        "event": "error",
                        "session_id": str(session_id),
                        "message": "No API keys configured. Go to Settings to add your LLM provider API key.",
                    })
                return

            # Run conductor
            conductor = Conductor(
                db=db,
                session=session,
                api_keys=api_keys,
                progress_callback=progress_callback,
            )

            await conductor.run()
            await db.commit()

        except Exception as e:
            logger.error(f"Research workflow failed for session {session_id}: {e}")
            try:
                result = await db.execute(
                    select(ResearchSession).where(ResearchSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                if session:
                    session.status = "failed"
                    log = ExecutionLog(
                        session_id=session.id,
                        level="ERROR",
                        agent_type="conductor",
                        message=f"Workflow failed: {str(e)}",
                    )
                    db.add(log)
                await db.commit()
            except Exception:
                await db.rollback()
