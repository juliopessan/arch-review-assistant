"""ADR (Architecture Decision Record) data models."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ADRStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class ADROption(BaseModel):
    """A considered option/alternative in the ADR."""

    title: str
    description: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)


class ADR(BaseModel):
    """A single Architecture Decision Record following MADR format."""

    number: int = Field(description="Sequential ADR number, e.g. 001")
    title: str = Field(description="Short imperative phrase, e.g. 'Use Redis for session cache'")
    status: ADRStatus = ADRStatus.PROPOSED
    date: str = Field(default_factory=lambda: date.today().isoformat())
    context: str = Field(description="What is the issue motivating this decision?")
    decision_drivers: list[str] = Field(
        default_factory=list,
        description="Key forces, constraints, and quality attributes driving the decision",
    )
    considered_options: list[ADROption] = Field(
        default_factory=list,
        description="Options that were considered",
    )
    decision: str = Field(description="The chosen option and why")
    consequences_positive: list[str] = Field(
        default_factory=list,
        description="Good consequences of this decision",
    )
    consequences_negative: list[str] = Field(
        default_factory=list,
        description="Bad or risky consequences that need mitigation",
    )
    consequences_neutral: list[str] = Field(
        default_factory=list,
        description="Neutral consequences and follow-up actions",
    )
    links: list[str] = Field(
        default_factory=list,
        description="References, related ADRs, or relevant documents",
    )
    source_finding: str | None = Field(
        default=None,
        description="Title of the review finding that triggered this ADR",
    )


class ADRGenerationResult(BaseModel):
    """Result of generating ADRs from a review."""

    adrs: list[ADR]
    total_generated: int
    source: str = Field(description="What triggered generation: 'review' or 'manual'")
    model_used: str
