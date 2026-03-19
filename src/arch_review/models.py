"""Core data models for Architecture Review Assistant."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"


class FindingCategory(str, Enum):
    SECURITY        = "security"
    SCALABILITY     = "scalability"
    RELIABILITY     = "reliability"
    MAINTAINABILITY = "maintainability"
    PERFORMANCE     = "performance"
    COST            = "cost"
    OBSERVABILITY   = "observability"
    MISSING_ADR     = "missing_adr"
    TRADE_OFF       = "trade_off"
    RISK            = "risk"


class Finding(BaseModel):
    title:               str
    category:            FindingCategory
    severity:            Severity
    description:         str
    affected_components: list[str] = Field(default_factory=list)
    recommendation:      str
    questions_to_ask:    list[str] = Field(default_factory=list)
    references:          list[str] = Field(default_factory=list)


class ArchitectureInput(BaseModel):
    description:  str
    context:      Optional[str] = None
    input_format: str = "text"
    focus_areas:  list[FindingCategory] = Field(default_factory=list)


class ReviewSummary(BaseModel):
    total_findings:     int
    critical_count:     int
    high_count:         int
    medium_count:       int
    low_count:          int
    info_count:         int
    top_risk:           Optional[str] = None
    overall_assessment: str = ""


class OrchestrationPlanSnapshot(BaseModel):
    """Serializable snapshot of the Agent Manager orchestration plan."""
    architecture_type: str            = "unknown"
    complexity:        str            = "medium"
    top_risks:         list[str]      = Field(default_factory=list)
    compliance_flags:  list[str]      = Field(default_factory=list)
    cloud_providers:   list[str]      = Field(default_factory=list)
    manager_briefing:  str            = ""
    active_agents:     list[str]      = Field(default_factory=list)
    skipped_agents:    list[str]      = Field(default_factory=list)
    agent_priorities:  dict[str, str] = Field(default_factory=dict)
    agent_focus_notes: dict[str, str] = Field(default_factory=dict)


class AgentRunMetric(BaseModel):
    agent_name:     str
    phase:          str
    duration_s:     float        = 0.0
    tokens_in:      int          = 0
    tokens_out:     int          = 0
    findings_count: int          = 0
    error:          Optional[str] = None

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def cost_usd(self) -> float:
        return (self.tokens_in * 3.0 + self.tokens_out * 15.0) / 1_000_000


class RunMetrics(BaseModel):
    model_used:       str   = ""
    started_at:       str   = ""
    total_duration_s: float = 0.0
    phase_manager_s:  float = 0.0
    phase_parallel_s: float = 0.0
    phase_synth_s:    float = 0.0
    agents:           list[AgentRunMetric] = Field(default_factory=list)

    @property
    def tokens_total(self) -> int:
        return sum(a.tokens_total for a in self.agents)

    @property
    def tokens_in_total(self) -> int:
        return sum(a.tokens_in for a in self.agents)

    @property
    def tokens_out_total(self) -> int:
        return sum(a.tokens_out for a in self.agents)

    @property
    def cost_usd(self) -> float:
        return sum(a.cost_usd for a in self.agents)

    @property
    def findings_total(self) -> int:
        return sum(a.findings_count for a in self.agents if a.phase != "synthesizer")

    def roi_label(self, lang: str = "en") -> str:
        saved = max(0.0, 600.0 - self.cost_usd)
        ratio = saved / max(self.cost_usd, 0.001)
        if lang == "pt":
            return f"≈ ${saved:,.0f} economizados vs revisão manual ({ratio:.0f}x ROI)"
        return f"≈ ${saved:,.0f} saved vs manual review ({ratio:.0f}x ROI)"


class ReviewResult(BaseModel):
    input:                      ArchitectureInput
    findings:                   list[Finding]
    summary:                    ReviewSummary
    senior_architect_questions: list[str]                           = Field(default_factory=list)
    recommended_adrs:           list[str]                           = Field(default_factory=list)
    model_used:                 str
    review_version:             str                                 = "0.1.0"
    orchestration_plan:         Optional[OrchestrationPlanSnapshot] = None
    run_metrics:                Optional[RunMetrics]                = None
