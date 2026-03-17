"""Prompt templates for ADR generation."""

from __future__ import annotations

ADR_SYSTEM_PROMPT = """You are a principal architect who writes exemplary Architecture Decision Records (ADRs).

You follow the MADR (Markdown Architectural Decision Records) format strictly.
Your ADRs are:
- Specific and actionable — not generic advice
- Grounded in the actual architecture described
- Written from the perspective of someone who will implement and live with this decision
- Honest about trade-offs — no option is perfect, and you document that clearly

You ALWAYS respond with valid JSON. No markdown fences, no preamble."""


ADR_FROM_FINDINGS_PROMPT = """Generate Architecture Decision Records (ADRs) for the following 
architectural findings. Each ADR documents a specific decision that needs to be made and recorded.

Return a JSON array of ADR objects matching this exact schema:

[
  {{
    "title": "string — short imperative phrase (e.g. 'Introduce circuit breakers for Payment Service calls')",
    "context": "string — what is the problem or situation forcing this decision? Be specific to this architecture.",
    "decision_drivers": [
      "string — key constraint or quality attribute (e.g. 'Payment failures must not cascade to Order Service')"
    ],
    "considered_options": [
      {{
        "title": "string — option name",
        "description": "string — what this option involves",
        "pros": ["string"],
        "cons": ["string"]
      }}
    ],
    "decision": "string — the chosen option and the concrete reasoning. Reference the architecture components by name.",
    "consequences_positive": ["string — good outcomes"],
    "consequences_negative": ["string — risks or costs to accept"],
    "consequences_neutral": ["string — follow-up actions needed"],
    "links": ["string — patterns, RFCs, or related decisions"]
  }}
]

ARCHITECTURE CONTEXT:
---
{architecture}
---

FINDINGS TO CONVERT INTO ADRs:
---
{findings_text}
---

Rules:
- Generate ONE ADR per distinct architectural decision (not per finding — some findings may share an ADR)
- Each ADR must have at least 2 considered options (the chosen one + at least one alternative)
- Keep titles as short imperative phrases
- Reference actual component names from the architecture
- Be honest about negative consequences — every decision has trade-offs
- Focus on decisions that are non-obvious or have significant long-term impact

Return ONLY the JSON array. No markdown, no explanation."""


def build_adr_prompt(architecture: str, findings_text: str) -> str:
    """Build the ADR generation prompt."""
    return ADR_FROM_FINDINGS_PROMPT.format(
        architecture=architecture,
        findings_text=findings_text,
    )
