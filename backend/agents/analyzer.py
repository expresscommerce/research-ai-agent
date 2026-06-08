"""
Analyzer Agent — identifies trends, insights, contradictions, and key findings.
"""

from __future__ import annotations

import json

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm_json


class AnalyzerAgent(BaseAgent):
    agent_type = "analyzer"

    async def execute(self, context: AgentContext) -> AgentResult:
        # Gather all findings from previous researcher executions
        all_findings = []
        for finding_set in context.previous_findings:
            if isinstance(finding_set, dict):
                all_findings.extend(finding_set.get("findings", []))

        feedback_section = ""
        if context.critic_feedback:
            analysis_feedback = context.critic_feedback.get("analysis_feedback", "")
            if analysis_feedback:
                feedback_section = f"""

**IMPORTANT — Critic Feedback for Re-analysis:**
{analysis_feedback}

Weaknesses to address:
{json.dumps(context.critic_feedback.get('weaknesses', []), indent=2)}
"""

        user_message = f"""Analyze the following research findings:

**Original Query:** {context.query}

**Research Findings ({len(all_findings)} items):**
{json.dumps(all_findings, indent=2)}
{feedback_section}
**Iteration:** {context.iteration}

Provide deep analysis including key findings, trends, insights, contradictions, risks, and data quality assessment."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.4,
            max_tokens=5000,
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
