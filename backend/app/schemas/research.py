"""Research session schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=10, max_length=5000, description="The research question")
    model: Optional[str] = Field(None, description="LLM model to use (e.g., openai/gpt-4o)")
    max_iterations: Optional[int] = Field(None, ge=1, le=5, description="Max feedback iterations")
    quality_threshold: Optional[int] = Field(None, ge=50, le=100, description="Quality threshold score")


class ResearchSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    query: str
    status: str
    config: dict
    iteration_count: int
    confidence_score: Optional[float]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ResearchListResponse(BaseModel):
    sessions: list[ResearchSessionResponse]
    total: int
