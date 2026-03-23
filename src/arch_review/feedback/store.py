"""FeedbackStore — per-domain approve/reject memory for the arch-review squad.

Module 09 pattern:
  - Max 30 entries per domain (FIFO) — prevents context explosion
  - Agents MUST consult before suggesting — no repeating rejected patterns
  - Consolidation cycle: every 30 reviews → lessons.md gets feedback patterns
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default feedback directory
DEFAULT_DIR = Path.home() / ".arch-review" / "feedback"

# Max entries per domain file (Module 09: FIFO 30)
MAX_ENTRIES = 30

# Map agent names → domain file names
AGENT_DOMAIN: dict[str, str] = {
    "security_agent":        "security",
    "reliability_agent":     "reliability",
    "cost_agent":            "cost",
    "observability_agent":   "observability",
    "scalability_agent":     "scalability",
    "performance_agent":     "performance",
    "maintainability_agent": "maintainability",
    "synthesizer_agent":     "synthesis",
}


class FeedbackDecision(str, Enum):
    APPROVE = "approve"
    REJECT  = "reject"


@dataclass
class FeedbackEntry:
    date:       str            # ISO date
    agent:      str            # agent_name
    finding:    str            # finding title
    category:   str            # finding category
    severity:   str            # finding severity
    decision:   str            # approve | reject
    reason:     str            # why (optional but recommended)
    tags:       list[str]      # extracted from category + severity

    @classmethod
    def create(
        cls,
        agent: str,
        finding: str,
        category: str,
        severity: str,
        decision: FeedbackDecision,
        reason: str = "",
    ) -> "FeedbackEntry":
        tags = [category, severity]
        if decision == FeedbackDecision.REJECT:
            tags.append("rejected")
        return cls(
            date=datetime.now().strftime("%Y-%m-%d"),
            agent=agent,
            finding=finding,
            category=category,
            severity=severity,
            decision=decision.value,
            reason=reason,
            tags=tags,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FeedbackEntry":
        return cls(**d)


class FeedbackStore:
    """Persistent feedback storage per domain.

    Usage:
        store = FeedbackStore()
        store.record("security_agent", "No HTTPS", "security", "critical",
                     FeedbackDecision.REJECT, "We already have mTLS everywhere")

        # Agent reads before prompting
        section = store.get_feedback_section("security_agent")
        # → injected into agent prompt as "## Your Feedback History"
    """

    def __init__(self, feedback_dir: Optional[Path] = None) -> None:
        self.dir = Path(feedback_dir) if feedback_dir else DEFAULT_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    # ── Core operations ────────────────────────────────────────────────────────

    def record(
        self,
        agent: str,
        finding: str,
        category: str,
        severity: str,
        decision: FeedbackDecision,
        reason: str = "",
    ) -> FeedbackEntry:
        """Record an approve/reject decision. Enforces FIFO-30."""
        entry = FeedbackEntry.create(agent, finding, category, severity, decision, reason)
        domain = AGENT_DOMAIN.get(agent, "general")
        entries = self._load(domain)

        # FIFO: remove oldest if at capacity
        entries.append(entry)
        if len(entries) > MAX_ENTRIES:
            removed = len(entries) - MAX_ENTRIES
            entries = entries[removed:]
            logger.debug("FeedbackStore: FIFO trimmed %d old entries for domain=%s", removed, domain)

        self._save(domain, entries)
        logger.info("Feedback recorded: %s → %s [%s]", finding[:40], decision.value, agent)
        return entry

    def get_entries(
        self,
        agent: str,
        decision: Optional[FeedbackDecision] = None,
        limit: int = MAX_ENTRIES,
    ) -> list[FeedbackEntry]:
        """Get feedback entries for an agent, optionally filtered by decision."""
        domain = AGENT_DOMAIN.get(agent, "general")
        entries = self._load(domain)
        if decision:
            entries = [e for e in entries if e.decision == decision.value]
        return entries[-limit:]

    def get_feedback_section(self, agent: str) -> str:
        """Format feedback as a prompt section for injection into agent prompts.

        Returns empty string if no feedback exists (clean slate).
        Rejected findings get priority — agents MUST avoid repeating these.
        """
        domain = AGENT_DOMAIN.get(agent, "general")
        entries = self._load(domain)
        if not entries:
            return ""

        rejected  = [e for e in entries if e.decision == FeedbackDecision.REJECT.value]
        approved  = [e for e in entries if e.decision == FeedbackDecision.APPROVE.value]

        lines: list[str] = ["## Feedback From Previous Reviews (consult BEFORE suggesting)"]

        if rejected:
            lines.append(
                "\n### ❌ REJECTED patterns — DO NOT suggest these again:"
            )
            for e in rejected[-10:]:  # last 10 rejected
                reason_str = f" — Reason: {e.reason}" if e.reason else ""
                lines.append(f"  - [{e.date}] \"{e.finding}\" ({e.category}/{e.severity}){reason_str}")

        if approved:
            lines.append(
                "\n### ✅ APPROVED patterns — these resonated well, look for similar issues:"
            )
            for e in approved[-5:]:  # last 5 approved
                reason_str = f" — {e.reason}" if e.reason else ""
                lines.append(f"  - [{e.date}] \"{e.finding}\" ({e.category}/{e.severity}){reason_str}")

        lines.append(
            "\nIMPORTANT: If a finding is similar to a REJECTED pattern, "
            "either skip it or explicitly explain why this instance is different."
        )
        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Summary stats across all domains."""
        total_approve = total_reject = 0
        domain_stats: dict[str, dict] = {}
        for domain in AGENT_DOMAIN.values():
            entries = self._load(domain)
            approved = sum(1 for e in entries if e.decision == FeedbackDecision.APPROVE.value)
            rejected = sum(1 for e in entries if e.decision == FeedbackDecision.REJECT.value)
            if entries:
                domain_stats[domain] = {
                    "total": len(entries),
                    "approved": approved,
                    "rejected": rejected,
                    "capacity": f"{len(entries)}/{MAX_ENTRIES}",
                }
            total_approve += approved
            total_reject  += rejected
        return {
            "total_entries": total_approve + total_reject,
            "total_approved": total_approve,
            "total_rejected": total_reject,
            "domains": domain_stats,
        }

    def export_for_consolidation(self) -> dict[str, list[dict]]:
        """Export all feedback for lesson consolidation (every 30 reviews)."""
        result: dict[str, list[dict]] = {}
        for domain in set(AGENT_DOMAIN.values()):
            entries = self._load(domain)
            if entries:
                result[domain] = [e.to_dict() for e in entries]
        return result

    def clear_domain(self, agent: str) -> int:
        """Clear feedback for a specific agent domain. Returns entries removed."""
        domain = AGENT_DOMAIN.get(agent, "general")
        entries = self._load(domain)
        count = len(entries)
        self._save(domain, [])
        return count

    # ── Internal I/O ──────────────────────────────────────────────────────────

    def _path(self, domain: str) -> Path:
        return self.dir / f"{domain}.json"

    def _load(self, domain: str) -> list[FeedbackEntry]:
        p = self._path(domain)
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text())
            return [FeedbackEntry.from_dict(e) for e in data.get("entries", [])]
        except Exception as exc:
            logger.warning("FeedbackStore: failed to load %s: %s", domain, exc)
            return []

    def _save(self, domain: str, entries: list[FeedbackEntry]) -> None:
        p = self._path(domain)
        try:
            p.write_text(json.dumps(
                {"entries": [e.to_dict() for e in entries], "max": MAX_ENTRIES},
                indent=2, ensure_ascii=False,
            ))
        except Exception as exc:
            logger.error("FeedbackStore: failed to save %s: %s", domain, exc)
