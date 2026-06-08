"""
Research API routes — create, list, get, delete research sessions.
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.websocket import manager as ws_manager
from app.database import get_db
from app.models.user import User
from app.schemas.research import ResearchRequest, ResearchSessionResponse, ResearchListResponse
from app.services.research_service import ResearchService, run_research_in_background

router = APIRouter(prefix="/research", tags=["Research"])


@router.post("", response_model=ResearchSessionResponse, status_code=201)
async def create_research(
    body: ResearchRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new research session. The research runs asynchronously in the background."""
    service = ResearchService(db)
    session = await service.create_session(
        user=user,
        query=body.query,
        model=body.model,
        max_iterations=body.max_iterations,
        quality_threshold=body.quality_threshold,
    )

    # Create progress callback for WebSocket updates
    async def progress_callback(data: dict):
        await ws_manager.broadcast_to_session(str(session.id), data)

    # Start research in background
    background_tasks.add_task(
        run_research_in_background,
        session_id=session.id,
        user_id=user.id,
        progress_callback=progress_callback,
    )

    return ResearchSessionResponse.model_validate(session)


@router.get("", response_model=ResearchListResponse)
async def list_research(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all research sessions for the current user."""
    service = ResearchService(db)
    sessions, total = await service.list_sessions(user.id, limit, offset)
    return ResearchListResponse(
        sessions=[ResearchSessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.get("/{session_id}", response_model=ResearchSessionResponse)
async def get_research(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific research session."""
    service = ResearchService(db)
    session = await service.get_session(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Research session not found")
    return ResearchSessionResponse.model_validate(session)


@router.delete("/{session_id}")
async def delete_research(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a research session."""
    service = ResearchService(db)
    deleted = await service.delete_session(session_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Research session not found")
    return {"message": "Session deleted"}
