"""
Agent execution API routes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.agent import AgentExecutionResponse
from app.services.research_service import ResearchService

router = APIRouter(prefix="/research/{session_id}/agents", tags=["Agents"])


@router.get("", response_model=list[AgentExecutionResponse])
async def list_executions(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all agent executions for a research session."""
    service = ResearchService(db)
    session = await service.get_session(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Research session not found")

    executions = await service.get_executions(session_id)
    return [AgentExecutionResponse.model_validate(e) for e in executions]
