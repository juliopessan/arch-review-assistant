"""Agent Manager — pre-processes architecture and produces an orchestration plan.

Runs BEFORE the squad agents. Analyzes the architecture, context, and memory
to produce a tailored OrchestrationPlan that tells each agent:
- Whether to run (skip irrelevant agents)
- What priority/weight to apply
- What specific focus areas to emphasize
- What risks to pay extra attention to (from memory patterns)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import litellm

from arch_review.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)

# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class AgentDirective:
    """Instructions for a single agent from the Manager."""
    agent_name: str
    enabled: bool = True
    priority: str = "normal"          # "critical" | "high" | "normal" | "low"
    focus_note: str = ""              # Extra context the manager wants this agent to know
    skip_reason: str = ""             # Why the agent was disabled (if enabled=False)


@dataclass
class OrchestrationPlan:
    """Full plan produced by the Agent Manager before squad runs."""
    architecture_type: str            # e.g. "microservices", "monolith", "serverless"
    complexity: str                   # "low" | "medium" | "high"
    top_risks: list[str]              # Top 3 risks detected by the manager
    compliance_flags: list[str]       # e.g. ["LGPD", "PCI-DSS", "HIPAA"]
    cloud_providers: list[str]        # e.g. ["Azure", "AWS"]
    agent_directives: list[AgentDirective] = field(default_factory=list)
    manager_briefing: str = ""        # Overall briefing for the synthesizer
    manager_lesson: str = ""          # Lesson for manager memory after review

    def get_directive(self, agent_name: str) -> AgentDirective:
        for d in self.agent_directives:
            if d.agent_name == agent_name:
                return d
        return AgentDirective(agent_name=agent_name)  # default: enabled, normal

    @property
    def active_agents(self) -> list[str]:
        return [d.agent_name for d in self.agent_directives if d.enabled]

    @property
    def skipped_agents(self) -> list[str]:
        return [d.agent_name for d in self.agent_directives if not d.enabled]


# ── Manager system prompt ──────────────────────────────────────────────────────

MANAGER_SYSTEM = """\
You are the Agent Manager for a multi-agent architecture review system.
Your job is to ANALYZE the architecture BEFORE the specialist agents run,
and produce an orchestration plan that maximizes review quality and relevance.

You are NOT a reviewer. You are a meta-architect who decides HOW the review should happen.

You produce a JSON orchestration plan. You ALWAYS respond with valid JSON only."""

MANAGER_PROMPT = """\
Analyze this architecture and produce an orchestration plan for the review squad.

The squad has 4 specialist agents:
- security_agent: auth, secrets, compliance, attack vectors
- reliability_agent: SPOFs, resilience, cascading failures, RTO/RPO
- cost_agent: FinOps, right-sizing, data transfer, cloud economics
- observability_agent: logs, metrics, tracing, alerting, incident readiness

Return a JSON object with this exact schema:
{{
  "architecture_type": "string — e.g. microservices, monolith, serverless, hybrid",
  "complexity": "low | medium | high",
  "top_risks": ["up to 3 highest-level risks you spotted immediately"],
  "compliance_flags": ["any compliance regimes mentioned or implied, e.g. LGPD, GDPR, PCI-DSS, HIPAA, SOC2"],
  "cloud_providers": ["cloud providers detected, e.g. AWS, Azure, GCP, or on-prem"],
  "agent_directives": [
    {{
      "agent_name": "security_agent",
      "enabled": true,
      "priority": "critical | high | normal | low",
      "focus_note": "string — specific things this agent MUST look at in this architecture",
      "skip_reason": ""
    }},
    {{
      "agent_name": "reliability_agent",
      "enabled": true,
      "priority": "critical | high | normal | low",
      "focus_note": "string — specific reliability concerns for this architecture",
      "skip_reason": ""
    }},
    {{
      "agent_name": "cost_agent",
      "enabled": true,
      "priority": "critical | high | normal | low",
      "focus_note": "string — specific cost concerns, or skip if on-prem/no cloud",
      "skip_reason": "reason if enabled=false, else empty string"
    }},
    {{
      "agent_name": "observability_agent",
      "enabled": true,
      "priority": "critical | high | normal | low",
      "focus_note": "string — specific observability gaps to look for",
      "skip_reason": ""
    }}
  ],
  "manager_briefing": "string — key context for the Synthesizer about this architecture's most important characteristics",
  "manager_lesson": "string — one thing this architecture taught you that's worth remembering"
}}

Rules:
- Set an agent to enabled=false ONLY if it is completely irrelevant (e.g. cost_agent for an on-prem air-gapped system)
- priority=critical means this agent's domain is the most urgent concern for this architecture
- focus_note should be SPECIFIC — reference actual component names from the description
- compliance_flags should include anything implied, not just explicit mentions
- top_risks should be the 3 things that would hurt most in production
- Output ONLY the JSON, no preamble or markdown

ARCHITECTURE:
---
{architecture}
---

{context_section}
{patterns_section}"""


# ── Agent Manager class ────────────────────────────────────────────────────────

class AgentManager:
    """
    Runs before the ReviewSquad to analyze the architecture and produce
    an OrchestrationPlan. The plan tells each agent what to focus on,
    which agents are most critical, and which (if any) to skip.

    This is the pre-processor that makes the squad smarter and more targeted.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.1,   # Low temp — we want consistent analysis
        max_tokens: int = 2048,
        memory_dir: "Path | None" = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        from arch_review.squad.memory import AgentMemory, DEFAULT_MEMORY_DIR
        from pathlib import Path
        self._memory = AgentMemory("manager_agent", memory_dir or DEFAULT_MEMORY_DIR)

    def analyze(
        self,
        architecture: str,
        context: str = "",
        squad_patterns: str = "",
    ) -> OrchestrationPlan:
        """Analyze architecture and return an orchestration plan."""
        prompt = MANAGER_PROMPT.format(
            architecture=architecture,
            context_section=f"CONTEXT:\n{context}" if context else "",
            patterns_section=f"\nRECURRING PATTERNS FROM PAST REVIEWS (high priority):\n{squad_patterns}" if squad_patterns else "",
        )

        # Inject manager's own lessons
        lessons = self._memory.get_lessons_section()
        if lessons:
            prompt += f"\n\nYOUR PAST LESSONS (apply these):\n{lessons}"

        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": MANAGER_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            raw = response.choices[0].message.content or ""
            data = parse_llm_json(raw, context="AgentManager")
            plan = self._build_plan(data)
            logger.info(
                "AgentManager: %s/%s agents active, top_risks=%s",
                len(plan.active_agents), 4, plan.top_risks[:1],
            )
            return plan

        except Exception as exc:
            logger.error("AgentManager failed: %s — using default plan", exc)
            return self._default_plan()

    def record_lesson(self, lesson: str, arch_summary: str) -> None:
        """Record a lesson after review completes."""
        if lesson:
            self._memory.append_lesson(lesson, review_context=arch_summary)

    def _build_plan(self, data: dict[str, Any]) -> OrchestrationPlan:
        directives = []
        for d in data.get("agent_directives", []):
            directives.append(AgentDirective(
                agent_name=d.get("agent_name", ""),
                enabled=d.get("enabled", True),
                priority=d.get("priority", "normal"),
                focus_note=d.get("focus_note", ""),
                skip_reason=d.get("skip_reason", ""),
            ))

        # Ensure all 4 agents have a directive (fill missing with defaults)
        existing = {d.agent_name for d in directives}
        for name in ["security_agent","reliability_agent","cost_agent","observability_agent"]:
            if name not in existing:
                directives.append(AgentDirective(agent_name=name))

        return OrchestrationPlan(
            architecture_type=data.get("architecture_type", "unknown"),
            complexity=data.get("complexity", "medium"),
            top_risks=data.get("top_risks", []),
            compliance_flags=data.get("compliance_flags", []),
            cloud_providers=data.get("cloud_providers", []),
            agent_directives=directives,
            manager_briefing=data.get("manager_briefing", ""),
            manager_lesson=data.get("manager_lesson", ""),
        )

    def _default_plan(self) -> OrchestrationPlan:
        """Fallback plan when manager LLM call fails — enable all agents normally."""
        return OrchestrationPlan(
            architecture_type="unknown",
            complexity="medium",
            top_risks=[],
            compliance_flags=[],
            cloud_providers=[],
            agent_directives=[
                AgentDirective(agent_name="security_agent"),
                AgentDirective(agent_name="reliability_agent"),
                AgentDirective(agent_name="cost_agent"),
                AgentDirective(agent_name="observability_agent"),
            ],
            manager_briefing="",
        )
