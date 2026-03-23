"""ReviewSquad — Agent Manager + 4 specialized agents + synthesizer."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm

from arch_review.models import (
    AgentRunMetric,
    ArchitectureInput,
    Finding,
    FindingCategory,
    OrchestrationPlanSnapshot,
    ReviewResult,
    ReviewSummary,
    RunMetrics,
    Severity,
)
from arch_review.squad.manager import AgentManager, OrchestrationPlan
from arch_review.squad.memory import AgentMemory, SquadMemory
from arch_review.squad.prompts import (
    COST_SYSTEM,
    MAINTAINABILITY_SYSTEM,
    OBSERVABILITY_SYSTEM,
    PERFORMANCE_SYSTEM,
    RELIABILITY_SYSTEM,
    SCALABILITY_SYSTEM,
    SECURITY_SYSTEM,
    SYNTHESIZER_SYSTEM,
    build_cost_prompt,
    build_maintainability_prompt,
    build_observability_prompt,
    build_performance_prompt,
    build_reliability_prompt,
    build_scalability_prompt,
    build_security_prompt,
    build_synthesizer_prompt,
)
from arch_review.utils.json_parser import parse_llm_json, sanitize_architecture_input

logger = logging.getLogger(__name__)

litellm.suppress_debug_info = True


@dataclass
class AgentResult:
    """Raw result from a single specialized agent."""
    agent_name: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    insight: str = ""
    lesson: str = ""
    error: str | None = None
    # Runtime telemetry
    duration_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0


class ReviewSquad:
    """
    Orchestrates the full review pipeline:

    Phase 0: Agent Manager — analyzes architecture, produces OrchestrationPlan
             (decides which agents run, at what priority, with what focus)

    Phase 1: Specialist Agents — run in parallel, guided by the plan
             (only enabled agents run; each receives manager's focus_note)

    Phase 2: Synthesizer — consolidates findings into final ReviewResult

    Phase 3: Memory — lessons + patterns saved for future reviews

    Architecture:
        [AgentManager] ──→ OrchestrationPlan
                                  │
              ┌───────────────────┼───────────────────┐
        [SecurityAgent]  [ReliabilityAgent]  [CostAgent]  [ObservabilityAgent]
              └───────────────────┼───────────────────┘
                                  │
                         [SynthesizerAgent]
                                  │
                           ReviewResult
    """

    AGENTS = [
        ("security_agent",        SECURITY_SYSTEM,        build_security_prompt),
        ("reliability_agent",     RELIABILITY_SYSTEM,     build_reliability_prompt),
        ("cost_agent",            COST_SYSTEM,             build_cost_prompt),
        ("observability_agent",   OBSERVABILITY_SYSTEM,   build_observability_prompt),
        ("scalability_agent",     SCALABILITY_SYSTEM,     build_scalability_prompt),
        ("performance_agent",     PERFORMANCE_SYSTEM,     build_performance_prompt),
        ("maintainability_agent", MAINTAINABILITY_SYSTEM, build_maintainability_prompt),
    ]

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.2,
        max_tokens: int = 4500,
        memory_dir: Path | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_dir = memory_dir

        # Load installed skills and extend AGENTS dynamically
        from arch_review.skills import SkillRegistry
        registry = SkillRegistry()
        skill_agents = [s.as_agent_tuple for s in registry.load_all_installed()]
        self._active_agents = list(self.AGENTS) + skill_agents

        self.agent_memories = {
            name: AgentMemory(name, memory_dir)
            for name, _, _ in self._active_agents
        }
        self.agent_memories["synthesizer_agent"] = AgentMemory("synthesizer_agent", memory_dir)
        self.agent_memories["manager_agent"]     = AgentMemory("manager_agent",     memory_dir)
        self.squad_memory = SquadMemory(memory_dir)
        self.manager = AgentManager(model=model, memory_dir=memory_dir)

        if skill_agents:
            logger.info(
                "ReviewSquad: %d skill agent(s) loaded: %s",
                len(skill_agents),
                [a[0] for a in skill_agents],
            )

    def review(self, arch_input: ArchitectureInput) -> ReviewResult:
        """Run the full managed squad review synchronously."""
        return asyncio.run(self._review_async(arch_input))

    async def _review_async(self, arch_input: ArchitectureInput) -> ReviewResult:
        import time
        from datetime import datetime, timezone

        architecture = sanitize_architecture_input(arch_input.description)
        context = arch_input.context or ""
        squad_patterns = self.squad_memory.get_recurring_patterns()

        review_started = time.monotonic()
        started_at_iso = datetime.now(timezone.utc).isoformat()

        # ── Phase 0: Agent Manager ─────────────────────────────────────────────
        logger.info("ReviewSquad: Agent Manager analyzing architecture...")
        t_mgr_start = time.monotonic()
        plan: OrchestrationPlan = await asyncio.to_thread(
            self.manager.analyze,
            architecture,
            context,
            squad_patterns,
        )
        t_mgr_end = time.monotonic()
        phase_manager_s = t_mgr_end - t_mgr_start
        logger.info(
            "Plan: type=%s complexity=%s active=%s skipped=%s compliance=%s",
            plan.architecture_type, plan.complexity,
            plan.active_agents, plan.skipped_agents, plan.compliance_flags,
        )

        # ── Phase 1: Run enabled agents in parallel ────────────────────────────
        active_agents = [
            (name, system, prompt_fn)
            for name, system, prompt_fn in self._active_agents
            if plan.get_directive(name).enabled
        ]
        logger.info("ReviewSquad: launching %d/%d agents", len(active_agents), len(self._active_agents))

        tasks = [
            self._run_agent(
                agent_name=name,
                system_prompt=system,
                user_prompt=self._build_agent_prompt(
                    name, prompt_fn, architecture, context, plan
                ),
            )
            for name, system, prompt_fn in active_agents
        ]

        t_parallel_start = time.monotonic()
        agent_results: list[AgentResult] = await asyncio.gather(*tasks)
        phase_parallel_s = time.monotonic() - t_parallel_start

        # ── Phase 2: Collect findings for synthesizer ──────────────────────────
        all_raw_findings: list[dict[str, Any]] = []
        agent_insights: list[str] = []

        for result in agent_results:
            if result.error:
                logger.warning("Agent %s failed: %s", result.agent_name, result.error)
                continue
            all_raw_findings.extend(result.findings)
            if result.insight:
                agent_insights.append(f"[{result.agent_name}] {result.insight}")

        if plan.manager_briefing:
            agent_insights.insert(0, f"[manager] {plan.manager_briefing}")

        # ── Phase 3: Synthesizer ───────────────────────────────────────────────
        logger.info("ReviewSquad: synthesizer consolidating %d findings", len(all_raw_findings))

        synth_memory = self.agent_memories["synthesizer_agent"]
        plan_context = self._format_plan_context(plan)
        synth_prompt = build_synthesizer_prompt(
            architecture=architecture,
            context=context + ("\n\n" + plan_context if plan_context else ""),
            all_findings_json=json.dumps(all_raw_findings, indent=2),
            agent_insights=agent_insights,
            lessons=synth_memory.get_lessons_section(),
            squad_patterns=squad_patterns,
        )

        t_synth_start = time.monotonic()
        synth_result = await self._run_agent(
            agent_name="synthesizer_agent",
            system_prompt=SYNTHESIZER_SYSTEM,
            user_prompt=synth_prompt,
        )
        phase_synth_s = time.monotonic() - t_synth_start

        total_duration_s = time.monotonic() - review_started

        # ── Phase 4: Build ReviewResult ────────────────────────────────────────
        if synth_result.error or not synth_result.findings:
            logger.warning("Synthesizer failed — using raw findings as fallback")
            final_findings_raw = all_raw_findings
            overall_assessment = "Review completed with partial synthesis."
            senior_questions: list[str] = []
            recommended_adrs: list[str] = []
            cross_patterns: list[str] = []
            synth_lesson = ""
        else:
            final_findings_raw = synth_result.findings
            synth_data = getattr(synth_result, "_raw_data", {})
            overall_assessment = synth_data.get("overall_assessment", "")
            senior_questions = synth_data.get("senior_architect_questions", [])
            recommended_adrs = synth_data.get("recommended_adrs", [])
            cross_patterns = synth_data.get("cross_patterns", [])
            synth_lesson = synth_result.lesson

        findings = self._build_findings(final_findings_raw)
        summary = self._build_summary(findings, overall_assessment)

        # ── Phase 5: Update memories ───────────────────────────────────────────
        arch_summary = architecture[:100]
        self._update_memories(agent_results, synth_lesson, arch_summary, cross_patterns, summary)
        self.manager.record_lesson(plan.manager_lesson, arch_summary)

        # ── Build RunMetrics ───────────────────────────────────────────────────
        agent_metrics: list[AgentRunMetric] = []

        # Manager (no token data available since we use asyncio.to_thread directly)
        agent_metrics.append(AgentRunMetric(
            agent_name="manager_agent",
            phase="manager",
            duration_s=round(phase_manager_s, 2),
            tokens_in=0, tokens_out=0,
            findings_count=0,
            model_used=self.model,
        ))

        # Specialist agents (parallel phase)
        for ar in agent_results:
            agent_metrics.append(AgentRunMetric(
                agent_name=ar.agent_name,
                phase="parallel",
                duration_s=round(ar.duration_s, 2),
                tokens_in=ar.tokens_in,
                tokens_out=ar.tokens_out,
                findings_count=len(ar.findings),
                error=ar.error,
                model_used=self.model,
            ))

        # Synthesizer
        agent_metrics.append(AgentRunMetric(
            agent_name="synthesizer_agent",
            phase="synthesizer",
            duration_s=round(synth_result.duration_s, 2),
            tokens_in=synth_result.tokens_in,
            tokens_out=synth_result.tokens_out,
            findings_count=len(synth_result.findings),
            error=synth_result.error,
            model_used=self.model,
        ))

        run_metrics = RunMetrics(
            model_used=self.model,
            started_at=started_at_iso,
            total_duration_s=round(total_duration_s, 2),
            phase_manager_s=round(phase_manager_s, 2),
            phase_parallel_s=round(phase_parallel_s, 2),
            phase_synth_s=round(phase_synth_s, 2),
            agents=agent_metrics,
        )

        # Build serializable plan snapshot
        plan_snapshot = OrchestrationPlanSnapshot(
            architecture_type=plan.architecture_type,
            complexity=plan.complexity,
            top_risks=plan.top_risks,
            compliance_flags=plan.compliance_flags,
            cloud_providers=plan.cloud_providers,
            manager_briefing=plan.manager_briefing,
            active_agents=plan.active_agents,
            skipped_agents=plan.skipped_agents,
            agent_priorities={d.agent_name: d.priority for d in plan.agent_directives},
            agent_focus_notes={d.agent_name: d.focus_note for d in plan.agent_directives if d.focus_note},
        )

        return ReviewResult(
            input=arch_input,
            findings=findings,
            summary=summary,
            senior_architect_questions=senior_questions,
            recommended_adrs=recommended_adrs,
            model_used=f"squad:{self.model}",
            orchestration_plan=plan_snapshot,
            run_metrics=run_metrics,
        )

    def _build_agent_prompt(
        self,
        agent_name: str,
        prompt_fn: Any,
        architecture: str,
        context: str,
        plan: OrchestrationPlan,
    ) -> str:
        """Build agent prompt enriched with manager's focus_note + feedback history."""
        from arch_review.feedback.store import FeedbackStore
        directive = plan.get_directive(agent_name)

        # Inject manager's focus note into context
        enriched_context = context
        if directive.focus_note:
            enriched_context = (
                f"{context}\n\n"
                f"[MANAGER BRIEFING FOR {agent_name.upper()}]\n"
                f"Priority: {directive.priority.upper()}\n"
                f"Focus on: {directive.focus_note}"
            ).strip()

        # Add compliance flags to security agent
        if agent_name == "security_agent" and plan.compliance_flags:
            flags = ", ".join(plan.compliance_flags)
            enriched_context += f"\n\nCompliance regimes detected: {flags}. Pay extra attention."

        # Inject feedback history (Module 09: agents consult before suggesting)
        feedback_store = FeedbackStore(self.memory_dir)
        feedback_section = feedback_store.get_feedback_section(agent_name)

        lessons = self.agent_memories[agent_name].get_lessons_section()
        if feedback_section:
            lessons = f"{feedback_section}\n\n{lessons}" if lessons else feedback_section

        return prompt_fn(
            architecture,
            enriched_context,
            lessons,
            self.squad_memory.get_recurring_patterns(),
        )

    def _format_plan_context(self, plan: OrchestrationPlan) -> str:
        """Format plan metadata as context for the synthesizer."""
        lines = [
            f"[AGENT MANAGER ANALYSIS]",
            f"Architecture type: {plan.architecture_type}",
            f"Complexity: {plan.complexity}",
        ]
        if plan.top_risks:
            lines.append(f"Top risks identified: {'; '.join(plan.top_risks)}")
        if plan.compliance_flags:
            lines.append(f"Compliance: {', '.join(plan.compliance_flags)}")
        if plan.cloud_providers:
            lines.append(f"Cloud: {', '.join(plan.cloud_providers)}")
        if plan.skipped_agents:
            lines.append(f"Skipped agents: {', '.join(plan.skipped_agents)} (irrelevant for this architecture)")
        return "\n".join(lines)

    async def _run_agent(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AgentResult:
        result = AgentResult(agent_name=agent_name)
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        try:
            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            result.duration_s = loop.time() - t0
            # Capture token usage from response
            usage = getattr(response, "usage", None)
            if usage:
                result.tokens_in  = getattr(usage, "prompt_tokens", 0) or 0
                result.tokens_out = getattr(usage, "completion_tokens", 0) or 0
            raw = response.choices[0].message.content or ""
            data = self._parse_json(raw, agent_name)
            result.findings = data.get("findings", [])
            result.insight  = data.get("agent_insight", "")
            result.lesson   = data.get("lesson_for_memory", "")
            result._raw_data = data  # type: ignore[attr-defined]
        except Exception as exc:
            result.duration_s = loop.time() - t0
            logger.error("Agent %s error: %s", agent_name, exc)
            result.error = str(exc)
        return result

    def _parse_json(self, content: str, agent_name: str) -> dict[str, Any]:
        try:
            return parse_llm_json(content, context=agent_name)
        except ValueError:
            return {"findings": [], "agent_insight": "", "lesson_for_memory": ""}

    def _build_findings(self, raw_findings: list[dict[str, Any]]) -> list[Finding]:
        findings = []
        seen: set[str] = set()
        for raw in raw_findings:
            title = raw.get("title", "Untitled")
            norm  = title.lower().strip()
            if norm in seen:
                continue
            seen.add(norm)
            try:
                findings.append(Finding(
                    title=title,
                    category=FindingCategory(raw.get("category", "risk")),
                    severity=Severity(raw.get("severity", "medium")),
                    description=raw.get("description", ""),
                    affected_components=raw.get("affected_components", []),
                    recommendation=raw.get("recommendation", ""),
                    questions_to_ask=raw.get("questions_to_ask", []),
                    references=raw.get("references", []),
                ))
            except Exception as exc:
                logger.warning("Skipping malformed finding '%s': %s", title, exc)

        order = {Severity.CRITICAL:0,Severity.HIGH:1,Severity.MEDIUM:2,Severity.LOW:3,Severity.INFO:4}
        return sorted(findings, key=lambda f: order[f.severity])

    def _build_summary(self, findings: list[Finding], overall_assessment: str) -> ReviewSummary:
        counts = {s: 0 for s in Severity}
        for f in findings:
            counts[f.severity] += 1
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        return ReviewSummary(
            total_findings=len(findings),
            critical_count=counts[Severity.CRITICAL],
            high_count=counts[Severity.HIGH],
            medium_count=counts[Severity.MEDIUM],
            low_count=counts[Severity.LOW],
            info_count=counts[Severity.INFO],
            top_risk=critical[0].title if critical else None,
            overall_assessment=overall_assessment,
        )

    def _update_memories(
        self,
        agent_results: list[AgentResult],
        synth_lesson: str,
        arch_summary: str,
        cross_patterns: list[str],
        summary: ReviewSummary,
    ) -> None:
        for result in agent_results:
            if result.lesson and not result.error:
                mem = self.agent_memories.get(result.agent_name)
                if mem:
                    mem.append_lesson(result.lesson, review_context=arch_summary)
        if synth_lesson:
            self.agent_memories["synthesizer_agent"].append_lesson(synth_lesson, review_context=arch_summary)
        if cross_patterns:
            agents_involved = [r.agent_name for r in agent_results if not r.error]
            for pattern in cross_patterns:
                self.squad_memory.append_cross_pattern(pattern, agents_involved)
        self.squad_memory.append_review_summary(
            architecture_summary=arch_summary,
            total_findings=summary.total_findings,
            critical_count=summary.critical_count,
            top_patterns=cross_patterns[:3],
        )
        logger.info(
            "Memories updated — %d lessons, %d cross-patterns",
            sum(1 for r in agent_results if r.lesson), len(cross_patterns),
        )

