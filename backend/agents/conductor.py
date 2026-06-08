"""
Conductor — the main orchestrator that drives the full multi-agent research workflow.

Workflow: Plan → Research → Analyze → Summarize → Critique → (iterate if needed) → Final Report
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import AgentContext, AgentResult
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.analyzer import AnalyzerAgent
from agents.summarizer import SummarizerAgent
from agents.critic import CriticAgent
from agents.memory import MemoryManager
from app.config import settings
from app.models.agent_execution import AgentExecution
from app.models.research_session import ResearchSession
from app.models.source import ResearchSource
from app.models.report import Report
from app.models.log import ExecutionLog

logger = logging.getLogger(__name__)


class Conductor:
    """
    Orchestrates the multi-agent research workflow with iterative feedback loops.
    """

    def __init__(
        self,
        db: AsyncSession,
        session: ResearchSession,
        api_keys: dict[str, str],
        progress_callback: Optional[Callable] = None,
    ):
        self.db = db
        self.session = session
        self.api_keys = api_keys
        self.progress_callback = progress_callback

        # Initialize agents
        self.planner = PlannerAgent()
        self.researcher = ResearcherAgent()
        self.analyzer = AnalyzerAgent()
        self.summarizer = SummarizerAgent()
        self.critic = CriticAgent()

        # Initialize memory
        self.memory = MemoryManager(db, session.id)

        # Config
        self.model = session.config.get("model", settings.DEFAULT_MODEL)
        self.max_iterations = session.config.get("max_iterations", settings.MAX_ITERATIONS)
        self.quality_threshold = session.config.get("quality_threshold", settings.QUALITY_THRESHOLD)

    async def _log(self, message: str, level: str = "INFO", agent_type: str | None = None, data: dict | None = None, execution_id: uuid.UUID | None = None):
        """Write a log entry to the database."""
        log = ExecutionLog(
            session_id=self.session.id,
            execution_id=execution_id,
            level=level,
            agent_type=agent_type,
            message=message,
            data=data,
        )
        self.db.add(log)
        await self.db.flush()
        logger.log(getattr(logging, level, logging.INFO), f"[Session {self.session.id}] {message}")

    async def _notify(self, event: str, data: dict):
        """Send progress update via callback (for WebSocket)."""
        if self.progress_callback:
            try:
                await self.progress_callback({
                    "event": event,
                    "session_id": str(self.session.id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **data,
                })
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    async def _record_execution(
        self, result: AgentResult, iteration: int, input_data: dict
    ) -> AgentExecution:
        """Persist an agent execution to the database."""
        execution = AgentExecution(
            session_id=self.session.id,
            agent_type=result.agent_type,
            iteration=iteration,
            status=result.status,
            input_data=input_data,
            output_data=result.output,
            model_used=result.model_used,
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            cost_estimate=result.cost_estimate,
            duration_seconds=result.duration_seconds,
            completed_at=datetime.now(timezone.utc) if result.status == "completed" else None,
        )
        self.db.add(execution)
        await self.db.flush()

        # Save sources discovered by researcher
        if result.sources:
            for src in result.sources:
                source = ResearchSource(
                    session_id=self.session.id,
                    execution_id=execution.id,
                    title=src.get("title", "Unknown"),
                    url=src.get("url"),
                    content_snippet=src.get("content_snippet"),
                    relevance_score=src.get("relevance_score", 0.0),
                    source_type=src.get("source_type", "general"),
                )
                self.db.add(source)

        await self.db.flush()
        return execution

    async def _update_status(self, status: str):
        """Update the session status."""
        self.session.status = status
        self.session.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def run(self) -> Report:
        """Execute the full research workflow."""
        await self._log("Starting research workflow", agent_type="conductor")
        await self._update_status("planning")
        await self._notify("status_change", {"status": "planning", "message": "Starting research planning..."})

        try:
            # ═══════════════════════════════════════
            # Step 1: PLANNING
            # ═══════════════════════════════════════
            memory_context = await self.memory.recall_as_context()
            plan_context = AgentContext(
                session_id=self.session.id,
                query=self.session.query,
                model=self.model,
                api_keys=self.api_keys,
                memory=memory_context,
            )

            await self._notify("agent_start", {"agent": "planner", "message": "Analyzing research request..."})
            plan_result = await self.planner.run(plan_context)

            if plan_result.status == "failed":
                raise RuntimeError(f"Planner failed: {plan_result.error}")

            plan_exec = await self._record_execution(plan_result, 1, {"query": self.session.query})
            await self._log(f"Research plan created with {len(plan_result.output.get('sub_topics', []))} sub-topics", agent_type="planner", execution_id=plan_exec.id)
            await self._notify("agent_complete", {"agent": "planner", "message": "Research plan created", "data": {"sub_topics": len(plan_result.output.get("sub_topics", []))}})

            # Store plan in memory
            await self.memory.store("research_plan", json.dumps(plan_result.output), "decision")

            # Update session title from plan
            if plan_result.output.get("title"):
                self.session.title = plan_result.output["title"]

            # ═══════════════════════════════════════
            # Step 2: RESEARCH (+ iterative loop)
            # ═══════════════════════════════════════
            all_findings = [plan_result.output]  # Plan is the first "finding" (contains queries)
            analysis_result = None
            report_result = None
            critic_result_obj = None
            critic_feedback = {}
            critic_output = {}

            for iteration in range(1, self.max_iterations + 1):
                self.session.iteration_count = iteration
                await self._log(f"Starting iteration {iteration}/{self.max_iterations}", agent_type="conductor")

                # ── RESEARCH ──
                await self._update_status("researching")
                await self._notify("agent_start", {"agent": "researcher", "iteration": iteration, "message": f"Gathering information (iteration {iteration})..."})

                research_context = AgentContext(
                    session_id=self.session.id,
                    query=self.session.query,
                    model=self.model,
                    api_keys=self.api_keys,
                    iteration=iteration,
                    previous_findings=all_findings,
                    critic_feedback=critic_feedback,
                    memory=memory_context,
                )

                research_result = await self.researcher.run(research_context)
                if research_result.status == "failed":
                    await self._log(f"Researcher failed: {research_result.error}", level="ERROR", agent_type="researcher")
                    raise RuntimeError(f"Researcher failed: {research_result.error}")

                research_exec = await self._record_execution(research_result, iteration, {"queries": plan_result.output.get("research_queries", [])})
                all_findings.append(research_result.output)
                await self._notify("agent_complete", {"agent": "researcher", "iteration": iteration, "message": f"Found {len(research_result.output.get('findings', []))} findings"})

                # ── ANALYZE ──
                await self._update_status("analyzing")
                await self._notify("agent_start", {"agent": "analyzer", "iteration": iteration, "message": "Analyzing findings..."})

                analyze_context = AgentContext(
                    session_id=self.session.id,
                    query=self.session.query,
                    model=self.model,
                    api_keys=self.api_keys,
                    iteration=iteration,
                    previous_findings=all_findings,
                    critic_feedback=critic_feedback,
                    memory=memory_context,
                )

                analysis_result_obj = await self.analyzer.run(analyze_context)
                if analysis_result_obj.status == "failed":
                    raise RuntimeError(f"Analyzer failed: {analysis_result_obj.error}")

                await self._record_execution(analysis_result_obj, iteration, {"findings_count": len(all_findings)})
                analysis_result = analysis_result_obj.output
                await self._notify("agent_complete", {"agent": "analyzer", "iteration": iteration, "message": f"Identified {len(analysis_result.get('key_findings', []))} key findings"})

                # ── SUMMARIZE ──
                await self._update_status("summarizing")
                await self._notify("agent_start", {"agent": "summarizer", "iteration": iteration, "message": "Generating report..."})

                summarize_context = AgentContext(
                    session_id=self.session.id,
                    query=self.session.query,
                    model=self.model,
                    api_keys=self.api_keys,
                    iteration=iteration,
                    previous_findings=all_findings,
                    previous_analysis=analysis_result,
                    critic_feedback=critic_feedback,
                    memory=memory_context,
                )

                summary_result = await self.summarizer.run(summarize_context)
                if summary_result.status == "failed":
                    raise RuntimeError(f"Summarizer failed: {summary_result.error}")

                await self._record_execution(summary_result, iteration, {"analysis_keys": list(analysis_result.keys())})
                report_result = summary_result.output
                await self._notify("agent_complete", {"agent": "summarizer", "iteration": iteration, "message": "Report draft generated"})

                # ── CRITIQUE ──
                await self._update_status("reviewing")
                await self._notify("agent_start", {"agent": "critic", "iteration": iteration, "message": "Quality review in progress..."})

                critic_context = AgentContext(
                    session_id=self.session.id,
                    query=self.session.query,
                    model=self.model,
                    api_keys=self.api_keys,
                    iteration=iteration,
                    previous_findings=all_findings,
                    previous_analysis=analysis_result,
                    previous_report=report_result,
                    config={"max_iterations": self.max_iterations},
                    memory=memory_context,
                )

                critic_result_obj = await self.critic.run(critic_context)
                if critic_result_obj.status == "failed":
                    await self._log(f"Critic failed, accepting current report", level="WARN", agent_type="critic")
                    break

                await self._record_execution(critic_result_obj, iteration, {"report_length": len(str(report_result))})
                critic_output = critic_result_obj.output
                quality_score = critic_output.get("quality_score", 0)

                await self._log(
                    f"Critic score: {quality_score}/100 (threshold: {self.quality_threshold})",
                    agent_type="critic",
                    data={"score": quality_score, "verdict": critic_output.get("verdict")},
                )
                await self._notify("agent_complete", {
                    "agent": "critic",
                    "iteration": iteration,
                    "message": f"Quality score: {quality_score}/100",
                    "data": {"quality_score": quality_score, "verdict": critic_output.get("verdict")},
                })

                # Check if quality is sufficient
                if quality_score >= self.quality_threshold:
                    await self._log(f"Quality threshold met ({quality_score} >= {self.quality_threshold}), finalizing report", agent_type="conductor")
                    break

                # If not the last iteration, prepare feedback for next round
                if iteration < self.max_iterations:
                    critic_feedback = critic_output
                    await self._log(
                        f"Quality below threshold ({quality_score} < {self.quality_threshold}), starting iteration {iteration + 1}",
                        agent_type="conductor",
                        data={"feedback": critic_feedback},
                    )
                    await self._notify("feedback_loop", {
                        "iteration": iteration,
                        "quality_score": quality_score,
                        "message": f"Score {quality_score} below threshold {self.quality_threshold}. Improving...",
                        "needs_more_research": critic_output.get("needs_more_research", False),
                        "needs_reanalysis": critic_output.get("needs_reanalysis", False),
                    })
                else:
                    await self._log(f"Max iterations reached, finalizing with score {quality_score}", agent_type="conductor")

            # ═══════════════════════════════════════
            # Step 3: SAVE FINAL REPORT
            # ═══════════════════════════════════════
            confidence = critic_output.get("quality_score", 70) / 100.0 if critic_result_obj else 0.7

            report = Report(
                session_id=self.session.id,
                executive_summary=report_result.get("executive_summary", ""),
                detailed_report=report_result.get("detailed_report", ""),
                key_insights=report_result.get("key_insights", []),
                risks=report_result.get("risks", []),
                recommendations=report_result.get("recommendations", []),
                source_references=report_result.get("source_references", []),
                confidence_score=confidence,
                revision_number=self.session.iteration_count,
                critic_feedback=critic_output if critic_result_obj else None,
            )
            self.db.add(report)

            # Update session
            self.session.status = "completed"
            self.session.confidence_score = confidence
            self.session.completed_at = datetime.now(timezone.utc)

            await self.db.flush()
            await self._log("Research workflow completed successfully", agent_type="conductor", data={"confidence": confidence, "iterations": self.session.iteration_count})
            await self._notify("completed", {
                "message": "Research completed!",
                "confidence_score": confidence,
                "iterations": self.session.iteration_count,
                "report_id": str(report.id),
            })

            return report

        except Exception as e:
            self.session.status = "failed"
            self.session.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self._log(f"Workflow failed: {str(e)}", level="ERROR", agent_type="conductor")
            await self._notify("error", {"message": str(e)})
            raise
