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

        # Pass only metadata summaries to prevent output truncation
        user_message = f"""Compile and format the final research report metadata based on the following:

**Draft Report Summary:**
- Executive Summary: {draft_report.get("executive_summary", "")}
- Key Insights: {json.dumps(draft_report.get("key_insights", []), indent=2)}
- Risks: {json.dumps(draft_report.get("risks", []), indent=2)}
- Recommendations: {json.dumps(draft_report.get("recommendations", []), indent=2)}

**Verified Sources:**
{json.dumps(verified_sources_data, indent=2)}

**Original Query:** {context.query}

Please produce the final polished report JSON according to your formatting guidelines. You do not need to rewrite the detailed_report text (leave it as a placeholder or empty string), as we will automatically inject the high-resolution section-by-section draft report body."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.3,
            max_tokens=2000,
        )

        data = response["data"]

        # Inject and format the massive detailed report body from the Summarizer draft
        detailed_report_body = draft_report.get("detailed_report", "")
        
        # Build a formal academic bibliography
        sources_list = data.get("source_references", [])
        if not sources_list:
            sources_list = draft_report.get("source_references", [])
        if not sources_list and isinstance(verified_sources_data, dict):
            sources_list = verified_sources_data.get("verified_sources", [])

        bibliography_markdown = "\n\n## References & Bibliography\n\n"
        if sources_list:
            for idx, src in enumerate(sources_list, 1):
                title = src.get("title", "Research Source")
                url = src.get("url", "")
                cred = src.get("credibility", "high")
                snippet = src.get("citation_snippet", src.get("snippet", ""))
                
                url_str = f"  \nSource Link: {url}" if url else ""
                bibliography_markdown += f"**[{idx}]** *{title}*{url_str}  \n*Credibility: {cred.upper()}* | *Excerpt: \"{snippet}\"*\n\n"
        else:
            bibliography_markdown += "*No external sources were verified for this report.*\n"

        # Assemble the formal academic research paper layout
        academic_paper = f"""# RESEARCH PAPER: {context.query.upper()}

**Abstract**  
{data.get("executive_summary", draft_report.get("executive_summary", ""))}

---

{detailed_report_body}

---

{bibliography_markdown}
"""
        # Save the structured paper back to detailed_report
        data["detailed_report"] = academic_paper

        return AgentResult(
            agent_type=self.agent_type,
            status="completed",
            output=data,
            tokens_input=response["tokens_input"],
            tokens_output=response["tokens_output"],
            cost_estimate=response["cost_estimate"],
            model_used=response["model"],
        )
