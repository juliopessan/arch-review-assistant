"""ADR Generator — converts review findings into structured ADRs via LLM."""

from __future__ import annotations

import logging
from typing import Any

import litellm

from arch_review.models import Finding, ReviewResult
from arch_review.models_adr import ADR, ADRGenerationResult, ADROption, ADRStatus
from arch_review.prompts.adr import ADR_SYSTEM_PROMPT, build_adr_prompt
from arch_review.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)


class ADRGenerator:
    """Generates Architecture Decision Records from review findings."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        litellm_kwargs: dict | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.litellm_kwargs: dict = litellm_kwargs or {}

    def from_review(self, result: ReviewResult) -> ADRGenerationResult:
        """Generate ADRs from a complete ReviewResult."""
        # Focus on findings that warrant ADR documentation
        adr_worthy = [
            f for f in result.findings
            if f.category.value in (
                "missing_adr", "trade_off", "security",
                "reliability", "scalability", "risk",
            )
        ]

        # Also include explicitly recommended ADRs as context
        extra_context = ""
        if result.recommended_adrs:
            extra_context = "\n\nThe review also flagged these decisions as needing ADRs:\n"
            extra_context += "\n".join(f"- {a}" for a in result.recommended_adrs)

        findings_text = self._format_findings(adr_worthy) + extra_context
        architecture = result.input.description

        return self._generate(
            architecture=architecture,
            findings_text=findings_text,
            source="review",
        )

    def from_findings(
        self,
        findings: list[Finding],
        architecture: str,
    ) -> ADRGenerationResult:
        """Generate ADRs from a specific list of findings."""
        findings_text = self._format_findings(findings)
        return self._generate(
            architecture=architecture,
            findings_text=findings_text,
            source="manual",
        )

    def _generate(
        self,
        architecture: str,
        findings_text: str,
        source: str,
    ) -> ADRGenerationResult:
        prompt = build_adr_prompt(
            architecture=architecture,
            findings_text=findings_text,
        )

        logger.debug("Generating ADRs with model: %s", self.model)

        response = litellm.completion(
            model=self.model,
            messages=[
                {"role": "system", "content": ADR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.litellm_kwargs,
        )

        raw = response.choices[0].message.content or ""
        adrs = self._parse_adrs(raw)

        return ADRGenerationResult(
            adrs=adrs,
            total_generated=len(adrs),
            source=source,
            model_used=self.model,
        )

    def _parse_adrs(self, content: str) -> list[ADR]:
        """Parse LLM response into ADR objects."""
        try:
            parsed = parse_llm_json(content, context="ADRGenerator")
        except ValueError as exc:
            logger.error("Failed to parse ADR response: %s", exc)
            raise

        raw_list: list[dict[str, Any]] = (
            parsed if isinstance(parsed, list)
            else parsed.get("adrs", parsed.get("findings", [parsed]))
        )

        adrs = []
        for i, raw in enumerate(raw_list, start=1):
            try:
                options = [
                    ADROption(
                        title=o.get("title", "Option"),
                        description=o.get("description", ""),
                        pros=o.get("pros", []),
                        cons=o.get("cons", []),
                    )
                    for o in raw.get("considered_options", [])
                ]

                adr = ADR(
                    number=i,
                    title=raw.get("title", f"Decision {i}"),
                    status=ADRStatus.PROPOSED,
                    context=raw.get("context", ""),
                    decision_drivers=raw.get("decision_drivers", []),
                    considered_options=options,
                    decision=raw.get("decision", ""),
                    consequences_positive=raw.get("consequences_positive", []),
                    consequences_negative=raw.get("consequences_negative", []),
                    consequences_neutral=raw.get("consequences_neutral", []),
                    links=raw.get("links", []),
                    source_finding=raw.get("source_finding"),
                )
                adrs.append(adr)
            except Exception as exc:
                logger.warning("Skipping malformed ADR %d: %s", i, exc)

        return adrs

    def _format_findings(self, findings: list[Finding]) -> str:
        """Format findings as readable text for the prompt."""
        if not findings:
            return "No specific findings — generate ADRs based on the architecture description."

        lines = []
        for i, f in enumerate(findings, 1):
            lines.append(
                f"{i}. [{f.severity.value.upper()}] {f.title} ({f.category.value})\n"
                f"   Description: {f.description}\n"
                f"   Recommendation: {f.recommendation}"
            )
        return "\n\n".join(lines)
