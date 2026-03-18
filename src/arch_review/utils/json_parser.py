"""Robust JSON parser — handles truncated responses, encoding issues, and partial JSON."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_llm_json(content: str, context: str = "") -> dict[str, Any]:
    """
    Parse JSON from an LLM response with multiple fallback strategies:

    1. Strip markdown fences
    2. Try direct json.loads
    3. Try extracting the first {...} block
    4. Try repairing truncated JSON (unterminated strings, missing closers)
    5. Raise ValueError with a clear message
    """
    content = _strip_fences(content)

    # Strategy 1: direct parse
    result = _try_parse(content)
    if result is not None:
        return result

    # Strategy 2: extract first JSON object block
    extracted = _extract_json_block(content)
    if extracted:
        result = _try_parse(extracted)
        if result is not None:
            logger.warning("JSON extracted from surrounding text (%s)", context)
            return result

    # Strategy 2.5: simple append missing closing brace (most common truncation)
    for suffix in ["}", "]}", "]}}"] :
        result = _try_parse(content + suffix)
        if result is not None:
            logger.warning("JSON repaired with suffix '%s' (%s)", suffix, context)
            return result

    # Strategy 3: repair truncated JSON
    repaired = _repair_truncated(content)
    if repaired:
        result = _try_parse(repaired)
        if result is not None:
            logger.warning("JSON repaired (truncated response) (%s)", context)
            return result

    # Strategy 4: sanitize non-ASCII and retry
    sanitized = _sanitize_content(content)
    result = _try_parse(sanitized)
    if result is not None:
        logger.warning("JSON parsed after sanitizing non-ASCII (%s)", context)
        return result

    repaired2 = _repair_truncated(sanitized)
    if repaired2:
        result = _try_parse(repaired2)
        if result is not None:
            logger.warning("JSON parsed after sanitize + repair (%s)", context)
            return result

    raise ValueError(
        f"Model returned invalid JSON that could not be repaired. "
        f"Context: {context}. "
        f"Try a more capable model (e.g. claude-sonnet-4-20250514 or gpt-4o). "
        f"First 200 chars: {content[:200]}"
    )


def sanitize_architecture_input(text: str) -> str:
    """
    Sanitize architecture input text before sending to LLM.

    Removes/replaces characters that commonly cause JSON serialization issues
    when they appear in LLM responses that quote the input back.
    """
    # Replace smart quotes with ASCII equivalents
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u2014", "--").replace("\u2013", "-")
    text = text.replace("\u00b7", "·")  # keep middle dot as is — safe in strings

    # Replace Mermaid comment markers that can confuse LLMs
    text = re.sub(r"%%.*$", "", text, flags=re.MULTILINE)

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    return text.strip()


# ── Internal helpers ───────────────────────────────────────────────────────────

def _strip_fences(content: str) -> str:
    """Remove markdown code fences."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        return "\n".join(line for line in lines if not line.startswith("```")).strip()
    return content


def _try_parse(content: str) -> dict[str, Any] | None:
    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            return {"findings": result}
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _extract_json_block(content: str) -> str | None:
    """Extract the first {...} block from content."""
    start = content.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(content[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
        if not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return content[start:i + 1]
    return None


def _repair_truncated(content: str) -> str | None:
    """
    Repair truncated JSON by finding the last complete key:value pair
    and closing any open structures.

    Handles:
    - Truncation mid-string (most common LLM failure)
    - Missing closing brackets/braces
    """
    if not content.strip().startswith("{"):
        return None

    # Walk through to find depth and last "clean" position
    # A clean position is right after a complete value at root or array level
    depth_brace = 0
    depth_bracket = 0
    in_string = False
    escape_next = False
    last_clean_pos = -1  # last position where we had complete depth-balanced content

    for i, ch in enumerate(content):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
            if depth_brace >= 1:  # closed an inner object
                last_clean_pos = i
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1
            if depth_bracket >= 0:
                last_clean_pos = i
        elif ch == "," and not in_string:
            # Comma at array/object level = boundary between complete items
            last_clean_pos = i - 1  # position before the comma

    # Nothing broken
    if depth_brace <= 1 and depth_bracket == 0 and not in_string:
        return None

    # Find the truncation point — last complete item boundary
    # Look backwards from end for the last } or ] or " that closes a value
    truncate_at = last_clean_pos
    if truncate_at < 0:
        return None

    # Trim to last clean position, strip trailing comma/whitespace
    truncated = content[:truncate_at + 1].rstrip()
    while truncated.endswith(","):
        truncated = truncated[:-1].rstrip()

    # Recount depths on truncated to know how to close
    d_brace = 0
    d_bracket = 0
    in_s = False
    esc = False
    for ch in truncated:
        if esc:
            esc = False
            continue
        if ch == "\\" and in_s:
            esc = True
            continue
        if ch == '"':
            in_s = not in_s
            continue
        if in_s:
            continue
        if ch == "{":
            d_brace += 1
        elif ch == "}":
            d_brace -= 1
        elif ch == "[":
            d_bracket += 1
        elif ch == "]":
            d_bracket -= 1

    closing = "]" * max(d_bracket, 0) + "}" * max(d_brace, 0)
    if not closing:
        return None
    return truncated + closing


def _sanitize_content(content: str) -> str:
    """Replace problematic Unicode characters in LLM response."""
    # Replace emojis and special chars that can appear in LLM responses
    # that quote back user input with special characters
    replacements = {
        "\u201c": '\\"', "\u201d": '\\"',
        "\u2018": "\\'", "\u2019": "\\'",
        "\u2014": "--",  "\u2013": "-",
        "\u00b7": ".",
        # Common emoji that break JSON when unescaped in strings
    }
    for char, replacement in replacements.items():
        content = content.replace(char, replacement)

    # Remove control characters except newline/tab
    content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", content)
    return content
