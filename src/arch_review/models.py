"""Core data models for Architecture Review Assistant."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Model pricing table (USD per 1M tokens) ────────────────────────────────────
# Format: "model_id_substring": (input_price, output_price)
# Matched via substring so partial model IDs work (e.g. "sonnet-4" matches all variants)
# Prices updated March 2026. Free models (OpenRouter :free) have 0 cost.
_MODEL_PRICING: list[tuple[str, float, float]] = [
    # Anthropic
    ("claude-opus-4",     15.00, 75.00),
    ("claude-sonnet-4",    3.00, 15.00),
    ("claude-haiku-4",     0.80,  4.00),
    # OpenAI
    ("gpt-5.4-nano",     0.20,  1.25),   # Ultra-cheap OCR / high-volume pipelines
    ("gpt-4o-mini",      0.15,  0.60),
    ("gpt-4o",           2.50, 10.00),
    # Google Gemini 3.x
    ("gemini-3.1-pro",     3.50, 10.50),
    ("gemini-3.1-flash",   0.30,  2.50),
    # Google Gemini 2.5
    ("gemini-2.5-pro",     1.25, 10.00),
    ("gemini-2.5-flash-lite", 0.10, 0.40),
    ("gemini-2.5-flash",   0.30,  2.50),
    # Mistral
    ("mistral-large",      2.00,  6.00),
    # OpenRouter — Chinese free models (zero cost)
    (":free",              0.00,  0.00),
    # Ollama (local — zero API cost)
    ("ollama/",            0.00,  0.00),
]

_DEFAULT_PRICING = (3.00, 15.00)  # fallback: claude-sonnet-4 pricing


def _model_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost in USD for given model and token counts."""
    model_lower = model.lower()
    for fragment, price_in, price_out in _MODEL_PRICING:
        if fragment in model_lower:
            return (tokens_in * price_in + tokens_out * price_out) / 1_000_000
    p_in, p_out = _DEFAULT_PRICING
    return (tokens_in * p_in + tokens_out * p_out) / 1_000_000


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
    model_used:     str          = ""   # populated from ReviewSquad.model

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def cost_usd(self) -> float:
        return _model_cost(self.model_used, self.tokens_in, self.tokens_out)


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
        cost = self.cost_usd
        baseline = 600.0
        saved = max(0.0, baseline - cost)
        if cost <= 0.0:
            return "Free run — $600 saved vs manual review" if lang == "en" \
                else "Execução gratuita — $600 economizados vs revisão manual"
        ratio = saved / cost
        ratio_str = f"{ratio/1000:.1f}k x" if ratio >= 1000 else f"{ratio:.0f}x"
        if lang == "pt":
            return f"≈ ${saved:,.0f} economizados vs revisão manual ({ratio_str} ROI)"
        return f"≈ ${saved:,.0f} saved vs manual review ({ratio_str} ROI)"


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
