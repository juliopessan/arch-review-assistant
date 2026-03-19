"""Core data models for Architecture Review Assistant."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(str, Enum):
    SECURITY = "security"
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"
    MAINTAINABILITY = "maintainability"
    PERFORMANCE = "performance"
    COST = "cost"
    OBSERVABILITY = "observability"
    MISSING_ADR = "missing_adr"
    TRADE_OFF = "trade_off"
    RISK = "risk"


class Finding(BaseModel):
    """A single finding from the architecture review."""

    title: str = Field(description="Short title of the finding")
    category: FindingCategory
    severity: Severity
    description: str = Field(description="Detailed description of the issue")
    affected_components: list[str] = Field(
        default_factory=list,
        description="Which components or layers are affected",
    )
    recommendation: str = Field(description="Concrete actionable recommendation")
    questions_to_ask: list[str] = Field(
        default_factory=list,
        description="Questions a senior architect would ask about this finding",
    )
    references: list[str] = Field(
        default_factory=list,
        description="Relevant patterns, papers, or docs",
    )


class ArchitectureInput(BaseModel):
    """Input provided by the user for review."""

    description: str = Field(description="Architecture description in text or Mermaid")
    context: str | None = Field(
        default=None,
        description="Business context, constraints, or goals",
    )
    input_format: str = Field(
        default="text",
        description="Format of input: text, mermaid, json",
    )
    focus_areas: list[FindingCategory] = Field(
        default_factory=list,
        description="Optional: focus the review on specific categories",
    )


class ReviewSummary(BaseModel):
    """High-level summary statistics of the review."""

    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    top_risk: str | None = None
    overall_assessment: str = Field(
        description="One-paragraph overall assessment"
    )


class AgentFocusPlan(BaseModel):
    """Manager-defined focus and priority for a single squad agent."""

    agent_name: str
    priority: str = Field(description="Priority level: critical, high, medium, or low")
    active: bool = True
    rationale: str = Field(default="", description="Why this agent was prioritized or skipped")
    focus_areas: list[str] = Field(
        default_factory=list,
        description="Specific focus directives injected into this agent",
    )


class OrchestrationPlanSnapshot(BaseModel):
    """Serializable snapshot of the Agent Manager orchestration plan."""

    architecture_type: str = Field(description="Manager's classification of the architecture")
    complexity: str = Field(description="Estimated complexity: low, medium, or high")
    compliance_flags: list[str] = Field(default_factory=list)
    cloud_providers: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)
    manager_briefing: str = Field(
        default="",
        description="Short summary of how the squad should approach this review",
    )
    agent_plans: list[AgentFocusPlan] = Field(default_factory=list)


class ReviewResult(BaseModel):
    """Complete result of an architecture review."""

    input: ArchitectureInput
    findings: list[Finding]
    summary: ReviewSummary
    senior_architect_questions: list[str] = Field(
        default_factory=list,
        description="High-level questions a senior architect would open the review with",
    )
    recommended_adrs: list[str] = Field(
        default_factory=list,
        description="Architectural decisions that should be documented as ADRs",
    )
    orchestration_plan: OrchestrationPlanSnapshot | None = None
    model_used: str
    review_version: str = "0.1.0"
