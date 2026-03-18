"""Architecture Review Assistant — Streamlit Web UI."""

from __future__ import annotations

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Architecture Review Assistant",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .severity-critical { background:#fef2f2; border-left:4px solid #ef4444; padding:12px 16px; border-radius:4px; margin:8px 0; }
    .severity-high     { background:#fff7ed; border-left:4px solid #f97316; padding:12px 16px; border-radius:4px; margin:8px 0; }
    .severity-medium   { background:#fefce8; border-left:4px solid #eab308; padding:12px 16px; border-radius:4px; margin:8px 0; }
    .severity-low      { background:#eff6ff; border-left:4px solid #3b82f6; padding:12px 16px; border-radius:4px; margin:8px 0; }
    .severity-info     { background:#f9fafb; border-left:4px solid #9ca3af; padding:12px 16px; border-radius:4px; margin:8px 0; }
    .metric-card       { background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; text-align:center; }
    .adr-card          { background:#f0fdf4; border:1px solid #86efac; border-radius:8px; padding:16px; margin:8px 0; }
    .stTextArea textarea { font-family: monospace; font-size: 13px; }
    h1 { color: #1e293b; }
    .finding-title { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
    .finding-rec   { color: #166534; margin-top: 8px; font-size: 13px; }
    .finding-q     { color: #854d0e; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ── Imports ───────────────────────────────────────────────────────────────────
import os
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arch_review.engine import SUPPORTED_MODELS, ReviewEngine
from arch_review.models import ArchitectureInput, FindingCategory, ReviewResult, Severity
from arch_review.adr_generator import ADRGenerator
from arch_review.models_adr import ADRGenerationResult

# ── Constants ─────────────────────────────────────────────────────────────────
SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH:     "🟠",
    Severity.MEDIUM:   "🟡",
    Severity.LOW:      "🔵",
    Severity.INFO:     "⚪",
}

SEVERITY_CSS = {
    Severity.CRITICAL: "severity-critical",
    Severity.HIGH:     "severity-high",
    Severity.MEDIUM:   "severity-medium",
    Severity.LOW:      "severity-low",
    Severity.INFO:     "severity-info",
}

EXAMPLE_ARCH = """# E-commerce Order Processing System

## Components
- **API Gateway**: Single entry point, handles auth via JWT
- **Order Service**: Accepts orders, validates inventory, publishes to RabbitMQ
- **Inventory Service**: Manages stock, reads from a single PostgreSQL instance
- **Payment Service**: Calls Stripe API synchronously during order flow
- **Notification Service**: Listens to RabbitMQ, sends email via SMTP
- **Database**: Single PostgreSQL instance shared between Order and Inventory

## Flow
1. Client → API Gateway → Order Service
2. Order Service validates inventory (sync call to Inventory Service)
3. Order Service charges payment (sync call to Payment Service → Stripe)
4. Order Service publishes OrderPlaced event to RabbitMQ
5. Notification Service consumes event, sends confirmation email

## Infrastructure
- All services deployed on a single EC2 t3.medium
- No CDN, no caching layer
- Logs written to local files
- RabbitMQ also on same EC2 instance
- No staging environment
"""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏗️ arch-review")
    st.caption("AI-powered architecture review")
    st.divider()

    # Model selection
    st.subheader("⚙️ Model")
    model_options = list(SUPPORTED_MODELS.keys())
    selected_model = st.selectbox(
        "LLM provider",
        options=model_options,
        index=0,
        help="Any LiteLLM-supported model. Set the matching API key below.",
    )

    provider = SUPPORTED_MODELS.get(selected_model, "")
    st.caption(f"Provider: `{provider}`")

    # API key input
    st.subheader("🔑 API Key")
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="sk-ant-... / sk-... / etc.",
        help="Set your provider API key. Not stored anywhere.",
    )
    if api_key:
        # Map provider to env var
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai":    "OPENAI_API_KEY",
            "google":    "GEMINI_API_KEY",
            "mistral":   "MISTRAL_API_KEY",
        }
        env_var = env_map.get(provider, "OPENAI_API_KEY")
        os.environ[env_var] = api_key
        st.success(f"✓ `{env_var}` set")

    # Focus areas
    st.subheader("🎯 Focus Areas")
    all_categories = [c.value for c in FindingCategory]
    focus_areas = st.multiselect(
        "Limit review to (optional)",
        options=all_categories,
        default=[],
        help="Leave empty to review everything.",
    )

    # ADR toggle
    st.subheader("📄 ADR Generator")
    generate_adrs = st.toggle("Generate ADRs after review", value=True)

    st.divider()
    st.caption("📖 [Docs](https://github.com/juliopessan/arch-review-assistant) · MIT License")


# ── Main UI ───────────────────────────────────────────────────────────────────
st.title("🏗️ Architecture Review Assistant")
st.caption("Paste your architecture description and get a senior architect's review in seconds.")

tab_review, tab_results, tab_adrs, tab_export = st.tabs([
    "📝 Input", "🔍 Findings", "📄 ADRs", "📤 Export"
])

# ── Tab 1: Input ──────────────────────────────────────────────────────────────
with tab_review:
    col1, col2 = st.columns([3, 1])

    with col1:
        arch_text = st.text_area(
            "Architecture description",
            height=380,
            placeholder="Paste your architecture here — prose, Mermaid diagram, bullet points...",
            help="The richer the description, the better the findings.",
        )

    with col2:
        st.markdown("**Context (optional)**")
        context_text = st.text_area(
            "Business context",
            height=180,
            placeholder="e.g. LGPD compliance required. ~500 concurrent users. Single cloud Azure.",
            label_visibility="collapsed",
        )

        st.markdown("**Quick load**")
        if st.button("📋 Load example", use_container_width=True):
            st.session_state["arch_text_example"] = EXAMPLE_ARCH
            st.rerun()

        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.pop("review_result", None)
            st.session_state.pop("adr_result", None)
            st.rerun()

    # Load example if triggered
    if "arch_text_example" in st.session_state:
        arch_text = st.session_state.pop("arch_text_example")

    # Run button
    st.divider()
    run_col, info_col = st.columns([1, 3])
    with run_col:
        run_clicked = st.button(
            "🚀 Run Review",
            type="primary",
            use_container_width=True,
            disabled=not arch_text.strip(),
        )
    with info_col:
        if not arch_text.strip():
            st.info("Paste an architecture description to begin.")
        elif not api_key and not any(
            os.environ.get(k) for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY"]
        ):
            st.warning("⚠️ Set an API key in the sidebar before running.")

    # ── Run review ──────────────────────────────────────────────────────────
    if run_clicked and arch_text.strip():
        focus_cats = [FindingCategory(f) for f in focus_areas]
        arch_input = ArchitectureInput(
            description=arch_text,
            context=context_text or None,
            focus_areas=focus_cats,
        )
        engine = ReviewEngine(model=selected_model)

        with st.spinner(f"Reviewing with `{selected_model}`..."):
            try:
                result: ReviewResult = engine.review(arch_input)
                st.session_state["review_result"] = result
                st.session_state.pop("adr_result", None)
            except Exception as exc:
                st.error(f"❌ Review failed: {exc}")
                st.stop()

        # Generate ADRs automatically if toggled
        if generate_adrs and "review_result" in st.session_state:
            with st.spinner("Generating ADRs..."):
                try:
                    gen = ADRGenerator(model=selected_model)
                    adr_result: ADRGenerationResult = gen.from_review(st.session_state["review_result"])
                    st.session_state["adr_result"] = adr_result
                except Exception as exc:
                    st.warning(f"ADR generation failed: {exc}")

        st.success("✅ Review complete! See the **Findings** tab.")
        st.rerun()


# ── Tab 2: Findings ───────────────────────────────────────────────────────────
with tab_results:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    else:
        result: ReviewResult = st.session_state["review_result"]
        s = result.summary

        # Summary metrics
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("🔴 Critical", s.critical_count)
        m2.metric("🟠 High",     s.high_count)
        m3.metric("🟡 Medium",   s.medium_count)
        m4.metric("🔵 Low",      s.low_count)
        m5.metric("⚪ Info",     s.info_count)
        m6.metric("📊 Total",    s.total_findings)

        st.divider()

        # Overall assessment
        with st.expander("📋 Overall Assessment", expanded=True):
            st.write(s.overall_assessment)

        # Senior architect questions
        if result.senior_architect_questions:
            with st.expander("❓ Opening Questions for the Review Session"):
                for i, q in enumerate(result.senior_architect_questions, 1):
                    st.markdown(f"**{i}.** {q}")

        # Severity filter
        st.subheader("Findings")
        severity_filter = st.multiselect(
            "Filter by severity",
            options=[s.value for s in Severity],
            default=[s.value for s in Severity],
            horizontal=True,
        )

        filtered = [
            f for f in result.findings
            if f.severity.value in severity_filter
        ]

        if not filtered:
            st.info("No findings match the selected filters.")
        else:
            for finding in filtered:
                css_class = SEVERITY_CSS[finding.severity]
                icon = SEVERITY_ICONS[finding.severity]
                cat = finding.category.value.upper().replace("_", " ")

                with st.container():
                    st.markdown(
                        f'<div class="{css_class}">'
                        f'<div class="finding-title">{icon} {finding.title} '
                        f'<span style="font-weight:400;color:#64748b;font-size:12px;">[{cat}]</span></div>'
                        f'<div style="font-size:13px;margin-top:6px;">{finding.description}</div>',
                        unsafe_allow_html=True,
                    )

                    if finding.affected_components:
                        st.markdown(
                            f'<div style="font-size:12px;color:#64748b;margin-top:6px;">'
                            f'🔗 Affects: {", ".join(finding.affected_components)}</div>',
                            unsafe_allow_html=True,
                        )

                    st.markdown(
                        f'<div class="finding-rec">✅ {finding.recommendation}</div>',
                        unsafe_allow_html=True,
                    )

                    if finding.questions_to_ask:
                        qs = " · ".join(f""{q}"" for q in finding.questions_to_ask)
                        st.markdown(
                            f'<div class="finding-q">💬 {qs}</div>',
                            unsafe_allow_html=True,
                        )

                    st.markdown("</div>", unsafe_allow_html=True)
                    st.markdown("")

        # Recommended ADRs
        if result.recommended_adrs:
            st.divider()
            st.subheader("📌 Recommended ADRs")
            for i, adr_title in enumerate(result.recommended_adrs, 1):
                st.markdown(f"**{i}.** {adr_title}")


# ── Tab 3: ADRs ───────────────────────────────────────────────────────────────
with tab_adrs:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    elif "adr_result" not in st.session_state:
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            if st.button("⚡ Generate ADRs now", type="primary", use_container_width=True):
                with st.spinner("Generating ADRs..."):
                    try:
                        gen = ADRGenerator(model=selected_model)
                        adr_result = gen.from_review(st.session_state["review_result"])
                        st.session_state["adr_result"] = adr_result
                        st.rerun()
                    except Exception as exc:
                        st.error(f"ADR generation failed: {exc}")
        with col_info:
            st.info("ADR generation was skipped. Click to generate now.")
    else:
        adr_result: ADRGenerationResult = st.session_state["adr_result"]

        st.success(f"✅ {adr_result.total_generated} ADR(s) generated with `{adr_result.model_used}`")

        for adr in adr_result.adrs:
            num = str(adr.number).zfill(4)
            with st.expander(f"📄 ADR-{num} — {adr.title}", expanded=False):
                col_l, col_r = st.columns(2)
                col_l.markdown(f"**Status:** `{adr.status.value}`")
                col_r.markdown(f"**Date:** {adr.date}")

                st.markdown("**Context**")
                st.write(adr.context)

                if adr.decision_drivers:
                    st.markdown("**Decision Drivers**")
                    for d in adr.decision_drivers:
                        st.markdown(f"- {d}")

                if adr.considered_options:
                    st.markdown("**Options Considered**")
                    for opt in adr.considered_options:
                        with st.container():
                            st.markdown(f"**{opt.title}**")
                            st.write(opt.description)
                            opt_col1, opt_col2 = st.columns(2)
                            if opt.pros:
                                opt_col1.markdown("✅ **Pros**")
                                for p in opt.pros:
                                    opt_col1.markdown(f"- {p}")
                            if opt.cons:
                                opt_col2.markdown("⚠️ **Cons**")
                                for c in opt.cons:
                                    opt_col2.markdown(f"- {c}")

                st.markdown("**Decision**")
                st.success(adr.decision)

                if adr.consequences_positive or adr.consequences_negative:
                    c1, c2 = st.columns(2)
                    if adr.consequences_positive:
                        c1.markdown("✅ **Positive Consequences**")
                        for c in adr.consequences_positive:
                            c1.markdown(f"- {c}")
                    if adr.consequences_negative:
                        c2.markdown("⚠️ **Negative Consequences**")
                        for c in adr.consequences_negative:
                            c2.markdown(f"- {c}")

                if adr.consequences_neutral:
                    st.markdown("**Follow-up Actions**")
                    for c in adr.consequences_neutral:
                        st.markdown(f"- {c}")


# ── Tab 4: Export ─────────────────────────────────────────────────────────────
with tab_export:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    else:
        result: ReviewResult = st.session_state["review_result"]

        st.subheader("📤 Export Review")

        # JSON export
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**JSON** — machine-readable, use in CI/CD")
            st.download_button(
                label="⬇️ Download review.json",
                data=result.model_dump_json(indent=2),
                file_name="arch-review.json",
                mime="application/json",
                use_container_width=True,
            )

        # Markdown export
        with col2:
            st.markdown("**Markdown** — paste into Confluence, Notion, GitHub")
            md_content = _build_markdown_report(result)
            st.download_button(
                label="⬇️ Download review.md",
                data=md_content,
                file_name="arch-review.md",
                mime="text/markdown",
                use_container_width=True,
            )

        # ADR export
        if "adr_result" in st.session_state:
            st.divider()
            st.subheader("📄 Export ADRs")
            adr_result: ADRGenerationResult = st.session_state["adr_result"]

            adr_zip = _build_adr_zip(adr_result)
            st.download_button(
                label=f"⬇️ Download {adr_result.total_generated} ADR(s) as .zip",
                data=adr_zip,
                file_name="adrs.zip",
                mime="application/zip",
                use_container_width=True,
            )
            st.caption("Unzip into your `docs/adr/` directory and commit.")

        # Preview
        st.divider()
        st.subheader("👁️ Markdown Preview")
        st.code(_build_markdown_report(result), language="markdown")


# ── Helper functions ──────────────────────────────────────────────────────────

def _build_markdown_report(result: ReviewResult) -> str:
    """Build a Markdown report from a ReviewResult."""
    s = result.summary
    lines = [
        "# Architecture Review Report",
        f"\n> Model: `{result.model_used}`\n",
        "## Summary\n",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 Critical | {s.critical_count} |",
        f"| 🟠 High | {s.high_count} |",
        f"| 🟡 Medium | {s.medium_count} |",
        f"| 🔵 Low | {s.low_count} |",
        f"| ⚪ Info | {s.info_count} |",
        f"| **Total** | **{s.total_findings}** |",
        f"\n## Overall Assessment\n\n{s.overall_assessment}",
    ]
    if result.senior_architect_questions:
        lines.append("\n## Opening Questions\n")
        for q in result.senior_architect_questions:
            lines.append(f"- {q}")
    lines.append("\n## Findings\n")
    for f in result.findings:
        icon = SEVERITY_ICONS[f.severity]
        cat = f.category.value.upper().replace("_", " ")
        lines.append(f"\n### {icon} {f.title}")
        lines.append(f"\n**Severity:** {f.severity.value} | **Category:** {cat}\n")
        lines.append(f"{f.description}\n")
        if f.affected_components:
            lines.append(f"**Affected:** {', '.join(f.affected_components)}\n")
        lines.append(f"**Recommendation:** {f.recommendation}\n")
        if f.questions_to_ask:
            lines.append("**Questions:**")
            for q in f.questions_to_ask:
                lines.append(f"- {q}")
    if result.recommended_adrs:
        lines.append("\n## Recommended ADRs\n")
        for i, a in enumerate(result.recommended_adrs, 1):
            lines.append(f"{i}. {a}")
    return "\n".join(lines)


def _build_adr_zip(adr_result: ADRGenerationResult) -> bytes:
    """Build a zip of ADR markdown files in memory."""
    import io
    import re
    import zipfile
    from datetime import date

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for adr in adr_result.adrs:
            num = str(adr.number).zfill(4)
            slug = re.sub(r"[^\w\s-]", "", adr.title.lower())
            slug = re.sub(r"[\s_]+", "-", slug).strip("-")[:60]
            filename = f"{num}-{slug}.md"

            drivers = "\n".join(f"* {d}" for d in adr.decision_drivers) or "* _(not specified)_"
            pos = "\n".join(f"* {c}" for c in adr.consequences_positive) or "* _(none)_"
            neg = "\n".join(f"* {c}" for c in adr.consequences_negative) or "* _(none)_"

            content_lines = [
                f"# {num}. {adr.title}\n",
                f"Date: {adr.date}\n",
                "## Status\n",
                f"{adr.status.value.capitalize()}\n",
                "## Context\n",
                f"{adr.context}\n",
                "## Decision Drivers\n",
                f"{drivers}\n",
                "## Decision\n",
                f"{adr.decision}\n",
                "## Positive Consequences\n",
                f"{pos}\n",
                "## Negative Consequences\n",
                f"{neg}\n",
            ]
            if adr.links:
                content_lines += ["## Links\n"] + [f"* {l}" for l in adr.links]

            zf.writestr(filename, "\n".join(content_lines))

    buf.seek(0)
    return buf.read()
