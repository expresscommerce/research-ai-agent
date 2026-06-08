"""
Critic Agent — reviews reports, scores quality, and requests improvements.
"""

from __future__ import annotations

import json

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm_json


class CriticAgent(BaseAgent):
    agent_type = "critic"

    async def execute(self, context: AgentContext) -> AgentResult:
        report = context.previous_report
        analysis = context.previous_analysis
        findings = context.previous_findings

        user_message = f"""Review this research report for quality, completeness, and accuracy.

**Original Research Query:** {context.query}

**Draft Report:**
Executive Summary: {report.get('executive_summary', 'N/A')}

Detailed Report: {report.get('detailed_report', 'N/A')[:3000]}

Key Insights: {json.dumps(report.get('key_insights', []), indent=2)}

Risks: {json.dumps(report.get('risks', []), indent=2)}

Recommendations: {json.dumps(report.get('recommendations', []), indent=2)}

**Analysis That Produced This Report:**
Key Findings: {json.dumps(analysis.get('key_findings', [])[:5], indent=2)}
Contradictions: {json.dumps(analysis.get('contradictions', []), indent=2)}
Data Quality: {json.dumps(analysis.get('data_quality_assessment', {{}}), indent=2)}

**Number of Source References:** {len(report.get('source_references', []))}
**Iteration:** {context.iteration}
**Max Iterations Allowed:** {context.config.get('max_iterations', 3)}

Evaluate this report rigorously. Be honest about scores. If this is the final iteration, be more lenient but still honest."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.3,
            max_tokens=3000,
        )

        data = response["data"]

        # Ensure quality_score is a number
        quality_score = data.get("quality_score", 70)
        if isinstance(quality_score, str):
            try:
                quality_score = int(quality_score)
            except (ValueError, TypeError):
                quality_score = 70

        data["quality_score"] = quality_score

        return AgentResult(
            agent_type=self.agent_type,
            status="completed",
            output=data,
            tokens_input=response["tokens_input"],
            tokens_output=response["tokens_output"],
            cost_estimate=response["cost_estimate"],
            model_used=response["model"],
        )
