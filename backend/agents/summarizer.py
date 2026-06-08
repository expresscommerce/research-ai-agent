"""
Summarizer Agent — converts findings into structured, professional reports.
"""

from __future__ import annotations

import json

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm_json


class SummarizerAgent(BaseAgent):
    agent_type = "summarizer"

    async def execute(self, context: AgentContext) -> AgentResult:
        analysis = context.previous_analysis
        findings = context.previous_findings

        # Collect all sources
        all_sources = []
        for f in findings:
            if isinstance(f, dict):
                all_sources.extend(f.get("sources", []))

        revision_note = ""
        if context.critic_feedback:
            revision_note = f"""

**REVISION REQUIRED — Critic Feedback:**
Quality Score: {context.critic_feedback.get('quality_score', 'N/A')}
Improvement suggestions:
{json.dumps(context.critic_feedback.get('improvement_suggestions', []), indent=2)}
Weaknesses to fix:
{json.dumps(context.critic_feedback.get('weaknesses', []), indent=2)}

This is revision #{context.iteration}. Address all feedback items.
"""

        user_message = f"""Generate a professional research report based on the following:

**Original Query:** {context.query}

**Analysis Results:**
{json.dumps(analysis, indent=2)}

**Source References ({len(all_sources)} sources):**
{json.dumps(all_sources[:20], indent=2)}
{revision_note}
**Iteration:** {context.iteration}

Create a comprehensive, well-structured report with executive summary, detailed findings, key insights, risks, recommendations, and source references."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.5,
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
