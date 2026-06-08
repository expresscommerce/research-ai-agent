"""
Abstract Base Agent — contract for all specialized agents.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Input context passed to an agent."""
    session_id: uuid.UUID
    query: str
    model: str
    api_keys: dict[str, str]
    iteration: int = 1
    previous_findings: list[dict] = field(default_factory=list)
    previous_analysis: dict = field(default_factory=dict)
    previous_report: dict = field(default_factory=dict)
    critic_feedback: dict = field(default_factory=dict)
    memory: list[dict] = field(default_factory=list)
    config: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """Output from an agent execution."""
    agent_type: str
    status: str = "completed"  # completed | failed
    output: dict = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0
    cost_estimate: float = 0.0
    model_used: str = ""
    duration_seconds: float = 0.0
    error: Optional[str] = None


class BaseAgent(ABC):
    """Abstract base class for all research agents."""

    agent_type: str = "base"

    def __init__(self):
        self.prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load the system prompt from the prompts directory."""
        prompt_path = Path(__file__).parent / "prompts" / f"{self.agent_type}.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        logger.warning(f"No prompt file found for {self.agent_type}, using default")
        return f"You are a {self.agent_type} agent."

    async def run(self, context: AgentContext) -> AgentResult:
        """Execute the agent with timing and error handling."""
        start = time.time()
        logger.info(f"[{self.agent_type}] Starting execution (iteration {context.iteration})")

        try:
            result = await self.execute(context)
            result.duration_seconds = time.time() - start
            logger.info(
                f"[{self.agent_type}] Completed in {result.duration_seconds:.2f}s "
                f"(tokens: {result.tokens_input}+{result.tokens_output})"
            )
            return result

        except Exception as e:
            duration = time.time() - start
            logger.error(f"[{self.agent_type}] Failed after {duration:.2f}s: {e}")
            return AgentResult(
                agent_type=self.agent_type,
                status="failed",
                error=str(e),
                duration_seconds=duration,
            )

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Implement the agent's core logic. Must be overridden."""
        ...
