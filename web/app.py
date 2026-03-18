"""Architecture Review Assistant — Streamlit Web UI (Redesign v2)."""

from __future__ import annotations

import html
import io
import os
import re
import sys
import threading
import zipfile
from pathlib import Path
from queue import Empty, Queue

import streamlit as st

st.set_page_config(
    page_title="arch-review — AI Architecture Review",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arch_review.adr_generator import ADRGenerator
from arch_review.engine import SUPPORTED_MODELS, ReviewEngine
from arch_review.models import ArchitectureInput, FindingCategory, ReviewResult, Severity
from arch_review.models_adr import ADRGenerationResult
from arch_review.squad import ReviewSquad
from arch_review.utils.extractor import extract_from_bytes, get_supported_formats

def e(text: str) -> str:
    return html.escape(str(text), quote=True)

# ── DESIGN SYSTEM (inspired by shadcn/Aceternity patterns from PDF) ────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main .block-container { padding: 0 !important; max-width: 100% !important; }
#MainMenu, footer, header { visibility: hidden; }

/* ── Hero section (inspired by animated-hero.tsx) ── */
.hero-section {
  background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 50%, #0f0f0f 100%);
  padding: 72px 40px 56px;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.hero-section::before {
  content: '';
  position: absolute; inset: 0;
  background: radial-gradient(ellipse 80% 50% at 50% 0%, rgba(99,102,241,.15) 0%, transparent 70%);
  pointer-events: none;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(99,102,241,.12); border: 1px solid rgba(99,102,241,.3);
  color: #a5b4fc; border-radius: 999px; padding: 6px 16px;
  font-size: 13px; font-weight: 500; margin-bottom: 28px;
  letter-spacing: .02em;
}
.hero-title {
  font-size: clamp(36px, 5vw, 64px); font-weight: 700;
  color: #f1f5f9; line-height: 1.1; margin: 0 0 8px;
  letter-spacing: -.03em;
}
.hero-title-accent {
  background: linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-subtitle {
  font-size: 17px; color: #94a3b8; max-width: 560px;
  margin: 12px auto 0; line-height: 1.7; font-weight: 400;
}

/* ── Vanish input (inspired by placeholders-and-vanish-input.tsx) ── */
.input-section {
  background: #0f0f0f;
  padding: 40px 40px 0;
}
.input-wrapper {
  max-width: 760px; margin: 0 auto;
  background: #18181b; border: 1px solid #27272a;
  border-radius: 16px; padding: 24px;
}
.input-label {
  font-size: 12px; font-weight: 600; letter-spacing: .08em;
  color: #71717a; text-transform: uppercase; margin-bottom: 10px;
}
.stTextArea > div > div > textarea {
  background: #09090b !important; color: #f4f4f5 !important;
  border: 1px solid #27272a !important; border-radius: 10px !important;
  font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
  font-size: 13px !important; line-height: 1.6 !important;
  padding: 14px !important; resize: vertical !important;
}
.stTextArea > div > div > textarea:focus {
  border-color: #6366f1 !important;
  box-shadow: 0 0 0 3px rgba(99,102,241,.15) !important;
}
.stTextArea > div > div > textarea::placeholder { color: #52525b !important; }

/* ── Upload zone ── */
.upload-zone {
  background: #09090b; border: 1.5px dashed #27272a;
  border-radius: 10px; padding: 20px; text-align: center;
  transition: border-color .2s;
}
.upload-zone:hover { border-color: #6366f1; }
[data-testid="stFileUploader"] {
  background: #09090b; border: 1.5px dashed #27272a;
  border-radius: 10px; padding: 12px;
}
[data-testid="stFileUploader"] label { color: #a1a1aa !important; }

/* ── Action buttons (inspired by shadcn button variants) ── */
.stButton > button {
  border-radius: 10px !important; font-weight: 500 !important;
  font-size: 14px !important; transition: all .2s !important;
  letter-spacing: .01em !important;
}
.btn-primary > button {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  border: none !important; color: white !important;
  padding: 0 24px !important; height: 44px !important;
  box-shadow: 0 4px 14px rgba(99,102,241,.35) !important;
}
.btn-primary > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 20px rgba(99,102,241,.45) !important;
}
.btn-outline > button {
  background: transparent !important; border: 1px solid #27272a !important;
  color: #a1a1aa !important; padding: 0 20px !important; height: 44px !important;
}
.btn-outline > button:hover {
  border-color: #6366f1 !important; color: #a5b4fc !important;
  background: rgba(99,102,241,.08) !important;
}

/* ── Results section ── */
.results-section {
  background: #0a0a0a; padding: 40px;
  min-height: 100vh;
}

/* ── Metric cards (inspired by pricing-cards.tsx card component) ── */
.metric-grid { display: grid; grid-template-columns: repeat(6,1fr); gap: 12px; margin-bottom: 28px; }
.metric-card {
  background: #18181b; border: 1px solid #27272a;
  border-radius: 12px; padding: 16px 12px; text-align: center;
}
.metric-card .number { font-size: 28px; font-weight: 700; line-height: 1; }
.metric-card .label { font-size: 11px; color: #71717a; margin-top: 4px; font-weight: 500; letter-spacing: .04em; }
.metric-critical .number { color: #f87171; }
.metric-high     .number { color: #fb923c; }
.metric-medium   .number { color: #fbbf24; }
.metric-low      .number { color: #60a5fa; }
.metric-info     .number { color: #94a3b8; }
.metric-total    .number { color: #a5b4fc; }

/* ── Finding cards (inspired by pricing card grid) ── */
.finding-card {
  background: #18181b; border: 1px solid #27272a;
  border-radius: 12px; padding: 20px; margin-bottom: 12px;
  transition: border-color .2s;
}
.finding-card:hover { border-color: #3f3f46; }
.finding-card.critical { border-left: 3px solid #ef4444; }
.finding-card.high     { border-left: 3px solid #f97316; }
.finding-card.medium   { border-left: 3px solid #eab308; }
.finding-card.low      { border-left: 3px solid #3b82f6; }
.finding-card.info     { border-left: 3px solid #6b7280; }
.finding-title { font-weight: 600; font-size: 15px; color: #f4f4f5; margin-bottom: 6px; }
.finding-meta  { font-size: 11px; color: #52525b; font-weight: 500; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 10px; }
.finding-desc  { font-size: 14px; color: #a1a1aa; line-height: 1.6; margin-bottom: 12px; }
.finding-rec   { background: rgba(34,197,94,.08); border: 1px solid rgba(34,197,94,.2); border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #86efac; margin-bottom: 8px; }
.finding-q     { font-size: 12px; color: #78716c; font-style: italic; margin-top: 8px; }
.finding-affects { font-size: 12px; color: #6366f1; margin-bottom: 8px; }
.sev-badge {
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 600; letter-spacing: .05em;
  text-transform: uppercase;
}
.sev-badge.critical { background: rgba(239,68,68,.15); color: #fca5a5; }
.sev-badge.high     { background: rgba(249,115,22,.15); color: #fdba74; }
.sev-badge.medium   { background: rgba(234,179,8,.15);  color: #fde047; }
.sev-badge.low      { background: rgba(59,130,246,.15); color: #93c5fd; }
.sev-badge.info     { background: rgba(107,114,128,.15);color: #d1d5db; }

/* ── Squad office (agent cards, inspired by testimonial carousel) ── */
.squad-section { background: #0f0f0f; padding: 32px 40px; }
.agent-card {
  background: #18181b; border: 1px solid #27272a;
  border-radius: 14px; padding: 18px 14px; text-align: center;
  transition: all .3s;
}
.agent-card.running {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,.12), 0 0 20px rgba(99,102,241,.08);
}
.agent-card.done    { border-color: #22c55e; box-shadow: 0 0 0 2px rgba(34,197,94,.1); }
.agent-card.error   { border-color: #ef4444; }
.agent-card.idle    { opacity: .5; }
.agent-emoji        { font-size: 26px; display: block; margin-bottom: 8px; }
.agent-label        { font-size: 13px; font-weight: 600; color: #f4f4f5; }
.agent-desc         { font-size: 11px; color: #52525b; margin-top: 3px; }
.agent-status       { font-size: 11px; color: #71717a; margin-top: 6px; }
.agent-count        { font-size: 12px; color: #6366f1; font-weight: 600; margin-top: 4px; }
.pipeline-connector { color: #27272a; font-size: 20px; text-align: center; padding-top: 24px; }

/* ── Memory section ── */
.memory-section { background: #0a0a0a; padding: 32px 40px; }
.memory-file-card {
  background: #18181b; border: 1px solid #27272a;
  border-radius: 12px; padding: 14px; text-align: center;
}
.memory-file-card.active { border-color: #22c55e; }
.memory-file-emoji { font-size: 20px; margin-bottom: 6px; }
.memory-file-name  { font-size: 12px; font-weight: 600; color: #a1a1aa; }
.memory-file-meta  { font-size: 11px; color: #52525b; margin-top: 3px; }
.memory-file-lessons { font-size: 11px; color: #818cf8; font-weight: 600; }

/* ── ADR cards ── */
.adr-card {
  background: #18181b; border: 1px solid #27272a;
  border-radius: 12px; padding: 20px; margin-bottom: 12px;
}
.adr-number { font-size: 11px; color: #6366f1; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
.adr-title  { font-size: 16px; font-weight: 600; color: #f4f4f5; margin: 6px 0 4px; }
.adr-status { display: inline-block; background: rgba(99,102,241,.12); color: #a5b4fc; border-radius: 999px; padding: 2px 10px; font-size: 11px; font-weight: 600; }

/* ── Tabs (override streamlit) ── */
.stTabs [data-baseweb="tab-list"] {
  background: #18181b; border-radius: 10px; padding: 4px;
  gap: 2px; border: 1px solid #27272a;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important; color: #71717a !important;
  border-radius: 8px !important; font-size: 13px !important;
  font-weight: 500 !important; padding: 8px 16px !important;
  transition: all .15s !important;
}
.stTabs [aria-selected="true"] {
  background: #09090b !important; color: #f4f4f5 !important;
  border: 1px solid #27272a !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: #0f0f0f !important; border-right: 1px solid #1c1c1e !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stMultiSelect label { color: #71717a !important; font-size: 12px !important; }

/* ── Misc ── */
.stAlert { border-radius: 10px !important; }
.stSpinner { color: #6366f1 !important; }
[data-testid="stExpander"] {
  background: #18181b !important; border: 1px solid #27272a !important;
  border-radius: 12px !important;
}
[data-testid="stExpander"] summary { color: #a1a1aa !important; }
hr { border-color: #1c1c1e !important; }
h1,h2,h3 { color: #f4f4f5 !important; }
p, li { color: #a1a1aa; }
code { background: #18181b !important; color: #a5b4fc !important; }
.section-title {
  font-size: 18px; font-weight: 600; color: #f4f4f5;
  margin-bottom: 20px; display: flex; align-items: center; gap: 8px;
}
.section-title span { font-size: 20px; }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
ICONS = {Severity.CRITICAL:"🔴",Severity.HIGH:"🟠",Severity.MEDIUM:"🟡",Severity.LOW:"🔵",Severity.INFO:"⚪"}
SEV_CSS = {Severity.CRITICAL:"critical",Severity.HIGH:"high",Severity.MEDIUM:"medium",Severity.LOW:"low",Severity.INFO:"info"}
ENV_MAP = {"anthropic":"ANTHROPIC_API_KEY","openai":"OPENAI_API_KEY","google":"GEMINI_API_KEY","mistral":"MISTRAL_API_KEY"}
AGENT_META = {
    "security_agent":      {"emoji":"🔐","label":"Security",     "desc":"Auth · Secrets · Compliance"},
    "reliability_agent":   {"emoji":"🛡️","label":"Reliability",   "desc":"SPOFs · Resilience · Failover"},
    "cost_agent":          {"emoji":"💰","label":"Cost",           "desc":"FinOps · Sizing · Transfer"},
    "observability_agent": {"emoji":"📡","label":"Observability",  "desc":"Logs · Metrics · Tracing"},
    "synthesizer_agent":   {"emoji":"🧠","label":"Synthesizer",    "desc":"Cross-patterns · Priority"},
}
PLACEHOLDERS = [
    "Paste your architecture — components, flows, infrastructure...",
    "Describe your microservices, databases, and message queues...",
    "Share your cloud architecture — AWS, Azure, GCP...",
    "Drop a Mermaid diagram or plain text description...",
    "What does your system look like? Auth, APIs, storage...",
]
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

# ── Sidebar (settings) ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    st.divider()
    selected_model = st.selectbox("Model", list(SUPPORTED_MODELS.keys()), index=0)
    provider = SUPPORTED_MODELS.get(selected_model, "")
    st.caption(f"`{provider}`")
    api_key = st.text_input("API Key", type="password", placeholder="sk-ant-... / sk-... / etc.", help="Session only.")
    if api_key:
        os.environ[ENV_MAP.get(provider, "OPENAI_API_KEY")] = api_key
        st.success(f"✓ Set")
    st.divider()
    focus_areas = st.multiselect("Focus Areas", [c.value for c in FindingCategory], default=[], help="Leave empty = review all.")
    generate_adrs = st.toggle("Auto-generate ADRs", value=True)
    st.divider()
    st.caption("🏗️ arch-review · MIT · [GitHub](https://github.com/juliopessan/arch-review-assistant)")

# ── Hero section ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-section">
  <div class="hero-badge">✦ AI-Powered · Multi-Agent · Self-Evolving</div>
  <h1 class="hero-title">Your architecture,<br><span class="hero-title-accent">reviewed by experts</span></h1>
  <p class="hero-subtitle">4 specialized AI agents — Security, Reliability, Cost, Observability — run in parallel and learn from every review.</p>
</div>
""", unsafe_allow_html=True)

# ── Main tabs ──────────────────────────────────────────────────────────────────
tabs = st.tabs(["✦ Review", "🤖 Squad Office", "🔍 Findings", "📄 ADRs", "📤 Export", "🧠 Memory"])
tab_input, tab_squad, tab_findings, tab_adrs, tab_export, tab_memory = tabs

# ── Tab: Review (input) ────────────────────────────────────────────────────────
with tab_input:
    st.markdown('<div class="input-section">', unsafe_allow_html=True)

    c_left, c_right = st.columns([3, 2], gap="large")

    with c_left:
        st.markdown('<div class="input-label">Architecture Description</div>', unsafe_allow_html=True)
        arch_text = st.text_area(
            "arch", height=300, label_visibility="collapsed",
            placeholder=PLACEHOLDERS[0],
            value=st.session_state.get("arch_prefill", ""),
        )
        st.session_state.pop("arch_prefill", None)

        # Context
        context_text = st.text_input(
            "Business context (optional)",
            placeholder="e.g. LGPD compliance required · ~500 concurrent users · Azure",
        )

    with c_right:
        # File upload zone
        st.markdown('<div class="input-label">Upload Architecture File</div>', unsafe_allow_html=True)
        supported = get_supported_formats()
        uploaded = st.file_uploader(
            f"Upload",
            type=supported,
            label_visibility="collapsed",
            help=f"Supported: {', '.join('.' + f for f in supported)}",
        )

        if uploaded:
            with st.spinner(f"Extracting from `{uploaded.name}`..."):
                try:
                    extracted = extract_from_bytes(uploaded.read(), uploaded.name)
                    st.session_state["arch_prefill"] = extracted
                    st.success(f"✅ Extracted {len(extracted):,} chars from `{uploaded.name}`")
                    with st.expander("Preview extracted text"):
                        st.code(extracted[:800] + ("..." if len(extracted) > 800 else ""), language="text")
                    if st.button("Use this as input ↑", key="use_extracted"):
                        st.rerun()
                except Exception as exc:
                    st.error(f"Extraction failed: {exc}")

        st.divider()

        # Quick actions
        col_ex, col_clr = st.columns(2)
        with col_ex:
            if st.button("📋 Load example", use_container_width=True):
                st.session_state["arch_prefill"] = EXAMPLE_ARCH
                st.rerun()
        with col_clr:
            if st.button("🗑️ Clear all", use_container_width=True):
                for k in ["review_result","adr_result","squad_log","arch_prefill"]:
                    st.session_state.pop(k, None)
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Action buttons ─────────────────────────────────────────────────────────
    st.markdown('<div style="background:#0f0f0f;padding:24px 40px 40px">', unsafe_allow_html=True)
    no_key = not api_key and not any(os.environ.get(k) for k in ENV_MAP.values())

    b1, b2, b3 = st.columns([1, 1, 2], gap="medium")
    with b1:
        st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
        run_squad = st.button("🤖 Squad Review", use_container_width=True, disabled=not arch_text.strip(), help="4 parallel agents ~60s — deeper findings")
        st.markdown('</div>', unsafe_allow_html=True)
    with b2:
        st.markdown('<div class="btn-outline">', unsafe_allow_html=True)
        run_single = st.button("⚡ Quick Review", use_container_width=True, disabled=not arch_text.strip(), help="Single agent, fast")
        st.markdown('</div>', unsafe_allow_html=True)
    with b3:
        if not arch_text.strip():
            st.info("Paste an architecture description or upload a file to begin.")
        elif no_key:
            st.warning("⚠️ Set your API key in the sidebar (⚙️ icon, top left).")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Trigger single review ──────────────────────────────────────────────────
    if run_single and arch_text.strip():
        arch_input = ArchitectureInput(
            description=arch_text, context=context_text or None,
            focus_areas=[FindingCategory(f) for f in focus_areas],
        )
        with st.spinner(f"Running quick review with `{selected_model}`..."):
            try:
                result = ReviewEngine(model=selected_model).review(arch_input)
                st.session_state["review_result"] = result
                st.session_state.pop("adr_result", None)
            except Exception as exc:
                st.error(f"❌ {exc}"); st.stop()
        if generate_adrs:
            with st.spinner("Generating ADRs..."):
                try:
                    st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(result)
                except Exception as exc:
                    st.warning(f"ADR generation failed: {exc}")
        st.success("✅ Done — see **Findings** tab.")
        st.rerun()

    # ── Trigger squad review ───────────────────────────────────────────────────
    if run_squad and arch_text.strip():
        st.session_state.update({
            "squad_arch": arch_text, "squad_context": context_text,
            "squad_running": True, "squad_log": [],
        })
        for k in ["review_result","adr_result"]: st.session_state.pop(k, None)
        st.rerun()


# ── Tab: Squad Office ──────────────────────────────────────────────────────────
with tab_squad:
    st.markdown('<div class="squad-section">', unsafe_allow_html=True)
    st.markdown('<div class="section-title"><span>🤖</span> Squad Office — Virtual Workspace</div>', unsafe_allow_html=True)
    st.markdown('<p style="color:#52525b;font-size:14px;margin-bottom:28px">4 specialized agents run in parallel, then the Synthesizer consolidates findings. Each agent learns from every review.</p>', unsafe_allow_html=True)

    squad_log: list[dict] = st.session_state.get("squad_log", [])

    def _agent_state(name: str) -> tuple[str, str, int]:
        evts = [v for v in squad_log if v.get("agent") == name]
        if any(v["event"] == "error" for v in evts): return "error", "❌ failed", 0
        if any(v["event"] == "done"  for v in evts):
            count = next((v.get("count",0) for v in evts if v["event"]=="done"), 0)
            return "done", "✅ done", count
        if any(v["event"] == "start" for v in evts): return "running", "⏳ running...", 0
        return "idle", "waiting", 0

    spec_names = list(AGENT_META.keys())[:4]
    synth_name = list(AGENT_META.keys())[4]

    # 4 agents row
    cols = st.columns(9)
    agent_cols = [cols[0], cols[2], cols[4], cols[6]]
    arrow_cols = [cols[1], cols[3], cols[5]]

    for i, name in enumerate(spec_names):
        meta = AGENT_META[name]
        css, status, count = _agent_state(name)
        count_html = f'<div class="agent-count">{count} findings</div>' if count else ""
        with agent_cols[i]:
            st.markdown(f'<div class="agent-card {css}"><span class="agent-emoji">{meta["emoji"]}</span><div class="agent-label">{meta["label"]}</div><div class="agent-desc">{meta["desc"]}</div><div class="agent-status">{status}</div>{count_html}</div>', unsafe_allow_html=True)
        if i < 3:
            with arrow_cols[i]:
                st.markdown('<div class="pipeline-connector" style="padding-top:26px">⟶</div>', unsafe_allow_html=True)

    # Synthesizer
    st.markdown("<br>", unsafe_allow_html=True)
    s1, s2, s3 = st.columns([2, 1, 2])
    with s2:
        meta = AGENT_META[synth_name]
        css, status, count = _agent_state(synth_name)
        count_html = f'<div class="agent-count">{count} findings</div>' if count else ""
        st.markdown(f'<div class="agent-card {css}"><span class="agent-emoji">{meta["emoji"]}</span><div class="agent-label">{meta["label"]}</div><div class="agent-desc">{meta["desc"]}</div><div class="agent-status">{status}</div>{count_html}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Run squad if triggered ─────────────────────────────────────────────────
    if st.session_state.get("squad_running"):
        arch_input = ArchitectureInput(
            description=st.session_state.get("squad_arch",""),
            context=st.session_state.get("squad_context") or None,
        )

        event_q: Queue = Queue()

        def _run_squad(q: Queue) -> None:
            import asyncio, json as _j
            from arch_review.squad.squad import ReviewSquad as _Squad
            from arch_review.squad.prompts import build_synthesizer_prompt as _bsp, SYNTHESIZER_SYSTEM as _SS
            import litellm as _ll

            async def _async():
                squad = _Squad(model=selected_model)
                arch  = squad.utils_sanitize(arch_input.description) if hasattr(squad, "utils_sanitize") else arch_input.description
                ctx   = arch_input.context or ""
                sp    = squad.squad_memory.get_recurring_patterns()

                tasks_info = []
                for name, system, prompt_fn in squad.AGENTS:
                    lessons = squad.agent_memories[name].get_lessons_section()
                    prompt  = prompt_fn(arch, ctx, lessons, sp)
                    q.put({"event":"start","agent":name})
                    tasks_info.append((name, system, prompt))

                async def _call(name, system, prompt):
                    try:
                        r = await asyncio.to_thread(_ll.completion, model=squad.model,
                            messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
                            temperature=squad.temperature, max_tokens=squad.max_tokens)
                        data = squad._parse_json(r.choices[0].message.content or "", name)
                        q.put({"event":"done","agent":name,"count":len(data.get("findings",[])),"data":data})
                        return name, data
                    except Exception as ex:
                        q.put({"event":"error","agent":name,"error":str(ex)})
                        return name, {"findings":[],"agent_insight":"","lesson_for_memory":""}

                results = await asyncio.gather(*[_call(n,s,p) for n,s,p in tasks_info])

                all_findings, insights = [], []
                from arch_review.squad.squad import AgentResult as _AR
                agent_results = []
                for name, data in results:
                    ar = _AR(agent_name=name)
                    ar.findings = data.get("findings",[]); ar.insight = data.get("agent_insight",""); ar.lesson = data.get("lesson_for_memory","")
                    agent_results.append(ar)
                    all_findings.extend(ar.findings)
                    if ar.insight: insights.append(f"[{name}] {ar.insight}")

                q.put({"event":"start","agent":"synthesizer_agent"})
                sm = squad.agent_memories["synthesizer_agent"]
                sp2 = build_synthesizer_prompt(arch, ctx, _j.dumps(all_findings,indent=2), insights, sm.get_lessons_section(), sp) if False else _bsp(arch, ctx, _j.dumps(all_findings,indent=2), insights, sm.get_lessons_section(), sp)
                try:
                    sr = await asyncio.to_thread(_ll.completion, model=squad.model,
                        messages=[{"role":"system","content":_SS},{"role":"user","content":sp2}],
                        temperature=squad.temperature, max_tokens=squad.max_tokens)
                    sdata = squad._parse_json(sr.choices[0].message.content or "", "synthesizer_agent")
                    q.put({"event":"done","agent":"synthesizer_agent","count":len(sdata.get("findings",[])),"data":sdata})
                except Exception as ex:
                    q.put({"event":"error","agent":"synthesizer_agent","error":str(ex)})
                    sdata = {"findings":all_findings}

                from arch_review.models import ReviewResult as _RR
                ff = squad._build_findings(sdata.get("findings", all_findings))
                sm2 = squad._build_summary(ff, sdata.get("overall_assessment",""))
                review = _RR(input=arch_input, findings=ff, summary=sm2,
                    senior_architect_questions=sdata.get("senior_architect_questions",[]),
                    recommended_adrs=sdata.get("recommended_adrs",[]), model_used=f"squad:{squad.model}")
                squad._update_memories(agent_results, sdata.get("lesson_for_memory",""), arch[:100], sdata.get("cross_patterns",[]), sm2)
                q.put({"event":"result","result":review})

            asyncio.run(_async())
            q.put({"event":"finished"})

        thread = threading.Thread(target=_run_squad, args=(event_q,), daemon=True)
        thread.start()

        progress_ph = st.empty()
        with progress_ph:
            with st.spinner("Squad running — agents working in parallel..."):
                while True:
                    try: ev = event_q.get(timeout=180)
                    except Empty: st.error("Squad timed out."); break
                    if ev["event"] in ("start","done","error"):
                        squad_log.append(ev); st.session_state["squad_log"] = squad_log
                    elif ev["event"] == "result":
                        st.session_state["review_result"] = ev["result"]
                    elif ev["event"] == "finished":
                        break

        st.session_state["squad_running"] = False
        if generate_adrs and "review_result" in st.session_state:
            with st.spinner("Generating ADRs..."):
                try:
                    st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(st.session_state["review_result"])
                except Exception: pass
        st.rerun()

    if "review_result" in st.session_state and not st.session_state.get("squad_running"):
        r = st.session_state["review_result"]
        if "squad:" in r.model_used:
            s = r.summary
            st.success(f"✅ Squad complete — **{s.total_findings} findings** · {s.critical_count} critical · {s.high_count} high")
            if s.top_risk: st.warning(f"⚠️ Top risk: **{e(s.top_risk)}**")
            st.info("→ See the **Findings** tab for the full report.")
        else:
            st.info("Run a **Squad Review** from the Review tab to see live agent activity here.")

    st.markdown('</div>', unsafe_allow_html=True)


# ── Tab: Findings ──────────────────────────────────────────────────────────────
with tab_findings:
    st.markdown('<div class="results-section">', unsafe_allow_html=True)
    if "review_result" not in st.session_state:
        st.markdown('<div style="text-align:center;padding:80px 0"><p style="font-size:48px">🔍</p><p style="color:#52525b;font-size:16px">Run a review first</p></div>', unsafe_allow_html=True)
    else:
        result: ReviewResult = st.session_state["review_result"]
        s = result.summary

        # Metric cards (pricing card style)
        st.markdown(f"""
        <div class="metric-grid">
          <div class="metric-card metric-critical"><div class="number">{s.critical_count}</div><div class="label">Critical</div></div>
          <div class="metric-card metric-high">   <div class="number">{s.high_count}</div>    <div class="label">High</div></div>
          <div class="metric-card metric-medium">  <div class="number">{s.medium_count}</div>  <div class="label">Medium</div></div>
          <div class="metric-card metric-low">     <div class="number">{s.low_count}</div>     <div class="label">Low</div></div>
          <div class="metric-card metric-info">    <div class="number">{s.info_count}</div>    <div class="label">Info</div></div>
          <div class="metric-card metric-total">   <div class="number">{s.total_findings}</div><div class="label">Total</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Model: `{result.model_used}`")

        if s.overall_assessment:
            with st.expander("📋 Overall Assessment", expanded=True):
                st.markdown(f'<p style="color:#a1a1aa;line-height:1.7">{e(s.overall_assessment)}</p>', unsafe_allow_html=True)

        if result.senior_architect_questions:
            with st.expander("❓ Opening Questions"):
                for i,q in enumerate(result.senior_architect_questions,1):
                    st.markdown(f'<p style="color:#a1a1aa"><span style="color:#6366f1;font-weight:600">{i}.</span> {e(q)}</p>', unsafe_allow_html=True)

        st.markdown('<div class="section-title" style="margin-top:24px"><span>⚡</span> Findings</div>', unsafe_allow_html=True)

        sev_filter = st.multiselect("Filter severity", [sv.value for sv in Severity], default=[sv.value for sv in Severity], horizontal=True)
        filtered = [f for f in result.findings if f.severity.value in sev_filter]

        for finding in filtered:
            css = SEV_CSS[finding.severity]
            cat = finding.category.value.upper().replace("_"," ")
            comps = f'<div class="finding-affects">🔗 {e(", ".join(finding.affected_components))}</div>' if finding.affected_components else ""
            qs = "".join(f'<span style="color:#71717a;font-style:italic">"{e(q)}" </span>' for q in finding.questions_to_ask)
            st.markdown(f"""
            <div class="finding-card {css}">
              <div class="finding-meta"><span class="sev-badge {css}">{finding.severity.value}</span> &nbsp; {e(cat)}</div>
              <div class="finding-title">{e(finding.title)}</div>
              <div class="finding-desc">{e(finding.description)}</div>
              {comps}
              <div class="finding-rec">✅ {e(finding.recommendation)}</div>
              {f'<div class="finding-q">💬 {qs}</div>' if qs else ""}
            </div>
            """, unsafe_allow_html=True)

        if result.recommended_adrs:
            st.markdown('<div class="section-title" style="margin-top:28px"><span>📌</span> Recommended ADRs</div>', unsafe_allow_html=True)
            for i,t in enumerate(result.recommended_adrs,1):
                st.markdown(f'<p><span style="color:#6366f1;font-weight:600">{i}.</span> <span style="color:#a1a1aa">{e(t)}</span></p>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ── Tab: ADRs ──────────────────────────────────────────────────────────────────
with tab_adrs:
    st.markdown('<div class="results-section">', unsafe_allow_html=True)
    if "review_result" not in st.session_state:
        st.markdown('<div style="text-align:center;padding:80px 0"><p style="font-size:48px">📄</p><p style="color:#52525b">Run a review first</p></div>', unsafe_allow_html=True)
    elif "adr_result" not in st.session_state:
        c1,c2 = st.columns([1,3])
        with c1:
            st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
            if st.button("⚡ Generate ADRs", use_container_width=True):
                with st.spinner("Generating..."):
                    try:
                        st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(st.session_state["review_result"])
                        st.rerun()
                    except Exception as exc: st.error(str(exc))
            st.markdown('</div>', unsafe_allow_html=True)
        with c2: st.info("ADRs not yet generated. Click to generate.")
    else:
        adr_result: ADRGenerationResult = st.session_state["adr_result"]
        st.success(f"✅ {adr_result.total_generated} ADR(s) — `{adr_result.model_used}`")
        for adr in adr_result.adrs:
            num = str(adr.number).zfill(4)
            with st.expander(f"ADR-{num} — {adr.title}"):
                st.markdown(f'<div class="adr-number">ADR-{num}</div><div class="adr-title">{e(adr.title)}</div><span class="adr-status">{adr.status.value}</span>', unsafe_allow_html=True)
                st.markdown("---")
                st.markdown(f"**Context**"); st.write(adr.context)
                if adr.decision_drivers:
                    st.markdown("**Decision Drivers**")
                    for d in adr.decision_drivers: st.markdown(f"- {d}")
                if adr.considered_options:
                    st.markdown("**Options Considered**")
                    for opt in adr.considered_options:
                        oc1,oc2 = st.columns(2)
                        oc1.markdown(f"**{opt.title}**"); oc1.write(opt.description)
                        if opt.pros:
                            oc1.markdown("✅ Pros")
                            for p in opt.pros: oc1.markdown(f"- {p}")
                        if opt.cons:
                            oc2.markdown("⚠️ Cons")
                            for c in opt.cons: oc2.markdown(f"- {c}")
                st.markdown("**Decision**"); st.success(adr.decision)
                if adr.consequences_positive or adr.consequences_negative:
                    p2,n2 = st.columns(2)
                    if adr.consequences_positive:
                        p2.markdown("✅ Positive")
                        for c in adr.consequences_positive: p2.markdown(f"- {c}")
                    if adr.consequences_negative:
                        n2.markdown("⚠️ Negative")
                        for c in adr.consequences_negative: n2.markdown(f"- {c}")
    st.markdown('</div>', unsafe_allow_html=True)


# ── Tab: Export ────────────────────────────────────────────────────────────────
with tab_export:
    st.markdown('<div class="results-section">', unsafe_allow_html=True)
    if "review_result" not in st.session_state:
        st.markdown('<div style="text-align:center;padding:80px 0"><p style="font-size:48px">📤</p><p style="color:#52525b">Run a review first</p></div>', unsafe_allow_html=True)
    else:
        result: ReviewResult = st.session_state["review_result"]
        st.markdown('<div class="section-title"><span>📤</span> Export</div>', unsafe_allow_html=True)
        ec1,ec2 = st.columns(2)
        with ec1:
            st.markdown("**JSON** — for CI/CD pipelines")
            st.download_button("⬇️ review.json", result.model_dump_json(indent=2), "arch-review.json","application/json",use_container_width=True)
        with ec2:
            st.markdown("**Markdown** — Confluence / Notion / GitHub")
            st.download_button("⬇️ review.md", _build_md(result), "arch-review.md","text/markdown",use_container_width=True)
        if "adr_result" in st.session_state:
            st.divider()
            st.markdown('<div class="section-title"><span>📄</span> ADRs</div>', unsafe_allow_html=True)
            adr_result: ADRGenerationResult = st.session_state["adr_result"]
            st.download_button(f"⬇️ {adr_result.total_generated} ADR(s) as .zip", _build_adr_zip(adr_result),"adrs.zip","application/zip",use_container_width=True)
            st.caption("Unzip into `docs/adr/` and commit.")
        st.divider()
        st.markdown("**Preview**")
        st.code(_build_md(result), language="markdown")
    st.markdown('</div>', unsafe_allow_html=True)


# ── Tab: Memory ────────────────────────────────────────────────────────────────
with tab_memory:
    st.markdown('<div class="memory-section">', unsafe_allow_html=True)
    st.markdown('<div class="section-title"><span>🧠</span> Agent Memory & Evolution</div>', unsafe_allow_html=True)
    st.markdown('<p style="color:#52525b;font-size:14px;margin-bottom:24px">Stored in <code>~/.arch-review/memory/</code>. Each agent learns and improves with every squad review.</p>', unsafe_allow_html=True)

    from arch_review.squad.memory import DEFAULT_MEMORY_DIR, AgentMemory, SquadMemory
    mem_dir = DEFAULT_MEMORY_DIR
    agents_list = ["security_agent","reliability_agent","cost_agent","observability_agent","synthesizer_agent"]

    mcols = st.columns(5)
    for i, name in enumerate(agents_list):
        meta = AGENT_META[name]
        f = mem_dir / f"{name}.md"
        exists = f.exists()
        size = f"{f.stat().st_size:,}b" if exists else "—"
        lessons = f.read_text().count("## Lesson") if exists else 0
        css = "active" if exists else ""
        with mcols[i]:
            st.markdown(f'<div class="memory-file-card {css}"><div class="memory-file-emoji">{meta["emoji"]}</div><div class="memory-file-name">{meta["label"]}</div><div class="memory-file-meta">{size}</div><div class="memory-file-lessons">{lessons} lessons</div></div>', unsafe_allow_html=True)

    sqf = mem_dir / "SQUAD_MEMORY.md"
    if sqf.exists():
        reviews = sqf.read_text().count("## Review [")
        patterns = sqf.read_text().count("## Cross-Agent Pattern")
        st.markdown(f'<div style="background:#18181b;border:1px solid #fde047;border-radius:10px;padding:14px;margin:16px 0"><span style="font-size:16px">📊</span> <strong style="color:#f4f4f5">SQUAD_MEMORY.md</strong> <span style="color:#71717a;font-size:13px">— {reviews} reviews · {patterns} cross-agent patterns</span></div>', unsafe_allow_html=True)

    st.divider()
    sel = st.selectbox("View agent memory", agents_list, format_func=lambda n: f"{AGENT_META[n]['emoji']} {AGENT_META[n]['label']}")
    mf = mem_dir / f"{sel}.md"
    if mf.exists():
        t1,t2 = st.tabs(["📖 Full", "📝 Lessons only"])
        with t1: st.code(mf.read_text(), language="markdown")
        with t2:
            content = mf.read_text()
            section = content.split("---",1)[1].strip() if "---" in content else "(no lessons yet)"
            st.code(section, language="markdown")
    else:
        st.info(f"No memory for `{sel}` yet — run a squad review first.")

    st.divider()
    st.markdown("**Squad Memory**")
    if sqf.exists():
        st.code(sqf.read_text(), language="markdown")
    else:
        st.info("No squad memory yet.")

    st.divider()
    if st.button("🗑️ Reset all memories", type="secondary"):
        if st.session_state.get("confirm_reset"):
            for a in agents_list:
                f = mem_dir / f"{a}.md"
                if f.exists(): f.unlink()
                AgentMemory(a, mem_dir)
            if sqf.exists(): sqf.unlink()
            SquadMemory(mem_dir)
            st.session_state.pop("confirm_reset", None)
            st.success("✓ Reset done.")
            st.rerun()
        else:
            st.session_state["confirm_reset"] = True
            st.warning("Click again to confirm — this cannot be undone.")

    st.markdown('</div>', unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────
def _build_md(result: ReviewResult) -> str:
    s = result.summary
    lines = ["# Architecture Review Report", f"\n> Model: `{result.model_used}`\n",
        "## Summary\n","| Severity | Count |","|----------|-------|",
        f"| 🔴 Critical | {s.critical_count} |",f"| 🟠 High | {s.high_count} |",
        f"| 🟡 Medium | {s.medium_count} |",f"| 🔵 Low | {s.low_count} |",
        f"| ⚪ Info | {s.info_count} |",f"| **Total** | **{s.total_findings}** |",
        f"\n## Overall Assessment\n\n{s.overall_assessment}"]
    if result.senior_architect_questions:
        lines += ["\n## Opening Questions\n"] + [f"- {q}" for q in result.senior_architect_questions]
    lines.append("\n## Findings\n")
    for f in result.findings:
        cat = f.category.value.upper().replace("_"," ")
        lines += [f"\n### {ICONS[f.severity]} {f.title}",
            f"\n**Severity:** {f.severity.value} | **Category:** {cat}\n",f"{f.description}\n"]
        if f.affected_components: lines.append(f"**Affected:** {', '.join(f.affected_components)}\n")
        lines.append(f"**Recommendation:** {f.recommendation}\n")
        if f.questions_to_ask: lines += ["**Questions:**"] + [f"- {q}" for q in f.questions_to_ask]
    if result.recommended_adrs:
        lines += ["\n## Recommended ADRs\n"] + [f"{i}. {a}" for i,a in enumerate(result.recommended_adrs,1)]
    return "\n".join(lines)

def _build_adr_zip(adr_result: ADRGenerationResult) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for adr in adr_result.adrs:
            num = str(adr.number).zfill(4)
            slug = re.sub(r"[\s_]+","-",re.sub(r"[^\w\s-]","",adr.title.lower())).strip("-")[:60]
            drivers = "\n".join(f"* {d}" for d in adr.decision_drivers) or "* _(not specified)_"
            pos = "\n".join(f"* {c}" for c in adr.consequences_positive) or "* _(none)_"
            neg = "\n".join(f"* {c}" for c in adr.consequences_negative) or "* _(none)_"
            body = "\n".join([f"# {num}. {adr.title}\n",f"Date: {adr.date}\n",
                f"## Status\n\n{adr.status.value.capitalize()}\n",
                f"## Context\n\n{adr.context}\n",f"## Decision Drivers\n\n{drivers}\n",
                f"## Decision\n\n{adr.decision}\n",
                f"## Positive Consequences\n\n{pos}\n",f"## Negative Consequences\n\n{neg}\n",
            ] + (["## Links\n"] + [f"* {lnk}" for lnk in adr.links] if adr.links else []))
            zf.writestr(f"{num}-{slug}.md", body)
    buf.seek(0)
    return buf.read()
