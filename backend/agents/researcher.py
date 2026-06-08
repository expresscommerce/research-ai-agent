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

        # Find query generator output in previous findings (if present)
        query_gen_output = {}
        for finding in context.previous_findings:
            if isinstance(finding, dict) and ("tavily_queries" in finding or "ddg_queries" in finding or "arxiv_queries" in finding):
                query_gen_output = finding
                break

        tavily_queries = query_gen_output.get("tavily_queries", queries)
        ddg_queries = query_gen_output.get("ddg_queries", queries)
        arxiv_queries = query_gen_output.get("arxiv_queries", queries)

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

        # Execute configured search engines in parallel
        search_results = []
        search_context_str = ""
        tasks = []

        # Tavily Search
        if settings.ENABLE_TAVILY and settings.TAVILY_API_KEY:
            async def run_tavily(q: str):
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.post(
                            "https://api.tavily.com/search",
                            json={
                                "api_key": settings.TAVILY_API_KEY,
                                "query": q,
                                "search_depth": "basic",
                                "include_answer": False,
                                "max_results": 2
                            }
                        )
                        if response.status_code == 200:
                            data = response.json()
                            results = data.get("results", [])
                            return [{"title": r.get("title"), "url": r.get("url"), "content": r.get("content"), "engine": "tavily"} for r in results]
                except Exception as ex:
                    logger.error(f"Tavily search failed for '{q}': {ex}")
                return []
            
            for q in tavily_queries[:2]:
                tasks.append(run_tavily(q))

        # DuckDuckGo Search
        if settings.ENABLE_DUCKDUCKGO:
            async def run_ddg(q: str):
                try:
                    from duckduckgo_search import DDGS
                    # Run ddgs search synchronously in executor to prevent blocking the async loop
                    def sync_search(query_str):
                        with DDGS() as ddgs:
                            return [r for r in ddgs.text(query_str, max_results=2)]
                    
                    loop = asyncio.get_running_loop()
                    results = await loop.run_in_executor(None, sync_search, q)
                    return [{"title": r.get("title"), "url": r.get("href"), "content": r.get("body"), "engine": "duckduckgo"} for r in results]
                except Exception as ex:
                    logger.error(f"DuckDuckGo search failed for '{q}': {ex}")
                return []

            for q in ddg_queries[:2]:
                tasks.append(run_ddg(q))

        # arXiv Academic Search
        if settings.ENABLE_ARXIV:
            async def run_arxiv(q: str):
                try:
                    import xml.etree.ElementTree as ET
                    url = f"http://export.arxiv.org/api/query?search_query=all:{q}&start=0&max_results=2"
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.get(url)
                        if response.status_code == 200:
                            root = ET.fromstring(response.content)
                            results = []
                            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                                title = entry.find("{http://www.w3.org/2005/Atom}title")
                                summary = entry.find("{http://www.w3.org/2005/Atom}summary")
                                url_id = entry.find("{http://www.w3.org/2005/Atom}id")
                                results.append({
                                    "title": title.text.strip().replace("\n", " ") if title is not None else "arXiv Article",
                                    "url": url_id.text.strip() if url_id is not None else "",
                                    "content": summary.text.strip().replace("\n", " ") if summary is not None else "",
                                    "engine": "arxiv"
                                })
                            return results
                except Exception as ex:
                    logger.error(f"arXiv search failed for '{q}': {ex}")
                return []

            for q in arxiv_queries[:2]:
                tasks.append(run_arxiv(q))

        # Run all searches concurrently
        if tasks:
            logger.info(f"[researcher] Running concurrent searches across enabled engines")
            results_lists = await asyncio.gather(*tasks)
            for sublist in results_lists:
                if sublist:
                    search_results.extend(sublist)

        # Build query context
        if search_results:
            search_context_str = "\n\n**Retrieved Search Results (Tavily, DuckDuckGo, and arXiv):**\n"
            for idx, res in enumerate(search_results, 1):
                search_context_str += f"- [{idx}] [{res.get('engine').upper()}] {res.get('title')} ({res.get('url')}): {res.get('content')}\n"
        else:
            logger.info("[researcher] No search results returned from any enabled engines. Simulating knowledge.")

        user_message = f"""Research the following topics thoroughly:

**Original Query:** {context.query}

**Sub-Topics to Cover:**
{json.dumps(sub_topics, indent=2)}

**Specific Research Queries:**
{json.dumps(queries, indent=2)}
{feedback_section}{search_context_str}

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
