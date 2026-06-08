"""
Source Verifier Agent — checks relevance, credibility, and authority of gathered sources.
"""

from __future__ import annotations

import json
import logging

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm_json

logger = logging.getLogger(__name__)


class SourceVerifierAgent(BaseAgent):
    agent_type = "source_verifier"

    async def execute(self, context: AgentContext) -> AgentResult:
        # Context.previous_findings has the researcher's output at index -1 (since we append researcher's findings)
        researcher_output = context.previous_findings[-1] if context.previous_findings else {}
        sources_to_verify = researcher_output.get("sources", [])

        # If no sources are found in the structured output, check context.previous_findings directly
        if not sources_to_verify and len(context.previous_findings) > 1:
            # Maybe it is stored in another format, try to find a list of sources
            for findings in reversed(context.previous_findings):
                if isinstance(findings, dict) and "sources" in findings:
                    sources_to_verify = findings["sources"]
                    break

        user_message = f"""Verify the following sources for the research query:

**Research Query:** {context.query}

**Sources to verify:**
{json.dumps(sources_to_verify, indent=2)}

Evaluate their credibility and decide whether to trust or reject them."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.2,
            max_tokens=2000,
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
