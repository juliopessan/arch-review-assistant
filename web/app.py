"""Architecture Review Assistant — Streamlit Web UI."""

from __future__ import annotations

import html
import io
import os
import re
import sys
import zipfile
from pathlib import Path

import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Architecture Review Assistant",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arch_review.adr_generator import ADRGenerator
from arch_review.engine import SUPPORTED_MODELS, ReviewEngine
from arch_review.models import ArchitectureInput, FindingCategory, ReviewResult, Severity
from arch_review.models_adr import ADRGenerationResult

# ── Security helper ────────────────────────────────────────────────────────────

def e(text: str) -> str:
    """Escape LLM/user content before injecting into HTML."""
    return html.escape(str(text), quote=True)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.sev-critical{background:#fef2f2;border-left:4px solid #ef4444;padding:12px 16px;border-radius:4px;margin:8px 0}
.sev-high    {background:#fff7ed;border-left:4px solid #f97316;padding:12px 16px;border-radius:4px;margin:8px 0}
.sev-medium  {background:#fefce8;border-left:4px solid #eab308;padding:12px 16px;border-radius:4px;margin:8px 0}
.sev-low     {background:#eff6ff;border-left:4px solid #3b82f6;padding:12px 16px;border-radius:4px;margin:8px 0}
.sev-info    {background:#f9fafb;border-left:4px solid #9ca3af;padding:12px 16px;border-radius:4px;margin:8px 0}
.ftitle{font-weight:600;font-size:15px;margin-bottom:4px}
.frec  {color:#166534;margin-top:8px;font-size:13px}
.fq    {color:#854d0e;font-size:13px}
.stTextArea textarea{font-family:monospace;font-size:13px}
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
ICONS = {
    Severity.CRITICAL: "🔴", Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡", Severity.LOW: "🔵", Severity.INFO: "⚪",
}
CSS_CLASS = {
    Severity.CRITICAL: "sev-critical", Severity.HIGH: "sev-high",
    Severity.MEDIUM: "sev-medium", Severity.LOW: "sev-low", Severity.INFO: "sev-info",
}
ENV_MAP = {
    "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY", "mistral": "MISTRAL_API_KEY",
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
- All services on a single EC2 t3.medium
- No CDN, no caching layer
- Logs written to local files
- RabbitMQ on same EC2 instance
- No staging environment"""

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏗️ arch-review")
    st.caption("AI-powered architecture review")
    st.divider()

    st.subheader("⚙️ Model")
    selected_model = st.selectbox("LLM provider", list(SUPPORTED_MODELS.keys()), index=0)
    provider = SUPPORTED_MODELS.get(selected_model, "")
    st.caption(f"Provider: `{provider}`")

    st.subheader("🔑 API Key")
    api_key = st.text_input(
        "API Key", type="password",
        placeholder="sk-ant-... / sk-... / etc.",
        help="Session memory only — never logged or persisted.",
    )
    if api_key:
        env_var = ENV_MAP.get(provider, "OPENAI_API_KEY")
        os.environ[env_var] = api_key
        st.success(f"✓ `{env_var}` set for this session")

    st.subheader("🎯 Focus Areas")
    focus_areas = st.multiselect(
        "Limit review to (optional)",
        [c.value for c in FindingCategory],
        default=[],
        help="Leave empty to review everything.",
    )

    st.subheader("📄 ADR Generator")
    generate_adrs = st.toggle("Generate ADRs after review", value=True)

    st.divider()
    st.caption("📖 [GitHub](https://github.com/juliopessan/arch-review-assistant) · MIT")

# ── Main ───────────────────────────────────────────────────────────────────────
st.title("🏗️ Architecture Review Assistant")
st.caption("Paste your architecture and get a senior architect's review in seconds.")

tab_input, tab_findings, tab_adrs, tab_export = st.tabs([
    "📝 Input", "🔍 Findings", "📄 ADRs", "📤 Export"
])

# ── Tab: Input ─────────────────────────────────────────────────────────────────
with tab_input:
    col1, col2 = st.columns([3, 1])
    with col1:
        arch_text = st.text_area(
            "Architecture description", height=380,
            placeholder="Paste your architecture — prose, Mermaid, bullet points...",
        )
    with col2:
        st.markdown("**Context (optional)**")
        context_text = st.text_area(
            "Context", height=180, label_visibility="collapsed",
            placeholder="e.g. LGPD compliance. ~500 users. Azure.",
        )
        if st.button("📋 Load example", use_container_width=True):
            st.session_state["load_example"] = True
            st.rerun()
        if st.button("🗑️ Clear", use_container_width=True):
            for k in ["review_result", "adr_result"]:
                st.session_state.pop(k, None)
            st.rerun()

    if st.session_state.pop("load_example", False):
        arch_text = EXAMPLE_ARCH

    st.divider()
    run_col, info_col = st.columns([1, 3])
    with run_col:
        run_clicked = st.button("🚀 Run Review", type="primary",
                                use_container_width=True, disabled=not arch_text.strip())
    with info_col:
        if not arch_text.strip():
            st.info("Paste an architecture description to begin.")
        elif not api_key and not any(os.environ.get(k) for k in ENV_MAP.values()):
            st.warning("⚠️ Set an API key in the sidebar before running.")

    if run_clicked and arch_text.strip():
        arch_input = ArchitectureInput(
            description=arch_text,
            context=context_text or None,
            focus_areas=[FindingCategory(f) for f in focus_areas],
        )
        with st.spinner(f"Reviewing with `{selected_model}`..."):
            try:
                result = ReviewEngine(model=selected_model).review(arch_input)
                st.session_state["review_result"] = result
                st.session_state.pop("adr_result", None)
            except Exception as exc:
                st.error(f"❌ Review failed: {exc}")
                st.stop()

        if generate_adrs:
            with st.spinner("Generating ADRs..."):
                try:
                    adr_r = ADRGenerator(model=selected_model).from_review(result)
                    st.session_state["adr_result"] = adr_r
                except Exception as exc:
                    st.warning(f"ADR generation failed: {exc}")

        st.success("✅ Done — see the **Findings** tab.")
        st.rerun()

# ── Tab: Findings ──────────────────────────────────────────────────────────────
with tab_findings:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    else:
        result: ReviewResult = st.session_state["review_result"]
        s = result.summary

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("🔴 Critical", s.critical_count)
        m2.metric("🟠 High",     s.high_count)
        m3.metric("🟡 Medium",   s.medium_count)
        m4.metric("🔵 Low",      s.low_count)
        m5.metric("⚪ Info",     s.info_count)
        m6.metric("📊 Total",    s.total_findings)
        st.divider()

        with st.expander("📋 Overall Assessment", expanded=True):
            st.write(s.overall_assessment)

        if result.senior_architect_questions:
            with st.expander("❓ Opening Questions"):
                for i, q in enumerate(result.senior_architect_questions, 1):
                    st.markdown(f"**{i}.** {q}")

        st.subheader("Findings")
        sev_filter = st.multiselect(
            "Filter by severity",
            [sv.value for sv in Severity],
            default=[sv.value for sv in Severity],
            horizontal=True,
        )
        filtered = [f for f in result.findings if f.severity.value in sev_filter]

        for finding in filtered:
            css = CSS_CLASS[finding.severity]
            icon = ICONS[finding.severity]
            cat = finding.category.value.upper().replace("_", " ")
            comps = e(", ".join(finding.affected_components)) if finding.affected_components else ""
            qs_html = " · ".join(f'"{e(q)}"' for q in finding.questions_to_ask)

            st.markdown(
                f'<div class="{css}">'
                f'<div class="ftitle">{icon} {e(finding.title)} '
                f'<span style="font-weight:400;color:#64748b;font-size:12px">[{e(cat)}]</span></div>'
                f'<div style="font-size:13px;margin-top:6px">{e(finding.description)}</div>'
                + (f'<div style="font-size:12px;color:#64748b;margin-top:6px">🔗 Affects: {comps}</div>' if comps else "")
                + f'<div class="frec">✅ {e(finding.recommendation)}</div>'
                + (f'<div class="fq">💬 {qs_html}</div>' if qs_html else "")
                + '</div>',
                unsafe_allow_html=True,
            )
            st.markdown("")

        if result.recommended_adrs:
            st.divider()
            st.subheader("📌 Recommended ADRs")
            for i, t in enumerate(result.recommended_adrs, 1):
                st.markdown(f"**{i}.** {t}")

# ── Tab: ADRs ──────────────────────────────────────────────────────────────────
with tab_adrs:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    elif "adr_result" not in st.session_state:
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("⚡ Generate ADRs", type="primary", use_container_width=True):
                with st.spinner("Generating..."):
                    try:
                        ar = ADRGenerator(model=selected_model).from_review(
                            st.session_state["review_result"]
                        )
                        st.session_state["adr_result"] = ar
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed: {exc}")
        with c2:
            st.info("ADRs were not generated automatically. Click to generate.")
    else:
        adr_result: ADRGenerationResult = st.session_state["adr_result"]
        st.success(f"✅ {adr_result.total_generated} ADR(s) — model: `{adr_result.model_used}`")

        for adr in adr_result.adrs:
            num = str(adr.number).zfill(4)
            with st.expander(f"📄 ADR-{num} — {adr.title}", expanded=False):
                cl, cr = st.columns(2)
                cl.markdown(f"**Status:** `{adr.status.value}`")
                cr.markdown(f"**Date:** {adr.date}")
                st.markdown("**Context**"); st.write(adr.context)

                if adr.decision_drivers:
                    st.markdown("**Decision Drivers**")
                    for d in adr.decision_drivers:
                        st.markdown(f"- {d}")

                if adr.considered_options:
                    st.markdown("**Options Considered**")
                    for opt in adr.considered_options:
                        st.markdown(f"**{opt.title}**"); st.write(opt.description)
                        oc1, oc2 = st.columns(2)
                        if opt.pros:
                            oc1.markdown("✅ **Pros**")
                            for p in opt.pros: oc1.markdown(f"- {p}")
                        if opt.cons:
                            oc2.markdown("⚠️ **Cons**")
                            for c in opt.cons: oc2.markdown(f"- {c}")

                st.markdown("**Decision**"); st.success(adr.decision)

                if adr.consequences_positive or adr.consequences_negative:
                    pc, nc = st.columns(2)
                    if adr.consequences_positive:
                        pc.markdown("✅ **Positive**")
                        for c in adr.consequences_positive: pc.markdown(f"- {c}")
                    if adr.consequences_negative:
                        nc.markdown("⚠️ **Negative**")
                        for c in adr.consequences_negative: nc.markdown(f"- {c}")

                if adr.consequences_neutral:
                    st.markdown("**Follow-up**")
                    for c in adr.consequences_neutral: st.markdown(f"- {c}")

# ── Tab: Export ────────────────────────────────────────────────────────────────
with tab_export:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    else:
        result: ReviewResult = st.session_state["review_result"]
        st.subheader("📤 Export Review")

        ec1, ec2 = st.columns(2)
        with ec1:
            st.markdown("**JSON** — for CI/CD pipelines")
            st.download_button("⬇️ review.json", result.model_dump_json(indent=2),
                               "arch-review.json", "application/json", use_container_width=True)
        with ec2:
            st.markdown("**Markdown** — for Confluence / Notion / GitHub")
            st.download_button("⬇️ review.md", _build_md(result),
                               "arch-review.md", "text/markdown", use_container_width=True)

        if "adr_result" in st.session_state:
            st.divider()
            st.subheader("📄 Export ADRs")
            adr_result: ADRGenerationResult = st.session_state["adr_result"]
            st.download_button(
                f"⬇️ {adr_result.total_generated} ADR(s) as .zip",
                _build_adr_zip(adr_result), "adrs.zip", "application/zip",
                use_container_width=True,
            )
            st.caption("Unzip into `docs/adr/` and commit.")

        st.divider()
        st.subheader("👁️ Markdown Preview")
        st.code(_build_md(result), language="markdown")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_md(result: ReviewResult) -> str:
    s = result.summary
    lines = [
        "# Architecture Review Report",
        f"\n> Model: `{result.model_used}`\n",
        "## Summary\n",
        "| Severity | Count |", "|----------|-------|",
        f"| 🔴 Critical | {s.critical_count} |",
        f"| 🟠 High | {s.high_count} |",
        f"| 🟡 Medium | {s.medium_count} |",
        f"| 🔵 Low | {s.low_count} |",
        f"| ⚪ Info | {s.info_count} |",
        f"| **Total** | **{s.total_findings}** |",
        f"\n## Overall Assessment\n\n{s.overall_assessment}",
    ]
    if result.senior_architect_questions:
        lines += ["\n## Opening Questions\n"] + [f"- {q}" for q in result.senior_architect_questions]
    lines.append("\n## Findings\n")
    for f in result.findings:
        cat = f.category.value.upper().replace("_", " ")
        lines += [
            f"\n### {ICONS[f.severity]} {f.title}",
            f"\n**Severity:** {f.severity.value} | **Category:** {cat}\n",
            f"{f.description}\n",
        ]
        if f.affected_components:
            lines.append(f"**Affected:** {', '.join(f.affected_components)}\n")
        lines.append(f"**Recommendation:** {f.recommendation}\n")
        if f.questions_to_ask:
            lines += ["**Questions:**"] + [f"- {q}" for q in f.questions_to_ask]
    if result.recommended_adrs:
        lines += ["\n## Recommended ADRs\n"] + [f"{i}. {a}" for i, a in enumerate(result.recommended_adrs, 1)]
    return "\n".join(lines)


def _build_adr_zip(adr_result: ADRGenerationResult) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for adr in adr_result.adrs:
            num = str(adr.number).zfill(4)
            slug = re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", adr.title.lower())).strip("-")[:60]
            drivers = "\n".join(f"* {d}" for d in adr.decision_drivers) or "* _(not specified)_"
            pos = "\n".join(f"* {c}" for c in adr.consequences_positive) or "* _(none)_"
            neg = "\n".join(f"* {c}" for c in adr.consequences_negative) or "* _(none)_"
            body = "\n".join([
                f"# {num}. {adr.title}\n",
                f"Date: {adr.date}\n",
                f"## Status\n\n{adr.status.value.capitalize()}\n",
                f"## Context\n\n{adr.context}\n",
                f"## Decision Drivers\n\n{drivers}\n",
                f"## Decision\n\n{adr.decision}\n",
                f"## Positive Consequences\n\n{pos}\n",
                f"## Negative Consequences\n\n{neg}\n",
            ] + (["## Links\n"] + [f"* {lnk}" for lnk in adr.links] if adr.links else []))
            zf.writestr(f"{num}-{slug}.md", body)
    buf.seek(0)
    return buf.read()
