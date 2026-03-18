"""Tests for the robust JSON parser utility."""

from __future__ import annotations

import json

import pytest

from arch_review.utils.json_parser import (
    parse_llm_json,
    sanitize_architecture_input,
)

VALID = {"findings": [{"title": "Test", "severity": "high"}], "overall_assessment": "ok"}


class TestParseLlmJson:
    def test_parses_clean_json(self) -> None:
        result = parse_llm_json(json.dumps(VALID))
        assert result["overall_assessment"] == "ok"

    def test_strips_markdown_fences(self) -> None:
        content = f"```json\n{json.dumps(VALID)}\n```"
        result = parse_llm_json(content)
        assert "findings" in result

    def test_strips_unnamed_fences(self) -> None:
        content = f"```\n{json.dumps(VALID)}\n```"
        result = parse_llm_json(content)
        assert "findings" in result

    def test_extracts_json_from_preamble(self) -> None:
        content = f"Here is the review:\n\n{json.dumps(VALID)}\n\nHope that helps!"
        result = parse_llm_json(content)
        assert "findings" in result

    def test_repairs_truncated_at_root_level(self) -> None:
        # Most common case: model truncates mid-way through overall_assessment
        partial = '{"findings": [{"title": "Test", "severity": "high", "description": "x", "recommendation": "y", "category": "risk"}], "overall_assessment": "Critical gap'
        result = parse_llm_json(partial)
        assert "findings" in result
        assert len(result["findings"]) == 1

    def test_repairs_truncated_missing_root_brace(self) -> None:
        # Model returns complete findings array but misses closing brace
        partial = '{"findings": [{"title": "A", "severity": "high", "description": "x", "recommendation": "y", "category": "risk"}, {"title": "B", "severity": "medium", "description": "x", "recommendation": "y", "category": "risk"}], "overall_assessment": "ok"'
        result = parse_llm_json(partial)
        assert "findings" in result

    def test_handles_smart_quotes(self) -> None:
        # Smart quotes get replaced by regular quotes in sanitization
        content = '{"findings": [{"title": "Issue with \u201coperator\u201d node", "severity": "medium", "description": "x", "recommendation": "y", "category": "risk"}], "overall_assessment": "ok"}'
        result = parse_llm_json(content)
        # Smart quotes are replaced with regular quotes
        assert "operator" in result["findings"][0]["title"]

    def test_raises_on_completely_invalid(self) -> None:
        with pytest.raises(ValueError, match="invalid JSON"):
            parse_llm_json("this is just a sentence with no JSON at all")

    def test_wraps_list_response(self) -> None:
        # Some models return a list instead of object
        content = json.dumps([{"title": "Finding 1"}])
        result = parse_llm_json(content)
        assert "findings" in result
        assert result["findings"][0]["title"] == "Finding 1"


class TestSanitizeArchitectureInput:
    def test_removes_mermaid_comments(self) -> None:
        text = "graph LR\n  %% This is a comment\n  A --> B"
        result = sanitize_architecture_input(text)
        assert "%%" not in result
        assert "A --> B" in result

    def test_replaces_smart_quotes(self) -> None:
        text = "Service \u201cAuth\u201d connects to \u201cDB\u201d"
        result = sanitize_architecture_input(text)
        assert "\u201c" not in result
        assert "\u201d" not in result
        assert '"Auth"' in result

    def test_replaces_em_dash(self) -> None:
        text = "Service A \u2014 main entry point"
        result = sanitize_architecture_input(text)
        assert "\u2014" not in result
        assert "--" in result

    def test_normalizes_line_endings(self) -> None:
        text = "line1\r\nline2\rline3"
        result = sanitize_architecture_input(text)
        assert "\r" not in result
        assert result.count("\n") == 2

    def test_preserves_mermaid_structure(self) -> None:
        text = "flowchart LR\n  CALLER --> OC\n  OC --> AA"
        result = sanitize_architecture_input(text)
        assert "CALLER --> OC" in result
        assert "OC --> AA" in result

    def test_handles_the_exact_failing_diagram(self) -> None:
        """Test with the actual Mermaid diagram that caused the bug."""
        diagram = """flowchart LR
  %% \u2500\u2500 Chamador \u2500\u2500
  CALLER["\ud83d\udcde Chamador\nPSTN / Celular"]
  %% \u2500\u2500 Operadora \u2500\u2500
  OC["\ud83d\udd17 Operator Connect\nClaro \u00b7 Vivo \u00b7 Lumen"]
  AA["\ud83c\udfa4 Auto-Attendant\nMenu de voz \u00b7 IVR \u00b7 Hor\u00e1rios"]
  classDef caller fill:#FFF3F1,stroke:#F04E37"""
        result = sanitize_architecture_input(diagram)
        # Should not raise, should remove comments
        assert "%%" not in result
        assert "CALLER" in result
        assert "OC" in result
