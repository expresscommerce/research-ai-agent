"""
Planner Agent — analyzes research requests and creates research strategies.
"""

from __future__ import annotations

import json

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm_json


class PlannerAgent(BaseAgent):
    agent_type = "planner"

    async def execute(self, context: AgentContext) -> AgentResult:
        user_message = f"""Create a research strategy for the following query:

**Research Query:** {context.query}

**Additional Context:**
- Iteration: {context.iteration}
- Previous memory: {json.dumps(context.memory[:5]) if context.memory else 'None (first session)'}

Please analyze this query and create a comprehensive research plan."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.4,
            max_tokens=3000,
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
