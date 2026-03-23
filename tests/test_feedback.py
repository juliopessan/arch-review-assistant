"""Tests for the Feedback Loop immune system."""
from __future__ import annotations

from pathlib import Path
import pytest
from arch_review.feedback.store import (
    FeedbackStore, FeedbackDecision, FeedbackEntry, MAX_ENTRIES, AGENT_DOMAIN
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path: Path) -> FeedbackStore:
    return FeedbackStore(feedback_dir=tmp_path)


# ── Core record / retrieve ────────────────────────────────────────────────────

class TestFeedbackStore:

    def test_record_approve(self, store: FeedbackStore, tmp_path: Path) -> None:
        entry = store.record(
            "security_agent", "No HTTPS", "security", "critical",
            FeedbackDecision.APPROVE, "Good catch"
        )
        assert entry.decision == "approve"
        assert entry.agent == "security_agent"
        assert entry.finding == "No HTTPS"
        assert "security" in entry.tags
        assert "critical" in entry.tags

    def test_record_reject(self, store: FeedbackStore, tmp_path: Path) -> None:
        entry = store.record(
            "cost_agent", "Oversized EC2", "cost", "medium",
            FeedbackDecision.REJECT, "We need this size for burst"
        )
        assert entry.decision == "reject"
        assert "rejected" in entry.tags
        assert entry.reason == "We need this size for burst"

    def test_entries_persisted(self, store: FeedbackStore, tmp_path: Path) -> None:
        store.record("reliability_agent", "No failover", "reliability", "high",
                     FeedbackDecision.REJECT)
        # Re-open same dir
        store2 = FeedbackStore(feedback_dir=tmp_path)
        entries = store2.get_entries("reliability_agent")
        assert len(entries) == 1
        assert entries[0].finding == "No failover"

    def test_multiple_domains_isolated(self, store: FeedbackStore) -> None:
        store.record("security_agent", "Weak TLS", "security", "high",
                     FeedbackDecision.REJECT)
        store.record("cost_agent", "Idle EC2", "cost", "medium",
                     FeedbackDecision.APPROVE)
        sec = store.get_entries("security_agent")
        cost = store.get_entries("cost_agent")
        assert len(sec) == 1 and sec[0].finding == "Weak TLS"
        assert len(cost) == 1 and cost[0].finding == "Idle EC2"

    def test_filter_by_decision(self, store: FeedbackStore) -> None:
        store.record("security_agent", "Finding A", "security", "low",
                     FeedbackDecision.APPROVE)
        store.record("security_agent", "Finding B", "security", "high",
                     FeedbackDecision.REJECT, "Wrong context")
        rejected = store.get_entries("security_agent", FeedbackDecision.REJECT)
        approved = store.get_entries("security_agent", FeedbackDecision.APPROVE)
        assert len(rejected) == 1 and rejected[0].finding == "Finding B"
        assert len(approved) == 1 and approved[0].finding == "Finding A"


# ── FIFO enforcement ──────────────────────────────────────────────────────────

class TestFIFO:

    def test_fifo_enforces_max_30(self, store: FeedbackStore) -> None:
        for i in range(MAX_ENTRIES + 5):
            store.record("performance_agent", f"Finding {i}", "performance",
                         "medium", FeedbackDecision.REJECT)
        entries = store.get_entries("performance_agent")
        assert len(entries) == MAX_ENTRIES

    def test_fifo_keeps_newest(self, store: FeedbackStore) -> None:
        for i in range(MAX_ENTRIES + 5):
            store.record("performance_agent", f"Finding {i}", "performance",
                         "medium", FeedbackDecision.REJECT)
        entries = store.get_entries("performance_agent")
        # Oldest (0..4) should be gone, newest (5..34) should remain
        titles = [e.finding for e in entries]
        assert "Finding 0" not in titles
        assert f"Finding {MAX_ENTRIES + 4}" in titles


# ── Feedback section for prompt injection ─────────────────────────────────────

class TestFeedbackSection:

    def test_empty_returns_empty_string(self, store: FeedbackStore) -> None:
        section = store.get_feedback_section("security_agent")
        assert section == ""

    def test_rejected_in_section(self, store: FeedbackStore) -> None:
        store.record("security_agent", "No rate limiting", "security", "medium",
                     FeedbackDecision.REJECT, "We have WAF for this")
        section = store.get_feedback_section("security_agent")
        assert "No rate limiting" in section
        assert "REJECTED" in section
        assert "We have WAF for this" in section

    def test_approved_in_section(self, store: FeedbackStore) -> None:
        store.record("security_agent", "Missing MFA", "security", "high",
                     FeedbackDecision.APPROVE)
        section = store.get_feedback_section("security_agent")
        assert "Missing MFA" in section
        assert "APPROVED" in section

    def test_section_has_do_not_repeat_instruction(self, store: FeedbackStore) -> None:
        store.record("security_agent", "Test", "security", "low",
                     FeedbackDecision.REJECT)
        section = store.get_feedback_section("security_agent")
        assert "DO NOT suggest" in section or "do not" in section.lower()

    def test_rejected_takes_priority(self, store: FeedbackStore) -> None:
        store.record("cost_agent", "Oversized DB", "cost", "high",
                     FeedbackDecision.REJECT, "Intentional for compliance")
        store.record("cost_agent", "Idle Lambda", "cost", "low",
                     FeedbackDecision.APPROVE)
        section = store.get_feedback_section("cost_agent")
        # Rejected should appear before approved
        rejected_pos = section.find("REJECTED")
        approved_pos = section.find("APPROVED")
        assert rejected_pos < approved_pos


# ── Stats ─────────────────────────────────────────────────────────────────────

class TestStats:

    def test_stats_empty(self, store: FeedbackStore) -> None:
        stats = store.get_stats()
        assert stats["total_entries"] == 0
        assert stats["total_approved"] == 0
        assert stats["total_rejected"] == 0

    def test_stats_counts(self, store: FeedbackStore) -> None:
        store.record("security_agent", "A", "security", "high", FeedbackDecision.APPROVE)
        store.record("security_agent", "B", "security", "low",  FeedbackDecision.REJECT)
        store.record("cost_agent",     "C", "cost",     "medium", FeedbackDecision.REJECT)
        stats = store.get_stats()
        assert stats["total_entries"] == 3
        assert stats["total_approved"] == 1
        assert stats["total_rejected"] == 2

    def test_stats_domain_breakdown(self, store: FeedbackStore) -> None:
        store.record("reliability_agent", "SPOF", "reliability", "critical",
                     FeedbackDecision.REJECT)
        stats = store.get_stats()
        assert "reliability" in stats["domains"]
        assert stats["domains"]["reliability"]["rejected"] == 1


# ── Clear domain ──────────────────────────────────────────────────────────────

class TestClear:

    def test_clear_domain(self, store: FeedbackStore) -> None:
        store.record("observability_agent", "No tracing", "observability", "high",
                     FeedbackDecision.REJECT)
        removed = store.clear_domain("observability_agent")
        assert removed == 1
        assert store.get_entries("observability_agent") == []

    def test_clear_does_not_affect_other_domains(self, store: FeedbackStore) -> None:
        store.record("security_agent", "A", "security", "low", FeedbackDecision.APPROVE)
        store.record("cost_agent", "B", "cost", "low", FeedbackDecision.APPROVE)
        store.clear_domain("security_agent")
        assert len(store.get_entries("cost_agent")) == 1


# ── Export ────────────────────────────────────────────────────────────────────

class TestExport:

    def test_export_for_consolidation(self, store: FeedbackStore) -> None:
        store.record("maintainability_agent", "God class", "maintainability",
                     "medium", FeedbackDecision.REJECT)
        export = store.export_for_consolidation()
        assert "maintainability" in export
        assert len(export["maintainability"]) == 1
        assert export["maintainability"][0]["finding"] == "God class"

    def test_agent_domain_coverage(self) -> None:
        # All 7 specialist agents + synthesizer must have a domain mapping
        expected = {
            "security_agent", "reliability_agent", "cost_agent",
            "observability_agent", "scalability_agent", "performance_agent",
            "maintainability_agent", "synthesizer_agent",
        }
        assert expected.issubset(set(AGENT_DOMAIN.keys()))
