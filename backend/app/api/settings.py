"""
Settings API routes — API key management.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.settings import APIKeyUpdate, APIKeyConfigResponse, APIKeyTestRequest, APIKeyTestResponse
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/api-keys", response_model=APIKeyConfigResponse)
async def get_api_key(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get configured API key config."""
    service = SettingsService(db)
    return await service.get_api_key_config(user)


@router.put("/api-keys", response_model=APIKeyConfigResponse)
async def update_api_key(
    body: APIKeyUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update API key. Automatically detects provider and encrypts it."""
    service = SettingsService(db)
    return await service.update_api_key(user, body.api_key)


@router.post("/api-keys/test", response_model=APIKeyTestResponse)
async def test_api_key(
    body: APIKeyTestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test an API key against its automatically detected provider."""
    service = SettingsService(db)
    result = await service.test_api_key(body.api_key, body.model)
    return APIKeyTestResponse(**result)


@router.get("/models")
async def list_models(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all available models grouped by provider."""
    service = SettingsService(db)
    return await service.get_available_models()
