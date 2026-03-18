"""ReviewSquad — 4 specialized agents running in parallel + synthesizer with memory."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm

from arch_review.models import (
    ArchitectureInput,
    Finding,
    FindingCategory,
    ReviewResult,
    ReviewSummary,
    Severity,
)
from arch_review.squad.memory import AgentMemory, SquadMemory
from arch_review.squad.prompts import (
    COST_SYSTEM,
    OBSERVABILITY_SYSTEM,
    RELIABILITY_SYSTEM,
    SECURITY_SYSTEM,
    SYNTHESIZER_SYSTEM,
    build_cost_prompt,
    build_observability_prompt,
    build_reliability_prompt,
    build_security_prompt,
    build_synthesizer_prompt,
)

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


class ReviewSquad:
    """
    Orchestrates 4 specialized agents running in parallel,
    followed by a synthesizer that produces the final review.

    Each agent:
    - Has its own AGENT.md memory file that persists across reviews
    - Loads its past lessons before each review
    - Appends new lessons after each review
    - Contributes to the shared SQUAD_MEMORY.md

    Architecture:
        [SecurityAgent] ─┐
        [ReliabilityAgent]─┤ parallel ──→ [SynthesizerAgent] → ReviewResult
        [CostAgent] ──────┤
        [ObservabilityAgent]─┘
    """

    AGENTS = [
        ("security_agent",      SECURITY_SYSTEM,      build_security_prompt),
        ("reliability_agent",   RELIABILITY_SYSTEM,   build_reliability_prompt),
        ("cost_agent",          COST_SYSTEM,           build_cost_prompt),
        ("observability_agent", OBSERVABILITY_SYSTEM,  build_observability_prompt),
    ]

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.2,
        max_tokens: int = 3000,
        memory_dir: Path | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_dir = memory_dir

        # Initialize memory for each agent + squad
        self.agent_memories = {
            name: AgentMemory(name, memory_dir)
            for name, _, _ in self.AGENTS
        }
        self.agent_memories["synthesizer_agent"] = AgentMemory("synthesizer_agent", memory_dir)
        self.squad_memory = SquadMemory(memory_dir)

    def review(self, arch_input: ArchitectureInput) -> ReviewResult:
        """Run the full squad review synchronously (wraps async internally)."""
        return asyncio.run(self._review_async(arch_input))

    async def _review_async(self, arch_input: ArchitectureInput) -> ReviewResult:
        architecture = arch_input.description
        context = arch_input.context or ""
        squad_patterns = self.squad_memory.get_recurring_patterns()

        # ── Phase 1: Run all 4 agents in parallel ──────────────────────────────
        logger.info("ReviewSquad: launching %d agents in parallel", len(self.AGENTS))

        tasks = [
            self._run_agent(
                agent_name=name,
                system_prompt=system,
                user_prompt=prompt_fn(
                    architecture,
                    context,
                    self.agent_memories[name].get_lessons_section(),
                    squad_patterns,
                ),
            )
            for name, system, prompt_fn in self.AGENTS
        ]

        agent_results: list[AgentResult] = await asyncio.gather(*tasks)

        # ── Phase 2: Collect all findings for synthesizer ──────────────────────
        all_raw_findings: list[dict[str, Any]] = []
        agent_insights: list[str] = []

        for result in agent_results:
            if result.error:
                logger.warning("Agent %s failed: %s", result.agent_name, result.error)
                continue
            all_raw_findings.extend(result.findings)
            if result.insight:
                agent_insights.append(f"[{result.agent_name}] {result.insight}")

        # ── Phase 3: Synthesizer ───────────────────────────────────────────────
        logger.info("ReviewSquad: running synthesizer on %d findings", len(all_raw_findings))

        synth_memory = self.agent_memories["synthesizer_agent"]
        synth_prompt = build_synthesizer_prompt(
            architecture=architecture,
            context=context,
            all_findings_json=json.dumps(all_raw_findings, indent=2),
            agent_insights=agent_insights,
            lessons=synth_memory.get_lessons_section(),
            squad_patterns=squad_patterns,
        )

        synth_result = await self._run_agent(
            agent_name="synthesizer_agent",
            system_prompt=SYNTHESIZER_SYSTEM,
            user_prompt=synth_prompt,
        )

        # ── Phase 4: Build ReviewResult ────────────────────────────────────────
        if synth_result.error or not synth_result.findings:
            # Fallback: use raw findings if synthesizer fails
            logger.warning("Synthesizer failed, using raw findings as fallback")
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

        return ReviewResult(
            input=arch_input,
            findings=findings,
            summary=summary,
            senior_architect_questions=senior_questions,
            recommended_adrs=recommended_adrs,
            model_used=f"squad:{self.model}",
        )

    async def _run_agent(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AgentResult:
        """Run a single agent asynchronously."""
        result = AgentResult(agent_name=agent_name)
        try:
            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            raw = response.choices[0].message.content or ""
            data = self._parse_json(raw, agent_name)

            result.findings = data.get("findings", [])
            result.insight = data.get("agent_insight", "")
            result.lesson = data.get("lesson_for_memory", "")

            # Stash full data on synthesizer for cross_patterns etc.
            result._raw_data = data  # type: ignore[attr-defined]

        except Exception as exc:
            logger.error("Agent %s error: %s", agent_name, exc)
            result.error = str(exc)

        return result

    def _parse_json(self, content: str, agent_name: str) -> dict[str, Any]:
        """Parse JSON, stripping markdown fences if present."""
        content = content.strip()
        if content.startswith("```"):
            content = "\n".join(
                line for line in content.split("\n")
                if not line.startswith("```")
            )
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("Agent %s returned invalid JSON: %s", agent_name, exc)
            return {"findings": [], "agent_insight": "", "lesson_for_memory": ""}

    def _build_findings(self, raw_findings: list[dict[str, Any]]) -> list[Finding]:
        """Convert raw dicts to typed Finding objects, sorted by severity."""
        findings = []
        seen_titles: set[str] = set()

        for raw in raw_findings:
            title = raw.get("title", "Untitled")
            # Simple deduplication by normalized title
            normalized = title.lower().strip()
            if normalized in seen_titles:
                continue
            seen_titles.add(normalized)

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

        severity_order = {
            Severity.CRITICAL: 0, Severity.HIGH: 1,
            Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4,
        }
        return sorted(findings, key=lambda f: severity_order[f.severity])

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
        """Update all agent memories and squad memory after a review."""
        # Update each specialized agent's memory
        for result in agent_results:
            if result.lesson and not result.error:
                mem = self.agent_memories.get(result.agent_name)
                if mem:
                    mem.append_lesson(result.lesson, review_context=arch_summary)

        # Update synthesizer memory
        if synth_lesson:
            self.agent_memories["synthesizer_agent"].append_lesson(
                synth_lesson, review_context=arch_summary
            )

        # Update squad memory with cross-patterns
        if cross_patterns:
            agents_involved = [r.agent_name for r in agent_results if not r.error]
            for pattern in cross_patterns:
                self.squad_memory.append_cross_pattern(pattern, agents_involved)

        # Record review in squad history
        top_patterns = cross_patterns[:3] if cross_patterns else []
        self.squad_memory.append_review_summary(
            architecture_summary=arch_summary,
            total_findings=summary.total_findings,
            critical_count=summary.critical_count,
            top_patterns=top_patterns,
        )

        logger.info(
            "ReviewSquad: memories updated — %d agent lessons, %d cross-patterns",
            sum(1 for r in agent_results if r.lesson),
            len(cross_patterns),
        )
