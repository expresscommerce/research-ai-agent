"""
Execution logs API routes.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.research_service import ResearchService

router = APIRouter(prefix="/research/{session_id}/logs", tags=["Logs"])


class LogResponse(BaseModel):
    id: uuid.UUID
    level: str
    agent_type: Optional[str]
    message: str
    data: Optional[dict]
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[LogResponse])
async def get_logs(
    session_id: uuid.UUID,
    level: Optional[str] = Query(None, description="Filter by log level"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get execution logs for a research session."""
    service = ResearchService(db)
    session = await service.get_session(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Research session not found")

    logs = await service.get_logs(session_id, level)
    return [
        LogResponse(
            id=log.id,
            level=log.level,
            agent_type=log.agent_type,
            message=log.message,
            data=log.data,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
