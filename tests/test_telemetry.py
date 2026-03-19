"""Tests for local CLI telemetry and execution history."""

from __future__ import annotations

import json
from pathlib import Path

from arch_review.telemetry import log_cli_event, read_cli_history


class TestTelemetry:
    def test_log_cli_event_writes_jsonl_line(self, tmp_path: Path) -> None:
        log_cli_event("review", {"model": "gpt-4o"}, history_dir=tmp_path)

        raw = (tmp_path / "cli.jsonl").read_text(encoding="utf-8").strip()
        entry = json.loads(raw)
        assert entry["action"] == "review"
        assert entry["details"]["model"] == "gpt-4o"
        assert "timestamp" in entry

    def test_log_cli_event_appends_multiple_entries(self, tmp_path: Path) -> None:
        log_cli_event("review", history_dir=tmp_path)
        log_cli_event("squad_review", history_dir=tmp_path)

        lines = (tmp_path / "cli.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_read_cli_history_returns_newest_first(self, tmp_path: Path) -> None:
        log_cli_event("review", history_dir=tmp_path)
        log_cli_event("adr_generate", history_dir=tmp_path)

        entries = read_cli_history(history_dir=tmp_path)
        assert entries[0]["action"] == "adr_generate"
        assert entries[1]["action"] == "review"

    def test_read_cli_history_filters_by_action(self, tmp_path: Path) -> None:
        log_cli_event("review", history_dir=tmp_path)
        log_cli_event("review", history_dir=tmp_path)
        log_cli_event("squad_review", history_dir=tmp_path)

        entries = read_cli_history(action="review", history_dir=tmp_path)
        assert len(entries) == 2
        assert all(entry["action"] == "review" for entry in entries)

    def test_read_cli_history_respects_limit(self, tmp_path: Path) -> None:
        log_cli_event("review", history_dir=tmp_path)
        log_cli_event("squad_review", history_dir=tmp_path)
        log_cli_event("adr_generate", history_dir=tmp_path)

        entries = read_cli_history(limit=2, history_dir=tmp_path)
        assert len(entries) == 2

    def test_read_cli_history_skips_malformed_lines(self, tmp_path: Path) -> None:
        (tmp_path / "cli.jsonl").write_text(
            'not-json\n{"timestamp":"2026-03-19T00:00:00+00:00","action":"review","details":{}}\n',
            encoding="utf-8",
        )

        entries = read_cli_history(history_dir=tmp_path)
        assert len(entries) == 1
        assert entries[0]["action"] == "review"

    def test_read_cli_history_returns_empty_when_missing(self, tmp_path: Path) -> None:
        entries = read_cli_history(history_dir=tmp_path)
        assert entries == []
