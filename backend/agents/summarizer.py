"""
Summarizer Agent — converts findings into structured, professional reports.
"""

from __future__ import annotations

import json
import asyncio
import logging

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm, call_llm_json

logger = logging.getLogger(__name__)


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

        # Step 1: Generate the outer metadata/summary structure (excluding detailed_report)
        user_message_meta = f"""Generate the metadata and summaries for a professional research report:

**Original Query:** {context.query}

**Analysis Results:**
{json.dumps(analysis, indent=2)}

**Source References ({len(all_sources)} sources):**
{json.dumps(all_sources[:20], indent=2)}
{revision_note}
**Iteration:** {context.iteration}

Create the structured report fields including executive summary, key insights, risks, recommendations, and source references. You do not need to write the full detailed report body yet (leave 'detailed_report' empty or short)."""

        logger.info("[summarizer] Generating metadata and summaries")
        meta_response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message_meta,
            api_keys=context.api_keys,
            temperature=0.5,
            max_tokens=4000,
        )

        data = meta_response["data"]

        # Step 2: Generate the detailed report sections in parallel for massive depth
        sections = [
            ("Background & Context", "Provide the historical context, foundational concepts, and initial status of the topic."),
            ("Key Findings", "Outline the core discoveries, primary data points, and confirmed facts."),
            ("Detailed Analysis", "Analyze the underlying mechanisms, technical parameters, and deep structural details. Build sub-sections using ###."),
            ("Trends & Patterns", "Discuss the chronological evolution, market direction, or future projections."),
            ("Risks & Considerations", "Highlight the potential risks, caveats, and data limitations of these findings."),
            ("Conclusion & Strategic Outlook", "Synthesize the findings into a strong concluding argument and forward-looking projection.")
        ]

        logger.info(f"[summarizer] Generating {len(sections)} report sections in parallel for maximum depth")

        async def generate_section(title: str, guidance: str) -> str:
            system_prompt = f"""You are an expert academic writer and senior research analyst.
Your task is to write a highly detailed, professional, and comprehensive research paper section under the heading: "## {title}".

Guidance for this section: {guidance}

**Original Query:** {context.query}
**Research Analysis:**
{json.dumps(analysis, indent=2)}

**Top Findings & Evidence:**
{json.dumps(all_sources[:15], indent=2)}

**Instructions:**
1. Write a minimum of 400-600 words of dense, multi-paragraph text for this section.
2. DO NOT use generic summaries or brief bullet points. Write full, authoritative, and academic paragraphs.
3. Cite sources continuously using `[Source N]` or `[1]`, `[2]` format referencing the source references.
4. If subheaders are needed, use `###`.
5. Return ONLY the raw markdown content for this section. Do not wrap in JSON or markdown code blocks. Just start writing the section text."""

            try:
                response = await call_llm(
                    model=context.model,
                    system_prompt=system_prompt,
                    user_message=f"Write the detailed section: {title}",
                    api_keys=context.api_keys,
                    temperature=0.5,
                    max_tokens=3000,
                )
                return f"## {title}\n\n{response.content.strip()}\n\n"
            except Exception as e:
                logger.error(f"Failed to generate section '{title}': {e}")
                return f"## {title}\n\n*Failed to generate this section due to an error: {e}*\n\n"

        # Run section generations concurrently
        section_tasks = [generate_section(title, guidance) for title, guidance in sections]
        section_results = await asyncio.gather(*section_tasks)

        # Assemble the full detailed report markdown
        data["detailed_report"] = "".join(section_results)
        
        # Calculate new word count metadata
        word_count = len(data["detailed_report"].split())
        data["metadata"] = {
            "word_count": word_count,
            "reading_time_minutes": max(1, word_count // 200),
            "confidence_score": data.get("metadata", {}).get("confidence_score", 0.85)
        }

        logger.info(f"[summarizer] Successfully assembled detailed report containing {word_count} words")

        return AgentResult(
            agent_type=self.agent_type,
            status="completed",
            output=data,
            tokens_input=meta_response["tokens_input"],
            tokens_output=meta_response["tokens_output"],
            cost_estimate=meta_response["cost_estimate"],
            model_used=meta_response["model"],
        )
