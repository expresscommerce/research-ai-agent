"""Common schema utilities."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None
