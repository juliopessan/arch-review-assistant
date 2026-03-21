"""Tests for ReviewSquad multi-agent system and memory."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from arch_review.models import ArchitectureInput, Severity
from arch_review.squad.manager import AgentManager
from arch_review.squad.memory import AgentMemory, SquadMemory
from arch_review.squad.squad import ReviewSquad

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_AGENT_RESPONSE = {
    "findings": [
        {
            "title": "No authentication on internal services",
            "category": "security",
            "severity": "critical",
            "description": "Internal services communicate without mTLS or token validation.",
            "affected_components": ["Order Service", "Payment Service"],
            "recommendation": "Implement service-to-service authentication via mTLS or JWT.",
            "questions_to_ask": ["What prevents a compromised service from calling Payment directly?"],
            "references": ["OWASP API Security Top 10 — API2"],
        }
    ],
    "agent_insight": "Payment service has no authentication — critical attack vector.",
    "lesson_for_memory": "Always check inter-service auth in microservice architectures.",
}

MOCK_SYNTH_RESPONSE = {
    "findings": [
        {
            "title": "No authentication on internal services",
            "category": "security",
            "severity": "critical",
            "description": "Internal services communicate without mTLS or token validation.",
            "affected_components": ["Order Service", "Payment Service"],
            "recommendation": "Implement service-to-service authentication via mTLS or JWT.",
            "questions_to_ask": ["What prevents a compromised service from calling Payment directly?"],
            "references": ["OWASP API Security Top 10 — API2"],
        }
    ],
    "overall_assessment": "Critical security and reliability gaps found.",
    "senior_architect_questions": ["What is the blast radius if Order Service is compromised?"],
    "recommended_adrs": ["ADR: Service-to-service authentication strategy"],
    "cross_patterns": ["Missing internal service authentication"],
    "lesson_for_memory": "Synthesis: auth gaps often coexist with SPOF issues.",
}

MOCK_MANAGER_RESPONSE = {
    "architecture_type": "microservices",
    "complexity": "medium",
    "top_risks": ["No inter-service authentication", "Single point of failure on DB"],
    "compliance_flags": ["PCI-DSS"],
    "cloud_providers": ["AWS"],
    "agent_directives": [
        {"agent_name": "security_agent",        "enabled": True,  "priority": "critical", "focus_note": "Check auth between Order and Payment", "skip_reason": ""},
        {"agent_name": "reliability_agent",      "enabled": True,  "priority": "high",     "focus_note": "Single DB is a SPOF",                  "skip_reason": ""},
        {"agent_name": "cost_agent",             "enabled": True,  "priority": "normal",   "focus_note": "Check EC2 sizing",                     "skip_reason": ""},
        {"agent_name": "observability_agent",    "enabled": True,  "priority": "normal",   "focus_note": "Check distributed tracing",            "skip_reason": ""},
        {"agent_name": "scalability_agent",      "enabled": True,  "priority": "high",     "focus_note": "Single DB limits write scale",         "skip_reason": ""},
        {"agent_name": "performance_agent",      "enabled": True,  "priority": "normal",   "focus_note": "Sync payment call adds latency",       "skip_reason": ""},
        {"agent_name": "maintainability_agent",  "enabled": True,  "priority": "low",      "focus_note": "Shared DB couples services",           "skip_reason": ""},
    ],
    "manager_briefing": "Banking API with critical auth gaps and single DB SPOF.",
    "manager_lesson": "Classified this as microservices with shared DB anti-pattern.",
}


def _make_mock_llm(content: str) -> MagicMock:
    mock = MagicMock()
    mock.choices[0].message.content = content
    mock.usage.prompt_tokens = 100
    mock.usage.completion_tokens = 50
    return mock


# ── Memory tests ──────────────────────────────────────────────────────────────

class TestAgentMemory:
    def test_creates_file_on_init(self, tmp_path: Path) -> None:
        mem = AgentMemory("security_agent", tmp_path)
        assert mem.agent_file.exists()

    def test_default_template_has_role(self, tmp_path: Path) -> None:
        mem = AgentMemory("security_agent", tmp_path)
        content = mem.read()
        assert "Security Agent" in content
        assert "OWASP" in content

    def test_append_lesson(self, tmp_path: Path) -> None:
        mem = AgentMemory("security_agent", tmp_path)
        mem.append_lesson("Always check JWT expiry", review_context="ecommerce")
        content = mem.read()
        assert "Always check JWT expiry" in content
        assert "Lesson" in content

    def test_get_lessons_section_empty_before_lessons(self, tmp_path: Path) -> None:
        mem = AgentMemory("reliability_agent", tmp_path)
        # Before any lessons, section after --- should be empty or just headers
        section = mem.get_lessons_section()
        assert isinstance(section, str)

    def test_get_lessons_section_after_lesson(self, tmp_path: Path) -> None:
        mem = AgentMemory("cost_agent", tmp_path)
        mem.append_lesson("Watch egress costs in multi-AZ setups", review_context="banking")
        section = mem.get_lessons_section()
        assert "egress costs" in section

    def test_append_pattern(self, tmp_path: Path) -> None:
        mem = AgentMemory("observability_agent", tmp_path)
        mem.append_pattern("Local log files always indicate missing observability stack")
        content = mem.read()
        assert "Local log files" in content

    def test_unknown_agent_uses_default_template(self, tmp_path: Path) -> None:
        mem = AgentMemory("custom_agent", tmp_path)
        assert mem.agent_file.exists()
        content = mem.read()
        assert "custom_agent" in content


class TestSquadMemory:
    def test_creates_squad_file(self, tmp_path: Path) -> None:
        mem = SquadMemory(tmp_path)
        assert mem.squad_file.exists()

    def test_append_cross_pattern(self, tmp_path: Path) -> None:
        mem = SquadMemory(tmp_path)
        mem.append_cross_pattern(
            "Single EC2 + no auth + local logs = early-stage MVP anti-pattern",
            agents_involved=["security_agent", "reliability_agent", "observability_agent"],
        )
        content = mem.read()
        assert "Single EC2" in content
        assert "security_agent" in content

    def test_append_review_summary(self, tmp_path: Path) -> None:
        mem = SquadMemory(tmp_path)
        mem.append_review_summary(
            architecture_summary="E-commerce system with RabbitMQ",
            total_findings=12,
            critical_count=2,
            top_patterns=["Missing auth", "Single EC2"],
        )
        content = mem.read()
        assert "E-commerce" in content
        assert "12" in content

    def test_get_recurring_patterns_empty(self, tmp_path: Path) -> None:
        mem = SquadMemory(tmp_path)
        result = mem.get_recurring_patterns()
        assert isinstance(result, str)

    def test_get_recurring_patterns_after_append(self, tmp_path: Path) -> None:
        mem = SquadMemory(tmp_path)
        mem.append_cross_pattern("Missing auth everywhere", ["security_agent"])
        result = mem.get_recurring_patterns()
        assert "Missing auth" in result


# ── Squad tests ───────────────────────────────────────────────────────────────

class TestReviewSquad:
    def test_agent_manager_creates_orchestration_plan(self, tmp_path: Path) -> None:
        """AgentManager.analyze() returns a valid OrchestrationPlan with defaults."""
        manager = AgentManager(memory_dir=tmp_path)
        plan = manager._default_plan()

        # Default plan enables all 7 specialist agents
        assert len(plan.agent_directives) == 7
        assert all(d.enabled for d in plan.agent_directives)
        assert set(plan.active_agents) == {
            "security_agent", "reliability_agent", "cost_agent", "observability_agent",
            "scalability_agent", "performance_agent", "maintainability_agent",
        }
        assert plan.skipped_agents == []
        assert plan.complexity == "medium"

    def test_agent_manager_can_skip_cost_agent_for_on_prem(self, tmp_path: Path) -> None:
        """AgentDirective supports disabled agents via get_directive()."""
        from arch_review.squad.manager import AgentDirective, OrchestrationPlan
        plan = OrchestrationPlan(
            architecture_type="monolith",
            complexity="low",
            top_risks=[],
            compliance_flags=[],
            cloud_providers=[],
            agent_directives=[
                AgentDirective(agent_name="security_agent",      enabled=True,  priority="high"),
                AgentDirective(agent_name="reliability_agent",   enabled=True,  priority="normal"),
                AgentDirective(agent_name="cost_agent",          enabled=False, priority="low",
                               skip_reason="on-prem deployment, no cloud cost concerns"),
                AgentDirective(agent_name="observability_agent", enabled=True,  priority="normal"),
            ],
        )
        cost_d = plan.get_directive("cost_agent")
        assert cost_d.enabled is False
        assert cost_d.priority == "low"
        assert "cost_agent" in plan.skipped_agents
        assert len(plan.active_agents) == 3

    def test_init_creates_memories(self, tmp_path: Path) -> None:
        sq = ReviewSquad(model="claude-sonnet-4-20250514", memory_dir=tmp_path)
        assert len(sq.agent_memories) == 9  # manager + 7 agents + synthesizer
        assert sq.squad_memory is not None

    def test_parse_json_valid(self, tmp_path: Path) -> None:
        sq = ReviewSquad(memory_dir=tmp_path)
        result = sq._parse_json(json.dumps(MOCK_AGENT_RESPONSE), "security_agent")
        assert result["findings"][0]["severity"] == "critical"

    def test_parse_json_strips_fences(self, tmp_path: Path) -> None:
        sq = ReviewSquad(memory_dir=tmp_path)
        content = f"```json\n{json.dumps(MOCK_AGENT_RESPONSE)}\n```"
        result = sq._parse_json(content, "security_agent")
        assert len(result["findings"]) == 1

    def test_parse_json_invalid_returns_empty(self, tmp_path: Path) -> None:
        sq = ReviewSquad(memory_dir=tmp_path)
        result = sq._parse_json("not json", "security_agent")
        assert result == {"findings": [], "agent_insight": "", "lesson_for_memory": ""}

    def test_build_findings_deduplicates(self, tmp_path: Path) -> None:
        sq = ReviewSquad(memory_dir=tmp_path)
        raw = [MOCK_AGENT_RESPONSE["findings"][0]] * 3  # same finding 3 times
        findings = sq._build_findings(raw)
        assert len(findings) == 1

    def test_build_findings_sorts_by_severity(self, tmp_path: Path) -> None:
        sq = ReviewSquad(memory_dir=tmp_path)
        raw = [
            {**MOCK_AGENT_RESPONSE["findings"][0], "title": "Low issue", "severity": "low"},
            {**MOCK_AGENT_RESPONSE["findings"][0], "title": "Critical issue", "severity": "critical"},
        ]
        findings = sq._build_findings(raw)
        assert findings[0].severity == Severity.CRITICAL

    def test_build_summary(self, tmp_path: Path) -> None:
        sq = ReviewSquad(memory_dir=tmp_path)
        findings = sq._build_findings([MOCK_AGENT_RESPONSE["findings"][0]])
        summary = sq._build_summary(findings, "Critical gaps found.")
        assert summary.critical_count == 1
        assert summary.total_findings == 1
        assert summary.top_risk == "No authentication on internal services"

    @patch("arch_review.squad.squad.litellm.completion")
    def test_full_squad_review(self, mock_completion: MagicMock, tmp_path: Path) -> None:
        # manager(1) + 7 specialist agents + synthesizer(1) = 9 calls total
        mock_completion.side_effect = [
            _make_mock_llm(json.dumps(MOCK_MANAGER_RESPONSE)),  # manager
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # security
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # reliability
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # cost
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # observability
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # scalability
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # performance
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # maintainability
            _make_mock_llm(json.dumps(MOCK_SYNTH_RESPONSE)),  # synthesizer
        ]

        sq = ReviewSquad(model="claude-sonnet-4-20250514", memory_dir=tmp_path)
        arch_input = ArchitectureInput(description="A simple e-commerce system")
        result = sq.review(arch_input)

        assert result.summary.total_findings >= 1
        assert result.summary.critical_count >= 1
        assert "squad:" in result.model_used
        assert len(result.senior_architect_questions) > 0
        assert result.orchestration_plan is not None
        assert mock_completion.call_count == 9

    @patch("arch_review.squad.squad.litellm.completion")
    def test_squad_updates_memory_after_review(self, mock_completion: MagicMock, tmp_path: Path) -> None:
        mock_completion.side_effect = [
            _make_mock_llm(json.dumps(MOCK_MANAGER_RESPONSE)),  # manager
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # security
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # reliability
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # cost
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # observability
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # scalability
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # performance
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # maintainability
            _make_mock_llm(json.dumps(MOCK_SYNTH_RESPONSE)),  # synthesizer
        ]

        sq = ReviewSquad(memory_dir=tmp_path)
        arch_input = ArchitectureInput(description="Banking API with no auth")
        sq.review(arch_input)

        # Lessons should be appended to at least one agent file
        security_content = (tmp_path / "security_agent.md").read_text()
        assert "Always check inter-service auth" in security_content
        manager_content = (tmp_path / "manager_agent.md").read_text()
        assert "Classified" in manager_content

        # Squad memory should have a review entry
        squad_content = (tmp_path / "SQUAD_MEMORY.md").read_text()
        assert "Banking API" in squad_content

    @patch("arch_review.squad.squad.litellm.completion")
    def test_squad_handles_agent_failure_gracefully(
        self, mock_completion: MagicMock, tmp_path: Path
    ) -> None:
        # One agent throws, others succeed, synthesizer succeeds
        mock_completion.side_effect = [
            _make_mock_llm(json.dumps(MOCK_MANAGER_RESPONSE)),  # manager
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # security OK
            Exception("LLM timeout"),                          # reliability fails
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # cost OK
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # observability OK
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # scalability OK
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # performance OK
            _make_mock_llm(json.dumps(MOCK_AGENT_RESPONSE)),  # maintainability OK
            _make_mock_llm(json.dumps(MOCK_SYNTH_RESPONSE)),  # synthesizer OK
        ]

        sq = ReviewSquad(memory_dir=tmp_path)
        result = sq.review(ArchitectureInput(description="Some architecture"))
        # Should still produce a result despite one agent failing
        assert result is not None
        assert result.summary.total_findings >= 1
