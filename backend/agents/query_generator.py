"""
Query Generator Agent — generates optimized search queries for different search backends.
"""

from __future__ import annotations

import json
import logging

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm_json

logger = logging.getLogger(__name__)


class QueryGeneratorAgent(BaseAgent):
    agent_type = "query_generator"

    async def execute(self, context: AgentContext) -> AgentResult:
        # Get the planning strategy to generate queries from
        # Context.previous_findings contains the output of the Planner agent
        planner_plan = context.previous_findings[0] if context.previous_findings else {}

        user_message = f"""Generate engine-specific search queries based on this research plan:

**Research Plan:**
{json.dumps(planner_plan, indent=2)}

**Original Query:** {context.query}
**Iteration:** {context.iteration}

Please output the optimized queries for Tavily, DuckDuckGo, and arXiv."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.3,
            max_tokens=1500,
        )

        data = response["data"]

        return AgentResult(
            agent_type=self.agent_type,
            status="completed",
            output=data,
            tokens_input=response["tokens_input"],
            tokens_output=response["tokens_output"],
            cost_estimate=response["cost_estimate"],
            model_used=response["model"],
        )
