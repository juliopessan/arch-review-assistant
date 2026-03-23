"""Core review engine — calls LLM via LiteLLM and parses structured output."""

from __future__ import annotations

import logging
from typing import Any

import litellm

from arch_review.models import (
    ArchitectureInput,
    Finding,
    FindingCategory,
    ReviewResult,
    ReviewSummary,
    Severity,
)
from arch_review.prompts import SYSTEM_PROMPT, build_review_prompt
from arch_review.utils.json_parser import parse_llm_json, sanitize_architecture_input

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose logging by default
litellm.suppress_debug_info = True


DEFAULT_MODEL = "claude-sonnet-4-20250514"

SUPPORTED_MODELS = {
    # ── Anthropic ──────────────────────────────────────────────────────────────
    "claude-sonnet-4-20250514":  "anthropic",
    "claude-opus-4-20250514":    "anthropic",
    "claude-haiku-4-5-20251001": "anthropic",
    # ── OpenAI ─────────────────────────────────────────────────────────────────
    "gpt-4o":           "openai",
    "gpt-4o-mini":      "openai",
    "gpt-5.4-nano":     "openai",   # Ultra-cheap OCR / high-volume pipelines $0.20/$1.25 per 1M
    # ── Google ─────────────────────────────────────────────────────────────────
    "gemini/gemini-3.1-pro-preview":   "google",  # Flagship — Gemini 3.1 Pro (latest, Mar 2026)
    "gemini/gemini-3.1-flash-preview": "google",  # Fast — Gemini 3.1 Flash (frontier-class, Mar 2026)
    "gemini/gemini-2.5-pro":           "google",  # Stable — best price/performance, deep reasoning
    "gemini/gemini-2.5-flash":         "google",  # Stable — best price/perf for high-volume tasks
    "gemini/gemini-2.5-flash-lite":    "google",  # Lite — lowest cost, high-volume workhorse
    # ── Mistral ────────────────────────────────────────────────────────────────
    "mistral/mistral-large-latest": "mistral",
    # ── Ollama (local) ─────────────────────────────────────────────────────────
    "ollama/llama3":   "ollama",
    "ollama/mistral":  "ollama",
    # ── OpenRouter — Chinese models (free) ────────────────────────────────────
    # Best for agentic tasks / architecture reasoning
    "openrouter/deepseek/deepseek-chat-v3-0324:free":  "openrouter",  # DeepSeek V3 — SOTA reasoning, 128K
    "openrouter/deepseek/deepseek-r1-zero:free":       "openrouter",  # DeepSeek R1 — deep reasoning chain
    "openrouter/z-ai/glm-4.5-air:free":               "openrouter",  # GLM-4.5 Air — MoE, thinking mode
    "openrouter/stepfun/step-3.5-flash:free":         "openrouter",  # StepFun 3.5 Flash — 196B MoE, fast
    # Best for vision / OCR (architecture diagrams)
    "openrouter/qwen/qwen2.5-vl-3b-instruct:free":    "openrouter",  # Qwen2.5 VL — native vision + OCR
    "openrouter/moonshotai/kimi-vl-a3b-thinking:free": "openrouter", # Kimi VL — vision + reasoning
}


class ReviewEngine:
    """Orchestrates the architecture review process."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        litellm_kwargs: dict | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.litellm_kwargs: dict = litellm_kwargs or {}

    def review(self, arch_input: ArchitectureInput) -> ReviewResult:
        """Run a full architecture review and return structured results."""

        # Sanitize input to prevent JSON serialization issues with special chars
        clean_description = sanitize_architecture_input(arch_input.description)

        prompt = build_review_prompt(
            architecture=clean_description,
            context=arch_input.context,
            focus_areas=[f.value for f in arch_input.focus_areas],
        )

        logger.debug("Calling model: %s", self.model)

        response = litellm.completion(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.litellm_kwargs,
        )

        raw_content = response.choices[0].message.content or ""
        parsed = self._parse_response(raw_content)
        findings = self._build_findings(parsed.get("findings", []))
        summary = self._build_summary(findings, parsed.get("overall_assessment", ""))

        return ReviewResult(
            input=arch_input,
            findings=findings,
            summary=summary,
            senior_architect_questions=parsed.get("senior_architect_questions", []),
            recommended_adrs=parsed.get("recommended_adrs", []),
            model_used=self.model,
        )

    def _parse_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response using robust multi-strategy parser."""
        return parse_llm_json(content, context="ReviewEngine")

    def _build_findings(self, raw_findings: list[dict[str, Any]]) -> list[Finding]:
        """Convert raw dicts to typed Finding objects."""
        findings = []
        for raw in raw_findings:
            try:
                finding = Finding(
                    title=raw.get("title", "Untitled finding"),
                    category=FindingCategory(raw.get("category", "risk")),
                    severity=Severity(raw.get("severity", "medium")),
                    description=raw.get("description", ""),
                    affected_components=raw.get("affected_components", []),
                    recommendation=raw.get("recommendation", ""),
                    questions_to_ask=raw.get("questions_to_ask", []),
                    references=raw.get("references", []),
                )
                findings.append(finding)
            except Exception as exc:
                logger.warning("Skipping malformed finding: %s — %s", raw, exc)

        # Sort by severity
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        return sorted(findings, key=lambda f: severity_order[f.severity])

    def _build_summary(
        self, findings: list[Finding], overall_assessment: str
    ) -> ReviewSummary:
        """Build summary statistics from findings."""
        counts = {s: 0 for s in Severity}
        for f in findings:
            counts[f.severity] += 1

        top_risk = None
        critical_findings = [f for f in findings if f.severity == Severity.CRITICAL]
        if critical_findings:
            top_risk = critical_findings[0].title

        return ReviewSummary(
            total_findings=len(findings),
            critical_count=counts[Severity.CRITICAL],
            high_count=counts[Severity.HIGH],
            medium_count=counts[Severity.MEDIUM],
            low_count=counts[Severity.LOW],
            info_count=counts[Severity.INFO],
            top_risk=top_risk,
            overall_assessment=overall_assessment,
        )
