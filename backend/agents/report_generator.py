"""
Report Generator Agent — compiles and formats final output with verified citations.
"""

from __future__ import annotations

import json
import logging

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm_json

logger = logging.getLogger(__name__)


class ReportGeneratorAgent(BaseAgent):
    agent_type = "report_generator"

    async def execute(self, context: AgentContext) -> AgentResult:
        # Get the summarizer's draft report
        draft_report = context.previous_report if context.previous_report else {}
        
        # Get the verified sources (from previous findings / memory)
        verified_sources_data = {}
        for findings in reversed(context.previous_findings):
            if isinstance(findings, dict) and "verified_sources" in findings:
                verified_sources_data = findings
                break

        user_message = f"""Compile and format the final research report based on the following:

**Draft Report:**
{json.dumps(draft_report, indent=2)}

**Verified Sources:**
{json.dumps(verified_sources_data, indent=2)}

**Original Query:** {context.query}

Please produce the final polished report JSON according to your formatting guidelines."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.3,
            max_tokens=6000,
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
