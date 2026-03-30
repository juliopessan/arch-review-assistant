"""Tests for the enterprise PDF export."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from arch_review.models import (  # noqa: E402
    ArchitectureInput,
    Finding,
    FindingCategory,
    OrchestrationPlanSnapshot,
    ReviewResult,
    ReviewSummary,
    RunMetrics,
    AgentRunMetric,
    Severity,
)

if importlib.util.find_spec("reportlab") is not None:
    from pdf_export import build_pdf  # noqa: E402
else:
    build_pdf = None


@pytest.mark.skipif(build_pdf is None, reason="reportlab is not installed")
def test_build_pdf_generates_valid_pdf_bytes() -> None:
    review = ReviewResult(
        input=ArchitectureInput(
            description=(
                "API Gateway -> Order Service -> Payment Service -> PostgreSQL.\n"
                "All services run in a single region with shared infrastructure."
            ),
            context="LGPD + PCI workloads with strict uptime commitments.",
        ),
        findings=[
            Finding(
                title="Shared database creates a single failure domain",
                category=FindingCategory.RELIABILITY,
                severity=Severity.CRITICAL,
                description="Both services depend on the same primary database with no failover.",
                affected_components=["Order Service", "Payment Service", "PostgreSQL"],
                recommendation="Add Multi-AZ failover and isolate service ownership boundaries.",
                questions_to_ask=["What is the acceptable RTO for database failure?"],
                references=["AWS RDS Multi-AZ"],
            ),
            Finding(
                title="No end-to-end traceability for payment flow",
                category=FindingCategory.OBSERVABILITY,
                severity=Severity.HIGH,
                description="Tracing is absent, making transaction correlation slow during incidents.",
                affected_components=["API Gateway", "Payment Service"],
                recommendation="Adopt OpenTelemetry spans across the critical path.",
                questions_to_ask=["How do you currently correlate API and payment logs?"],
                references=["OpenTelemetry"],
            ),
        ],
        summary=ReviewSummary(
            total_findings=2,
            critical_count=1,
            high_count=1,
            medium_count=0,
            low_count=0,
            info_count=0,
            top_risk="Shared database creates a single failure domain",
            overall_assessment="The architecture has meaningful resilience and observability gaps.",
        ),
        senior_architect_questions=[
            "How will payment processing continue during a regional database event?"
        ],
        recommended_adrs=[
            "ADR: Database failover and ownership strategy",
            "ADR: Distributed tracing standard for revenue-critical services",
        ],
        model_used="squad:claude-sonnet-4-20250514",
        orchestration_plan=OrchestrationPlanSnapshot(
            architecture_type="microservices",
            complexity="high",
            top_risks=["Single database failover gap", "Weak production tracing"],
            compliance_flags=["LGPD", "PCI-DSS"],
            cloud_providers=["AWS"],
            manager_briefing="Prioritize reliability and payment-path observability first.",
            active_agents=["security_agent", "reliability_agent", "observability_agent", "performance_agent"],
            skipped_agents=["cost_agent"],
            agent_priorities={"reliability_agent": "critical", "observability_agent": "high"},
            agent_focus_notes={
                "reliability_agent": "Inspect failover behavior and ownership boundaries.",
                "observability_agent": "Focus on traceability for payment incidents.",
            },
        ),
        run_metrics=RunMetrics(
            model_used="claude-sonnet-4-20250514",
            started_at="2026-03-30T12:00:00+00:00",
            total_duration_s=31.4,
            phase_manager_s=3.1,
            phase_parallel_s=18.0,
            phase_synth_s=10.3,
            agents=[
                AgentRunMetric(agent_name="manager_agent", phase="manager", duration_s=3.1, model_used="claude-sonnet-4-20250514"),
                AgentRunMetric(agent_name="reliability_agent", phase="parallel", duration_s=9.4, tokens_in=1200, tokens_out=640, findings_count=1, model_used="claude-sonnet-4-20250514"),
                AgentRunMetric(agent_name="observability_agent", phase="parallel", duration_s=8.6, tokens_in=980, tokens_out=510, findings_count=1, model_used="claude-sonnet-4-20250514"),
                AgentRunMetric(agent_name="synthesizer_agent", phase="synthesizer", duration_s=10.3, tokens_in=1500, tokens_out=900, findings_count=2, model_used="claude-sonnet-4-20250514"),
            ],
        ),
    )

    pdf_bytes = build_pdf(review)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 5_000
