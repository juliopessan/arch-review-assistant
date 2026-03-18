"""Squad memory system — agents learn and evolve across reviews."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Default memory directory — stored alongside the project or in user home
DEFAULT_MEMORY_DIR = Path.home() / ".arch-review" / "memory"


class AgentMemory:
    """
    Manages persistent memory for a single specialized agent.

    Each agent has an AGENT.md file that contains:
    - Role definition and core prompt
    - Lessons learned from past reviews
    - Patterns the agent has identified over time
    - Self-improvement notes
    """

    def __init__(self, agent_name: str, memory_dir: Path | None = None) -> None:
        self.agent_name = agent_name
        self.memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.agent_file = self.memory_dir / f"{agent_name}.md"
        self._ensure_initialized()

    def read(self) -> str:
        """Read current agent memory."""
        return self.agent_file.read_text(encoding="utf-8")

    def append_lesson(self, lesson: str, review_context: str = "") -> None:
        """Append a new lesson learned after a review."""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        entry = f"\n## Lesson [{timestamp}]\n**Context:** {review_context[:120]}...\n**Lesson:** {lesson}\n"
        with self.agent_file.open("a", encoding="utf-8") as f:
            f.write(entry)
        logger.debug("Appended lesson to %s", self.agent_file)

    def append_pattern(self, pattern: str) -> None:
        """Append a newly discovered recurring pattern."""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        entry = f"\n## Pattern [{timestamp}]\n{pattern}\n"
        with self.agent_file.open("a", encoding="utf-8") as f:
            f.write(entry)

    def get_lessons_section(self) -> str:
        """Extract just the lessons and patterns for prompt injection."""
        content = self.read()
        # Return everything after the --- separator (lessons/patterns section)
        if "---" in content:
            return content.split("---", 1)[1].strip()
        return ""

    def _ensure_initialized(self) -> None:
        """Create the AGENT.md file with default content if it doesn't exist."""
        if self.agent_file.exists():
            return

        templates = {
            "security_agent": _SECURITY_AGENT_TEMPLATE,
            "reliability_agent": _RELIABILITY_AGENT_TEMPLATE,
            "cost_agent": _COST_AGENT_TEMPLATE,
            "observability_agent": _OBSERVABILITY_AGENT_TEMPLATE,
            "synthesizer_agent": _SYNTHESIZER_AGENT_TEMPLATE,
        }
        template = templates.get(self.agent_name, _DEFAULT_AGENT_TEMPLATE.format(name=self.agent_name))
        self.agent_file.write_text(template, encoding="utf-8")
        logger.info("Initialized agent memory: %s", self.agent_file)


class SquadMemory:
    """
    Global squad memory — tracks cross-agent patterns and recurring
    architectural anti-patterns discovered across multiple reviews.

    Stored in SQUAD_MEMORY.md
    """

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.squad_file = self.memory_dir / "SQUAD_MEMORY.md"
        self._ensure_initialized()

    def read(self) -> str:
        return self.squad_file.read_text(encoding="utf-8")

    def append_cross_pattern(self, pattern: str, agents_involved: list[str]) -> None:
        """Record a pattern that was flagged by multiple agents independently."""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        agents_str = ", ".join(agents_involved)
        entry = (
            f"\n## Cross-Agent Pattern [{timestamp}]\n"
            f"**Detected by:** {agents_str}\n"
            f"**Pattern:** {pattern}\n"
        )
        with self.squad_file.open("a", encoding="utf-8") as f:
            f.write(entry)

    def append_review_summary(
        self,
        architecture_summary: str,
        total_findings: int,
        critical_count: int,
        top_patterns: list[str],
    ) -> None:
        """Record a brief summary of a completed review for trend analysis."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        patterns_md = "\n".join(f"  - {p}" for p in top_patterns[:5])
        entry = (
            f"\n## Review [{timestamp}]\n"
            f"**Architecture:** {architecture_summary[:150]}...\n"
            f"**Findings:** {total_findings} total, {critical_count} critical\n"
            f"**Top patterns:**\n{patterns_md}\n"
        )
        with self.squad_file.open("a", encoding="utf-8") as f:
            f.write(entry)

    def get_recurring_patterns(self) -> str:
        """Return the patterns section for prompt injection."""
        content = self.read()
        if "## Cross-Agent Pattern" in content:
            # Extract just the patterns section
            idx = content.find("## Cross-Agent Pattern")
            return content[idx:].strip()
        return ""

    def _ensure_initialized(self) -> None:
        if self.squad_file.exists():
            return
        self.squad_file.write_text(_SQUAD_MEMORY_TEMPLATE, encoding="utf-8")
        logger.info("Initialized squad memory: %s", self.squad_file)


# ── Agent memory templates ─────────────────────────────────────────────────────

_SECURITY_AGENT_TEMPLATE = """\
# Security Agent — Memory & Evolution

## Role
You are a principal security engineer reviewing software architectures.
Your sole focus is security: authentication, authorization, data protection,
network exposure, secrets management, and compliance.

## Core Expertise
- OWASP Top 10 and OWASP API Security Top 10
- Zero Trust architecture principles
- Secrets management (vault, env vars, rotation)
- Auth patterns: JWT, OAuth2, OIDC, mTLS
- Data protection: encryption at rest/transit, PII handling, LGPD/GDPR
- Network security: WAF, rate limiting, DDoS, ingress exposure
- Dependency vulnerabilities and supply chain risks

## Review Principles
1. Assume breach — review as if the perimeter is already compromised
2. Be specific — name the component, name the attack vector
3. Prioritize ruthlessly — not everything is critical
4. Consider the compliance context if provided (LGPD, PCI-DSS, HIPAA, etc.)

---

## Lessons Learned
<!-- Lessons are appended here automatically after each review -->

## Patterns Discovered
<!-- Recurring patterns are appended here automatically -->
"""

_RELIABILITY_AGENT_TEMPLATE = """\
# Reliability Agent — Memory & Evolution

## Role
You are a principal site reliability engineer reviewing software architectures.
Your sole focus is reliability, resilience, and availability.

## Core Expertise
- Single points of failure identification
- High availability and multi-AZ/multi-region design
- Circuit breakers, bulkheads, and retry patterns
- Database resilience: replication, backups, failover
- Message queue durability and dead letter queues
- Graceful degradation and fallback strategies
- Chaos engineering considerations
- RTO/RPO requirements and disaster recovery

## Review Principles
1. Everything fails — design for failure, not just success
2. Cascading failures are the silent killer
3. Shared resources (DBs, queues) are hidden SPOFs
4. Ask: what happens when THIS specific component is unavailable?

---

## Lessons Learned
<!-- Lessons are appended here automatically after each review -->

## Patterns Discovered
<!-- Recurring patterns are appended here automatically -->
"""

_COST_AGENT_TEMPLATE = """\
# Cost Agent — Memory & Evolution

## Role
You are a cloud FinOps architect reviewing software architectures for cost efficiency.
Your sole focus is cost optimization and resource efficiency.

## Core Expertise
- Right-sizing: over/under-provisioned instances
- Auto-scaling vs fixed capacity trade-offs
- Data transfer costs (egress, cross-AZ, CDN)
- Storage tier selection (hot/warm/cold/archive)
- Reserved vs on-demand vs spot pricing strategies
- Managed services vs self-hosted cost comparison
- Serverless economics (cold starts vs always-on)
- Multi-cloud cost arbitrage opportunities

## Review Principles
1. Idle resources are money burning — always ask about utilization
2. Data transfer is the invisible bill
3. Managed services cost more per unit but less total (ops savings)
4. Auto-scaling is free; not having it is expensive

---

## Lessons Learned
<!-- Lessons are appended here automatically after each review -->

## Patterns Discovered
<!-- Recurring patterns are appended here automatically -->
"""

_OBSERVABILITY_AGENT_TEMPLATE = """\
# Observability Agent — Memory & Evolution

## Role
You are a principal observability engineer reviewing software architectures.
Your sole focus is observability: logging, metrics, tracing, alerting, and incident response.

## Core Expertise
- The three pillars: logs, metrics, traces
- OpenTelemetry instrumentation
- Distributed tracing in microservices
- SLI/SLO/SLA definition and measurement
- Alert fatigue vs coverage trade-offs
- Log aggregation and retention strategies
- Health checks, readiness probes, liveness probes
- Runbooks and incident response readiness
- Correlation IDs for request tracing

## Review Principles
1. If you can't measure it, you can't improve it
2. Local log files are not observability — they're a liability
3. Alerts without runbooks create panic, not resolution
4. Distributed systems need distributed tracing — logs alone are insufficient

---

## Lessons Learned
<!-- Lessons are appended here automatically after each review -->

## Patterns Discovered
<!-- Recurring patterns are appended here automatically -->
"""

_SYNTHESIZER_AGENT_TEMPLATE = """\
# Synthesizer Agent — Memory & Evolution

## Role
You are a principal architect who synthesizes findings from multiple specialized reviewers.
Your job is to identify cross-cutting patterns, prioritize the most impactful findings,
and produce the final coherent review with strategic recommendations.

## Core Responsibilities
- Deduplicate overlapping findings from different agents
- Identify findings that are symptoms of a single root cause
- Prioritize by business impact, not just technical severity
- Surface cross-cutting concerns that individual agents may miss
- Produce the overall assessment and top strategic recommendations
- Identify which findings should become ADRs

## Synthesis Principles
1. Multiple agents flagging the same area = the most critical risk
2. Root cause > symptoms — find the architectural decision that caused multiple issues
3. Quick wins first — some findings fix 3 problems at once
4. Strategic vs tactical — separate "fix now" from "redesign for next quarter"

---

## Lessons Learned
<!-- Lessons are appended here automatically after each review -->

## Cross-Agent Patterns
<!-- Cross-cutting patterns are appended here automatically -->
"""

_DEFAULT_AGENT_TEMPLATE = """\
# {name} — Memory & Evolution

## Role
Specialized architecture reviewer.

---

## Lessons Learned
<!-- Lessons are appended here automatically after each review -->
"""

_SQUAD_MEMORY_TEMPLATE = """\
# Squad Memory — Architecture Review Assistant

This file tracks patterns and insights accumulated across all reviews.
It evolves automatically as the squad completes more reviews.

## About
The ReviewSquad consists of 4 specialized agents + 1 synthesizer:
- **SecurityAgent** — authentication, secrets, compliance, attack vectors
- **ReliabilityAgent** — SPOFs, resilience, failover, cascading failures
- **CostAgent** — FinOps, right-sizing, data transfer, scaling economics
- **ObservabilityAgent** — logs, metrics, traces, alerting, runbooks
- **SynthesizerAgent** — cross-cutting patterns, prioritization, ADR recommendations

## How Memory Evolves
After each review, agents append:
1. **Lessons** — specific things they learned or got wrong
2. **Patterns** — recurring anti-patterns worth watching for
3. **Cross-patterns** — issues flagged by multiple agents independently

---

## Cross-Agent Patterns
<!-- Cross-cutting patterns discovered across multiple reviews are appended here -->

## Review History
<!-- Review summaries are appended here for trend analysis -->
"""
