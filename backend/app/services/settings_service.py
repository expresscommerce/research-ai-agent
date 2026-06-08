"""
Settings service — manages user API key storage and retrieval.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_value, decrypt_value, mask_key
from app.models.user import User
from agents.llm_provider import PROVIDER_ENV_MAP, SUPPORTED_MODELS, call_llm

logger = logging.getLogger(__name__)


def detect_provider(api_key: str) -> str:
    """Detect the LLM provider based on the API key prefix/format."""
    key = api_key.strip()
    if key.startswith("sk-ant-"):
        return "anthropic"
    elif key.startswith("AIzaSy"):
        return "gemini"
    elif key.startswith("gsk_"):
        return "groq"
    elif key.startswith("sk-or-v1-"):
        return "openrouter"
    elif key.startswith("sk-") or key.startswith("sk-proj-"):
        return "openai"
    else:
        # Default to deepinfra
        return "deepinfra"


class SettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_api_key_config(self, user: User) -> dict:
        """Get the active API key configuration."""
        api_keys = user.api_keys or {}
        active_provider = None
        decrypted_key = None

        for provider in PROVIDER_ENV_MAP:
            encrypted = api_keys.get(provider)
            if encrypted:
                try:
                    decrypted_key = decrypt_value(encrypted)
                    active_provider = provider
                    break
                except Exception:
                    continue

        if active_provider and decrypted_key:
            return {
                "configured": True,
                "provider": active_provider,
                "masked_key": mask_key(decrypted_key),
                "models": SUPPORTED_MODELS.get(active_provider, []),
            }

        return {
            "configured": False,
            "provider": None,
            "masked_key": None,
            "models": [],
        }

    async def update_api_key(self, user: User, api_key: str | None) -> dict:
        """Update API key. Automatically detects provider and encrypts it."""
        if not api_key:
            user.api_keys = {}
            await self.db.flush()
            return await self.get_api_key_config(user)

        provider = detect_provider(api_key)
        encrypted = encrypt_value(api_key.strip())

        # Store only the detected provider's key
        user.api_keys = {provider: encrypted}
        await self.db.flush()
        return await self.get_api_key_config(user)

    async def test_api_key(self, api_key: str, model: str | None = None) -> dict:
        """Test an API key by making a simple call."""
        provider = detect_provider(api_key)
        if not model:
            models = SUPPORTED_MODELS.get(provider, [])
            if not models:
                return {"success": False, "message": f"No models supported for provider: {provider}", "model_tested": None}
            model = models[0]

        try:
            response = await call_llm(
                model=model,
                system_prompt="You are a test assistant.",
                user_message="Say 'API key is working!' in exactly those words.",
                api_keys={provider: api_key.strip()},
                temperature=0.0,
                max_tokens=20,
            )
            return {
                "provider": provider,
                "success": True,
                "message": "Connection successful! API key is valid.",
                "model_tested": model,
            }
        except Exception as e:
            return {
                "provider": provider,
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "model_tested": model,
            }

    async def get_available_models(self) -> dict[str, list[str]]:
        """Return all supported models grouped by provider."""
        return SUPPORTED_MODELS
