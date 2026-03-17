"""Tests for ADR Generator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arch_review.adr_generator import ADRGenerator
from arch_review.models import ArchitectureInput, Finding, FindingCategory, ReviewResult, ReviewSummary, Severity
from arch_review.models_adr import ADR, ADRGenerationResult, ADROption, ADRStatus
from arch_review.output.adr_writer import _slugify, write_adrs

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_ADR_RESPONSE = [
    {
        "title": "Introduce circuit breakers for Payment Service calls",
        "context": (
            "The Order Service calls Payment Service synchronously. "
            "A slow Stripe API response blocks the entire order flow and can cascade failures."
        ),
        "decision_drivers": [
            "Payment failures must not cascade to Order Service",
            "System must remain available during Stripe outages",
        ],
        "considered_options": [
            {
                "title": "Resilience4j Circuit Breaker",
                "description": "Wrap Payment Service calls with a circuit breaker that opens after N failures.",
                "pros": ["Industry standard", "Configurable thresholds", "Built-in metrics"],
                "cons": ["Adds library dependency", "Requires fallback logic"],
            },
            {
                "title": "Timeout-only approach",
                "description": "Set aggressive timeouts on HTTP calls without a circuit breaker.",
                "pros": ["Simple to implement"],
                "cons": ["Does not prevent cascading load", "No automatic recovery detection"],
            },
        ],
        "decision": (
            "Implement Resilience4j Circuit Breaker around Payment Service calls. "
            "Open after 5 consecutive failures, half-open after 30s."
        ),
        "consequences_positive": [
            "Order Service remains available during Stripe outages",
            "Automatic recovery detection via half-open state",
        ],
        "consequences_negative": [
            "Orders during open circuit must be queued or rejected — requires business rule decision",
            "Adds operational complexity (circuit state monitoring)",
        ],
        "consequences_neutral": [
            "Add circuit state to observability dashboard",
            "Define SLA for payment retry window",
        ],
        "links": ["https://resilience4j.readme.io/docs/circuitbreaker", "Martin Fowler — Circuit Breaker pattern"],
    }
]


def _make_mock_llm_response(content: str) -> MagicMock:
    mock = MagicMock()
    mock.choices[0].message.content = content
    return mock


def _make_review_result() -> ReviewResult:
    finding = Finding(
        title="Single point of failure on EC2 instance",
        category=FindingCategory.RELIABILITY,
        severity=Severity.CRITICAL,
        description="All services on one instance.",
        recommendation="Distribute across AZs.",
    )
    return ReviewResult(
        input=ArchitectureInput(description="A simple e-commerce system"),
        findings=[finding],
        summary=ReviewSummary(
            total_findings=1,
            critical_count=1,
            high_count=0,
            medium_count=0,
            low_count=0,
            info_count=0,
            overall_assessment="Critical reliability gap.",
        ),
        senior_architect_questions=[],
        recommended_adrs=["ADR: Multi-AZ deployment strategy"],
        model_used="claude-sonnet-4-20250514",
    )


# ── Model tests ───────────────────────────────────────────────────────────────

class TestADRModel:
    def test_defaults(self) -> None:
        adr = ADR(
            number=1,
            title="Use Redis for session cache",
            context="We need fast session storage.",
            decision="Use Redis.",
        )
        assert adr.status == ADRStatus.PROPOSED
        assert adr.considered_options == []
        assert adr.number == 1

    def test_with_options(self) -> None:
        opt = ADROption(title="Redis", description="In-memory store", pros=["Fast"], cons=["Volatile"])
        adr = ADR(
            number=1,
            title="Cache strategy",
            context="Need caching.",
            decision="Use Redis.",
            considered_options=[opt],
        )
        assert len(adr.considered_options) == 1
        assert adr.considered_options[0].title == "Redis"


# ── Generator tests ───────────────────────────────────────────────────────────

class TestADRGenerator:
    def test_parse_valid_response(self) -> None:
        gen = ADRGenerator()
        adrs = gen._parse_adrs(json.dumps(MOCK_ADR_RESPONSE))
        assert len(adrs) == 1
        assert adrs[0].title == "Introduce circuit breakers for Payment Service calls"
        assert len(adrs[0].considered_options) == 2

    def test_parse_strips_markdown_fences(self) -> None:
        gen = ADRGenerator()
        content = f"```json\n{json.dumps(MOCK_ADR_RESPONSE)}\n```"
        adrs = gen._parse_adrs(content)
        assert len(adrs) == 1

    def test_parse_invalid_json_raises(self) -> None:
        gen = ADRGenerator()
        with pytest.raises(ValueError, match="invalid JSON"):
            gen._parse_adrs("not json at all")

    def test_parse_assigns_sequential_numbers(self) -> None:
        gen = ADRGenerator()
        two_adrs = MOCK_ADR_RESPONSE * 2
        adrs = gen._parse_adrs(json.dumps(two_adrs))
        assert adrs[0].number == 1
        assert adrs[1].number == 2

    def test_format_findings_empty(self) -> None:
        gen = ADRGenerator()
        result = gen._format_findings([])
        assert "No specific findings" in result

    def test_format_findings_includes_title(self) -> None:
        gen = ADRGenerator()
        finding = Finding(
            title="Missing circuit breaker",
            category=FindingCategory.RELIABILITY,
            severity=Severity.HIGH,
            description="Payment calls have no fallback.",
            recommendation="Add circuit breaker.",
        )
        result = gen._format_findings([finding])
        assert "Missing circuit breaker" in result
        assert "HIGH" in result

    @patch("arch_review.adr_generator.litellm.completion")
    def test_from_review_full_flow(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _make_mock_llm_response(
            json.dumps(MOCK_ADR_RESPONSE)
        )
        gen = ADRGenerator(model="claude-sonnet-4-20250514")
        result = gen.from_review(_make_review_result())

        assert isinstance(result, ADRGenerationResult)
        assert result.total_generated == 1
        assert result.source == "review"
        assert result.model_used == "claude-sonnet-4-20250514"

    @patch("arch_review.adr_generator.litellm.completion")
    def test_from_review_filters_adr_worthy_findings(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _make_mock_llm_response(json.dumps(MOCK_ADR_RESPONSE))
        gen = ADRGenerator()

        # Create review with mixed finding categories
        info_finding = Finding(
            title="Minor style issue",
            category=FindingCategory.MAINTAINABILITY,
            severity=Severity.INFO,
            description="Minor issue.",
            recommendation="Fix it.",
        )
        review = _make_review_result()
        review.findings.append(info_finding)

        gen.from_review(review)
        call_prompt = mock_completion.call_args[1]["messages"][1]["content"]
        # The MAINTAINABILITY/INFO finding should not dominate (reliability findings should be there)
        assert "Single point of failure" in call_prompt


# ── Writer tests ──────────────────────────────────────────────────────────────

class TestADRWriter:
    def test_slugify_basic(self) -> None:
        assert _slugify("Use Redis for session cache") == "use-redis-for-session-cache"

    def test_slugify_special_chars(self) -> None:
        slug = _slugify("Introduce circuit breakers (Resilience4j)")
        assert " " not in slug
        assert "(" not in slug

    def test_slugify_max_length(self) -> None:
        long_title = "A" * 100
        assert len(_slugify(long_title)) <= 60

    def test_write_adrs_creates_files(self, tmp_path: Path) -> None:
        gen = ADRGenerator()
        adrs_parsed = gen._parse_adrs(json.dumps(MOCK_ADR_RESPONSE))
        gen_result = ADRGenerationResult(
            adrs=adrs_parsed,
            total_generated=len(adrs_parsed),
            source="test",
            model_used="test-model",
        )

        written = write_adrs(gen_result, tmp_path, starting_number=1)
        assert len(written) == 1
        assert written[0].exists()
        assert written[0].suffix == ".md"

    def test_write_adrs_file_contains_title(self, tmp_path: Path) -> None:
        gen = ADRGenerator()
        adrs_parsed = gen._parse_adrs(json.dumps(MOCK_ADR_RESPONSE))
        gen_result = ADRGenerationResult(
            adrs=adrs_parsed,
            total_generated=1,
            source="test",
            model_used="test-model",
        )

        written = write_adrs(gen_result, tmp_path)
        content = written[0].read_text(encoding="utf-8")
        assert "Introduce circuit breakers" in content
        assert "Resilience4j" in content
        assert "## Status" in content
        assert "## Decision Outcome" in content

    def test_write_adrs_respects_starting_number(self, tmp_path: Path) -> None:
        gen = ADRGenerator()
        adrs_parsed = gen._parse_adrs(json.dumps(MOCK_ADR_RESPONSE))
        gen_result = ADRGenerationResult(
            adrs=adrs_parsed,
            total_generated=1,
            source="test",
            model_used="test-model",
        )

        written = write_adrs(gen_result, tmp_path, starting_number=7)
        assert written[0].name.startswith("0007-")
