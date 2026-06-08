"""Settings schemas."""

from __future__ import annotations

from pydantic import BaseModel


class APIKeyUpdate(BaseModel):
    api_key: str | None = None


class APIKeyConfigResponse(BaseModel):
    configured: bool
    provider: str | None = None
    masked_key: str | None = None
    models: list[str] = []


class APIKeyTestRequest(BaseModel):
    api_key: str
    model: str | None = None


class APIKeyTestResponse(BaseModel):
    provider: str
    success: bool
    message: str
    model_tested: str | None = None

