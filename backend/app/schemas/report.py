"""Report schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    executive_summary: Optional[str]
    detailed_report: Optional[str]
    key_insights: list
    risks: list
    recommendations: list
    source_references: list
    confidence_score: float
    revision_number: int
    critic_feedback: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class SourceResponse(BaseModel):
    id: uuid.UUID
    title: str
    url: Optional[str]
    content_snippet: Optional[str]
    relevance_score: float
    source_type: str
    found_at: datetime

    class Config:
        from_attributes = True
