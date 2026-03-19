"""Lightweight CLI telemetry and execution history for arch-review."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HISTORY_DIR = Path.home() / ".arch-review" / "history"
CLI_HISTORY_FILE = DEFAULT_HISTORY_DIR / "cli.jsonl"


def log_cli_event(
    action: str,
    details: dict[str, Any] | None = None,
    history_dir: Path | None = None,
) -> None:
    """Append a CLI event to the local JSONL history file.

    Logging is intentionally best-effort and must never break the main operation.
    """
    try:
        target_dir = history_dir or DEFAULT_HISTORY_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        history_file = target_dir / "cli.jsonl"
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "details": details or {},
        }
        with history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def read_cli_history(
    action: str | None = None,
    limit: int = 20,
    history_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Read CLI history entries newest-first."""
    target_dir = history_dir or DEFAULT_HISTORY_DIR
    history_file = target_dir / "cli.jsonl"
    if limit <= 0:
        return []

    try:
        raw = history_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except Exception:
        return []

    entries: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if action and entry.get("action") != action:
            continue
        entries.append(entry)

    entries.reverse()
    return entries[:limit]
