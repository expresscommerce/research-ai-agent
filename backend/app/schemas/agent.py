"""Agent execution schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AgentExecutionResponse(BaseModel):
    id: uuid.UUID
    agent_type: str
    iteration: int
    status: str
    input_data: dict
    output_data: dict
    model_used: Optional[str]
    tokens_input: int
    tokens_output: int
    cost_estimate: float
    duration_seconds: float
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True
