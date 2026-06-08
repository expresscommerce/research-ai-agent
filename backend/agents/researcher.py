"""
Researcher Agent — gathers information using LLM knowledge simulation.
"""

from __future__ import annotations

import json
import logging
import asyncio
import httpx

from agents.base_agent import BaseAgent, AgentContext, AgentResult
from agents.llm_provider import call_llm_json
from app.config import settings

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    agent_type = "researcher"

    async def execute(self, context: AgentContext) -> AgentResult:
        # Build research context from plan
        plan = context.previous_findings[0] if context.previous_findings else {}
        sub_topics = plan.get("sub_topics", [])
        queries = plan.get("research_queries", [])

        # Include critic feedback for targeted follow-up
        feedback_section = ""
        if context.critic_feedback:
            follow_ups = context.critic_feedback.get("follow_up_queries", [])
            if follow_ups:
                feedback_section = f"""

**IMPORTANT — Critic Feedback (address these gaps):**
Follow-up queries to investigate:
{json.dumps(follow_ups, indent=2)}

Previous weaknesses identified:
{json.dumps(context.critic_feedback.get('weaknesses', []), indent=2)}
"""

        # Web search via Tavily if configured
        tavily_api_key = settings.TAVILY_API_KEY
        search_results = []
        tavily_context = ""

        if tavily_api_key:
            logger.info(f"[researcher] Tavily API Key detected. Performing real web search for queries: {queries}")
            
            async def search_query(q: str):
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.post(
                            "https://api.tavily.com/search",
                            json={
                                "api_key": tavily_api_key,
                                "query": q,
                                "search_depth": "basic",
                                "include_answer": False,
                                "max_results": 3
                            }
                        )
                        if response.status_code == 200:
                            data = response.json()
                            return data.get("results", [])
                        else:
                            logger.error(f"Tavily search failed for '{q}': {response.status_code} {response.text}")
                except Exception as ex:
                    logger.error(f"Tavily search exception for '{q}': {ex}")
                return []

            tasks = [search_query(q) for q in queries[:3]]  # Limit to 3 queries to speed up context loading
            results_lists = await asyncio.gather(*tasks)
            for sublist in results_lists:
                if sublist:
                    search_results.extend(sublist)

            if search_results:
                tavily_context = "\n\n**Real Web Search Results (Tavily):**\n"
                for idx, res in enumerate(search_results, 1):
                    tavily_context += f"- [{idx}] {res.get('title')} ({res.get('url')}): {res.get('content')}\n"
        else:
            logger.info("[researcher] Tavily API Key not found. Falling back to LLM knowledge simulation.")

        user_message = f"""Research the following topics thoroughly:

**Original Query:** {context.query}

**Sub-Topics to Cover:**
{json.dumps(sub_topics, indent=2)}

**Specific Research Queries:**
{json.dumps(queries, indent=2)}
{feedback_section}{tavily_context}

**Iteration:** {context.iteration}

Provide comprehensive findings with sources, confidence scores, and identified gaps.
When real web search results are provided in the section above, prioritize summarizing and incorporating these real findings and citing their exact URLs. Do not invent simulated sources if real search results are present."""

        response = await call_llm_json(
            model=context.model,
            system_prompt=self.prompt_template,
            user_message=user_message,
            api_keys=context.api_keys,
            temperature=0.5,
            max_tokens=3000,
        )

        data = response["data"]

        # Extract sources for database storage
        sources = []
        for src in data.get("sources", []):
            sources.append({
                "title": src.get("title", "Unknown"),
                "url": src.get("url", ""),
                "content_snippet": src.get("snippet", ""),
                "relevance_score": src.get("relevance_score", 0.0),
                "source_type": src.get("type", "general"),
            })

        return AgentResult(
            agent_type=self.agent_type,
            status="completed",
            output=data,
            sources=sources,
            tokens_input=response["tokens_input"],
            tokens_output=response["tokens_output"],
            cost_estimate=response["cost_estimate"],
            model_used=response["model"],
        )
