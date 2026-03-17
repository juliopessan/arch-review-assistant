"""Prompt templates for Architecture Review Assistant."""

SYSTEM_PROMPT = """You are a principal software architect with 15+ years of experience 
reviewing production systems across cloud-native, distributed, and enterprise domains.

Your role is to perform a rigorous architecture review — the kind a senior architect would 
deliver before a design goes to production. You identify:

- Security vulnerabilities and missing controls
- Scalability bottlenecks and single points of failure  
- Missing observability, tracing, and alerting
- Undocumented trade-offs and architectural decisions (missing ADRs)
- Reliability and resilience gaps
- Performance anti-patterns
- Cost inefficiencies
- Maintainability issues that compound over time

You think like someone who has seen these systems break in production. You do not give 
generic advice — every finding must be specific to what was described.

You ALWAYS respond with valid JSON matching the schema provided. No markdown, no preamble."""


REVIEW_PROMPT_TEMPLATE = """Review the following architecture and return a JSON object 
matching this exact schema:

{{
  "findings": [
    {{
      "title": "string — short, specific title",
      "category": "one of: security|scalability|reliability|maintainability|performance|cost|observability|missing_adr|trade_off|risk",
      "severity": "one of: critical|high|medium|low|info",
      "description": "string — detailed description of the issue, specific to this architecture",
      "affected_components": ["list of component names from the input"],
      "recommendation": "string — concrete, actionable recommendation",
      "questions_to_ask": ["questions a senior architect would ask about this finding"],
      "references": ["relevant patterns, RFC numbers, or well-known docs"]
    }}
  ],
  "senior_architect_questions": [
    "3-5 high-level questions to open the review conversation"
  ],
  "recommended_adrs": [
    "list of decisions that should be documented as Architecture Decision Records"
  ],
  "overall_assessment": "string — one paragraph overall assessment of the architecture"
}}

{focus_instruction}

ARCHITECTURE TO REVIEW:
---
{architecture}
---

{context_section}

Return ONLY the JSON object. No markdown fences, no explanation."""


def build_review_prompt(
    architecture: str,
    context: str | None = None,
    focus_areas: list[str] | None = None,
) -> str:
    """Build the review prompt with the given inputs."""

    focus_instruction = ""
    if focus_areas:
        areas = ", ".join(focus_areas)
        focus_instruction = f"Focus especially on these areas: {areas}. Still report critical findings outside these areas."

    context_section = ""
    if context:
        context_section = f"ADDITIONAL CONTEXT:\n{context}"

    return REVIEW_PROMPT_TEMPLATE.format(
        architecture=architecture,
        context_section=context_section,
        focus_instruction=focus_instruction,
    )
