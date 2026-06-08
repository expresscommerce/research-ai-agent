"""
LLM Provider Abstraction Layer.

Uses LiteLLM to provide a unified interface across OpenAI, Anthropic,
Gemini, DeepInfra, OpenRouter, and more. Users supply their own API keys.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

# pyrefly: ignore [missing-import]
import litellm

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True
litellm.set_verbose = False

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    model: str
    tokens_input: int = 0
    tokens_output: int = 0
    cost_estimate: float = 0.0
    raw_response: dict = field(default_factory=dict)


# Map of provider names to their environment variable keys
PROVIDER_ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepinfra": "DEEPINFRA_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "together_ai": "TOGETHERAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}

# Supported models per provider
SUPPORTED_MODELS = {
    "openai": [
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "openai/gpt-4-turbo",
        "openai/o1-mini",
    ],
    "anthropic": [
        "anthropic/claude-sonnet-4-20250514",
        "anthropic/claude-3-5-haiku-20241022",
        "anthropic/claude-3-opus-20240229",
    ],
    "gemini": [
        "gemini/gemini-2.0-flash",
        "gemini/gemini-1.5-pro",
        "gemini/gemini-1.5-flash",
    ],
    "deepinfra": [
        "deepinfra/meta-llama/Meta-Llama-3.1-70B-Instruct",
        "deepinfra/mistralai/Mixtral-8x22B-Instruct-v0.1",
    ],
    "openrouter": [
        "openrouter/openai/gpt-4o",
        "openrouter/anthropic/claude-sonnet-4-20250514",
        "openrouter/meta-llama/llama-3.1-70b-instruct",
    ],
}


def set_provider_keys(api_keys: dict[str, str]):
    """
    Set decrypted API keys as environment variables for LiteLLM.
    Call this before making LLM calls for a specific user.
    """
    for provider, key in api_keys.items():
        env_var = PROVIDER_ENV_MAP.get(provider.lower())
        if env_var and key:
            os.environ[env_var] = key


def clear_provider_keys():
    """Remove all provider keys from environment after use."""
    for env_var in PROVIDER_ENV_MAP.values():
        os.environ.pop(env_var, None)


async def call_llm(
    model: str,
    system_prompt: str,
    user_message: str,
    api_keys: dict[str, str] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: Optional[dict] = None,
) -> LLMResponse:
    """
    Make a unified LLM call through LiteLLM.
    
    Args:
        model: Model identifier (e.g., "openai/gpt-4o-mini")
        system_prompt: System-level instructions for the agent
        user_message: The actual user/agent message
        api_keys: Decrypted user API keys dict
        temperature: Creativity parameter
        max_tokens: Maximum response length
        response_format: Optional JSON schema for structured output
    
    Returns:
        LLMResponse with content, token usage, and cost estimate
    """
    if api_keys:
        set_provider_keys(api_keys)

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": 300,
        }

        if response_format:
            kwargs["response_format"] = response_format

        response = await litellm.acompletion(**kwargs)

        content = response.choices[0].message.content or ""
        usage = response.usage

        cost_estimate = 0.0
        if usage:
            try:
                cost_estimate = litellm.completion_cost(completion_response=response)
            except Exception:
                # Default to 0.0 if LiteLLM cannot calculate the cost
                cost_estimate = 0.0

        return LLMResponse(
            content=content,
            model=model,
            tokens_input=usage.prompt_tokens if usage else 0,
            tokens_output=usage.completion_tokens if usage else 0,
            cost_estimate=cost_estimate,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else {},
        )

    except Exception as e:
        logger.error(f"LLM call failed for model {model}: {e}")
        raise
    finally:
        if api_keys:
            clear_provider_keys()


async def call_llm_json(
    model: str,
    system_prompt: str,
    user_message: str,
    api_keys: dict[str, str] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> dict:
    """
    Call LLM and parse the response as JSON.
    Instructs the model to return valid JSON and attempts parsing.
    """
    enhanced_prompt = system_prompt + "\n\nYou MUST respond with valid JSON only. No markdown, no explanation, just pure JSON."

    response = await call_llm(
        model=model,
        system_prompt=enhanced_prompt,
        user_message=user_message,
        api_keys=api_keys,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    content = response.content.strip()
    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # Clean up unescaped literal newlines in JSON strings
    cleaned_content = repair_json_newlines(content)

    try:
        parsed = json.loads(cleaned_content)
    except json.JSONDecodeError:
        try:
            # Fallback to original content
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from LLM response, returning raw content")
            parsed = {"raw_content": content, "parse_error": True}

    return {
        "data": parsed,
        "tokens_input": response.tokens_input,
        "tokens_output": response.tokens_output,
        "cost_estimate": response.cost_estimate,
        "model": response.model,
    }


def repair_json_newlines(s: str) -> str:
    """Replace literal unescaped newlines inside JSON string values with \\n."""
    in_string = False
    escaped = False
    result = []
    for char in s:
        if char == '"' and not escaped:
            in_string = not in_string
            result.append(char)
        elif char == '\\' and in_string:
            escaped = not escaped
            result.append(char)
        else:
            if char == '\n' and in_string:
                result.append('\\n')
            elif char == '\r' and in_string:
                result.append('\\r')
            else:
                result.append(char)
            escaped = False
    return "".join(result)
