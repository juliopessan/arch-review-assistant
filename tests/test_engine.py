"""Tests for Architecture Review Assistant core engine."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from arch_review.engine import ReviewEngine
from arch_review.models import (
    ArchitectureInput,
    Finding,
    FindingCategory,
    ReviewResult,
    Severity,
)
from arch_review.prompts import build_review_prompt

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_LLM_RESPONSE = {
    "findings": [
        {
            "title": "Single point of failure on EC2 instance",
            "category": "reliability",
            "severity": "critical",
            "description": "All services run on a single EC2 t3.medium. Any instance failure takes down the entire system.",
            "affected_components": ["API Gateway", "Order Service", "RabbitMQ"],
            "recommendation": "Distribute services across at least 2 AZs with an ALB. Extract RabbitMQ to a managed service like Amazon MQ.",
            "questions_to_ask": [
                "What is the RTO/RPO requirement for this system?",
                "Has a failure scenario been tested?",
            ],
            "references": ["AWS Well-Architected Framework — Reliability Pillar"],
        },
        {
            "title": "No observability stack",
            "category": "observability",
            "severity": "high",
            "description": "Logs written to local files mean they are lost on instance termination.",
            "affected_components": ["All services"],
            "recommendation": "Ship logs to CloudWatch Logs or an ELK stack. Add distributed tracing with OpenTelemetry.",
            "questions_to_ask": ["How do you diagnose production incidents today?"],
            "references": ["OpenTelemetry", "CloudWatch Logs"],
        },
    ],
    "senior_architect_questions": [
        "What are the SLA commitments to your customers?",
        "Has a load test ever been run against this system?",
    ],
    "recommended_adrs": [
        "ADR: Choice of message broker (RabbitMQ vs Amazon MQ)",
        "ADR: Database sharding strategy for Inventory Service",
    ],
    "overall_assessment": "The architecture has critical reliability gaps due to single-instance deployment. Must be addressed before any production scale.",
}


def _make_mock_response(content: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    return mock_response


# ── Model tests ───────────────────────────────────────────────────────────────

class TestFinding:
    def test_severity_ordering(self) -> None:
        findings = [
            Finding(title="Low", category=FindingCategory.RISK, severity=Severity.LOW,
                    description="", recommendation=""),
            Finding(title="Critical", category=FindingCategory.SECURITY, severity=Severity.CRITICAL,
                    description="", recommendation=""),
            Finding(title="Medium", category=FindingCategory.SCALABILITY, severity=Severity.MEDIUM,
                    description="", recommendation=""),
        ]
        # Simulate engine sort
        severity_order = {s: i for i, s in enumerate([
            Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO
        ])}
        sorted_findings = sorted(findings, key=lambda f: severity_order[f.severity])
        assert sorted_findings[0].severity == Severity.CRITICAL
        assert sorted_findings[-1].severity == Severity.LOW


class TestArchitectureInput:
    def test_default_values(self) -> None:
        arch = ArchitectureInput(description="A simple system")
        assert arch.focus_areas == []
        assert arch.context is None
        assert arch.input_format == "text"

    def test_with_focus_areas(self) -> None:
        arch = ArchitectureInput(
            description="A system",
            focus_areas=[FindingCategory.SECURITY, FindingCategory.COST],
        )
        assert len(arch.focus_areas) == 2


# ── Prompt tests ──────────────────────────────────────────────────────────────

class TestPrompts:
    def test_prompt_contains_architecture(self) -> None:
        arch = "My architecture has a database and an API"
        prompt = build_review_prompt(architecture=arch)
        assert arch in prompt

    def test_prompt_with_context(self) -> None:
        prompt = build_review_prompt(
            architecture="some arch",
            context="LGPD compliance required",
        )
        assert "LGPD compliance required" in prompt

    def test_prompt_with_focus_areas(self) -> None:
        prompt = build_review_prompt(
            architecture="some arch",
            focus_areas=["security", "cost"],
        )
        assert "security" in prompt
        assert "cost" in prompt

    def test_prompt_without_context_has_no_placeholder(self) -> None:
        prompt = build_review_prompt(architecture="some arch")
        assert "ADDITIONAL CONTEXT" not in prompt


# ── Engine tests ──────────────────────────────────────────────────────────────

class TestReviewEngine:
    def test_parse_valid_json(self) -> None:
        engine = ReviewEngine()
        parsed = engine._parse_response(json.dumps(MOCK_LLM_RESPONSE))
        assert "findings" in parsed
        assert len(parsed["findings"]) == 2

    def test_parse_json_with_markdown_fences(self) -> None:
        engine = ReviewEngine()
        content = f"```json\n{json.dumps(MOCK_LLM_RESPONSE)}\n```"
        parsed = engine._parse_response(content)
        assert "findings" in parsed

    def test_parse_invalid_json_raises(self) -> None:
        engine = ReviewEngine()
        with pytest.raises(ValueError, match="invalid JSON"):
            engine._parse_response("this is not json at all")

    def test_build_findings_sorts_by_severity(self) -> None:
        engine = ReviewEngine()
        findings = engine._build_findings(MOCK_LLM_RESPONSE["findings"])
        assert findings[0].severity == Severity.CRITICAL
        assert findings[1].severity == Severity.HIGH

    def test_build_findings_skips_malformed(self) -> None:
        engine = ReviewEngine()
        raw = [
            {"title": "good", "category": "security", "severity": "high",
             "description": "desc", "recommendation": "rec"},
            {"title": "bad", "category": "INVALID_CATEGORY", "severity": "INVALID"},
        ]
        findings = engine._build_findings(raw)
        assert len(findings) == 1

    def test_build_summary_counts_correctly(self) -> None:
        engine = ReviewEngine()
        findings = engine._build_findings(MOCK_LLM_RESPONSE["findings"])
        summary = engine._build_summary(findings, "good")
        assert summary.critical_count == 1
        assert summary.high_count == 1
        assert summary.total_findings == 2
        assert summary.top_risk == "Single point of failure on EC2 instance"

    @patch("arch_review.engine.litellm.completion")
    def test_review_full_flow(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _make_mock_response(
            json.dumps(MOCK_LLM_RESPONSE)
        )
        engine = ReviewEngine(model="claude-sonnet-4-20250514")
        arch_input = ArchitectureInput(description="A simple system with a database")
        result = engine.review(arch_input)

        assert isinstance(result, ReviewResult)
        assert result.summary.total_findings == 2
        assert result.summary.critical_count == 1
        assert len(result.recommended_adrs) == 2
        assert result.model_used == "claude-sonnet-4-20250514"

    @patch("arch_review.engine.litellm.completion")
    def test_review_calls_litellm_with_correct_model(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _make_mock_response(
            json.dumps(MOCK_LLM_RESPONSE)
        )
        engine = ReviewEngine(model="gpt-4o", temperature=0.1)
        arch_input = ArchitectureInput(description="Some architecture")
        engine.review(arch_input)

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["temperature"] == 0.1
