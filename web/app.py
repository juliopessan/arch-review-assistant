"""Architecture Review Assistant — Streamlit Web UI v3 with i18n."""

from __future__ import annotations

import html, io, os, re, sys, threading, zipfile, random
from pathlib import Path
from queue import Empty, Queue

# ── sys.path must be set BEFORE any arch_review import ────────────────────────
# Using absolute resolved paths prevents duplicate module loading
# (which causes Pydantic "different class identity" validation errors)
_SRC = str(Path(__file__).parent.parent.joinpath("src").resolve())
_WEB = str(Path(__file__).parent.resolve())
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
if _WEB not in sys.path:
    sys.path.insert(0, _WEB)

import streamlit as st

st.set_page_config(
    page_title="arch-review",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from arch_review.adr_generator import ADRGenerator
from arch_review.engine import SUPPORTED_MODELS, ReviewEngine
from arch_review.models import ArchitectureInput, FindingCategory, ReviewResult, Severity
from arch_review.models_adr import ADRGenerationResult
from arch_review.squad import ReviewSquad
from i18n import get_t, TRANSLATIONS

# ── Language selection (must happen before t() is called) ─────────────────────
if "lang" not in st.session_state:
    st.session_state["lang"] = "en"

# ── Tesseract required check ───────────────────────────────────────────────────
try:
    from arch_review.utils.extractor import extract_from_bytes, get_supported_formats
except EnvironmentError as _tess_err:
    st.error(str(_tess_err))
    st.markdown("""
**Tesseract is required** for architecture file extraction (PDF, images).

Install it and restart the app:
```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt-get install tesseract-ocr

# Windows
# https://github.com/UB-Mannheim/tesseract/wiki
```
""")
    st.stop()

def esc(text: str) -> str:
    return html.escape(str(text), quote=True)

# ══════════════════════════════════════════════════════════════════════════════
#  CSS — Orange DNA Design System
#  Skill: orange-dna-style-guide
#  Palette:
#    #F04E37  primary orange      → buttons, active tabs, accents, badges
#    #2E2E2E  dark grey           → all body text / headings
#    #FF7A59  soft orange         → highlights, hover states
#    #FFF3F1  orange tint         → card backgrounds, sidebar, tinted fields
#    #FFE5DF  warm tint           → critical/warning backgrounds
#    #E0E0E0  neutral grey        → borders, dividers
#    #666666  muted               → captions, meta, labels
#    #F5F5F5  row alt             → alternating rows
#  Typography: Inter (web) / Arial (fallback) — weights 400/600/700/800
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Reset & base ─────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: 'Inter', Arial, sans-serif !important;
  color: #2E2E2E !important;
  -webkit-font-smoothing: antialiased;
}
.main .block-container {
  max-width: 1200px !important;
  padding: 0 2rem 4rem !important;
}
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }

/* ── Orange DNA app header bar ───────────────────────────────────────────────── */
.fc-topbar {
  background: #F04E37;
  margin: -1rem -2rem 0; padding: 12px 2rem 10px;
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 3px solid #d43e29;
}
.fc-topbar-brand {
  display: flex; align-items: center; gap: 10px;
}
.fc-topbar-logo {
  font-size: 1.1rem; font-weight: 800; color: #fff !important;
  -webkit-text-fill-color: #fff !important;
  letter-spacing: -.03em;
}
.fc-topbar-tag {
  font-size: .68rem; font-weight: 700; color: rgba(255,255,255,.7) !important;
  -webkit-text-fill-color: rgba(255,255,255,.7) !important;
  letter-spacing: .08em; text-transform: uppercase;
  background: rgba(0,0,0,.15); padding: 2px 8px; border-radius: 999px;
}
.fc-topbar-meta {
  font-size: .72rem; color: rgba(255,255,255,.65) !important;
  -webkit-text-fill-color: rgba(255,255,255,.65) !important;
}

/* ── Hero section ─────────────────────────────────────────────────────────── */
.fc-hero {
  padding: 28px 0 20px;
  border-bottom: 3px solid #F04E37;
  margin-bottom: 0;
}
.fc-hero-title {
  font-size: 2.6rem; font-weight: 800; color: #2E2E2E !important;
  -webkit-text-fill-color: #2E2E2E !important;
  letter-spacing: -.05em; line-height: 1.1; margin-bottom: 6px;
}
.fc-hero-title span { color: #F04E37 !important; -webkit-text-fill-color: #F04E37 !important; }
.fc-hero-sub {
  font-size: .95rem; color: #666 !important;
  -webkit-text-fill-color: #666 !important;
  font-weight: 400; line-height: 1.5;
}
.fc-hero-badges { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.fc-chip {
  display: inline-flex; align-items: center; gap: 5px;
  background: #F5F5F5; border: 1px solid #E0E0E0;
  color: #2E2E2E !important; -webkit-text-fill-color: #2E2E2E !important;
  border-radius: 6px; padding: 4px 10px;
  font-size: .75rem; font-weight: 600;
}
.fc-chip.orange {
  background: #FFF3F1; border-color: rgba(240,78,55,.3);
  color: #F04E37 !important; -webkit-text-fill-color: #F04E37 !important;
}

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 0 !important;
  background: #F5F5F5 !important;
  border-radius: 10px !important;
  padding: 4px !important;
  border: none !important;
  margin-top: 16px !important;
}
.stTabs [data-baseweb="tab"] {
  border-radius: 8px !important;
  font-size: .84rem !important; font-weight: 600 !important;
  padding: 7px 16px !important;
  color: #666 !important; -webkit-text-fill-color: #666 !important;
  background: transparent !important;
  border: none !important;
  transition: all .15s !important;
}
.stTabs [aria-selected="true"] {
  color: #fff !important; -webkit-text-fill-color: #fff !important;
  background: #F04E37 !important;
  box-shadow: 0 2px 8px rgba(240,78,55,.3) !important;
  font-weight: 700 !important;
}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
  color: #F04E37 !important; -webkit-text-fill-color: #F04E37 !important;
  background: #FFF3F1 !important;
}
/* Remove tab underline indicator */
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]    { display: none !important; }

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
  border-radius: 8px !important; font-weight: 700 !important;
  font-size: .88rem !important; transition: all .15s !important;
  letter-spacing: .01em !important;
}
.stButton > button[kind="primary"] {
  background: #F04E37 !important; border: none !important;
  color: #fff !important; -webkit-text-fill-color: #fff !important;
  box-shadow: 0 2px 8px rgba(240,78,55,.3) !important;
  padding: 10px 22px !important;
}
.stButton > button[kind="primary"]:hover {
  background: #d43e29 !important;
  box-shadow: 0 4px 16px rgba(240,78,55,.4) !important;
  transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
  border: 1.5px solid #F04E37 !important;
  color: #F04E37 !important; -webkit-text-fill-color: #F04E37 !important;
  background: #fff !important;
}
.stButton > button[kind="secondary"]:hover { background: #FFF3F1 !important; }

/* ── Inputs ───────────────────────────────────────────────────────────────── */
/* All input text — Orange DNA widget rule: always hardcode, never inherit */
input, select {
  color: #2E2E2E !important; -webkit-text-fill-color: #2E2E2E !important;
  background: #fff !important;
}
label {
  color: #555555 !important; -webkit-text-fill-color: #555555 !important;
  font-weight: 600 !important; font-size: .85rem !important;
}
.stTextArea textarea {
  font-family: 'JetBrains Mono','Fira Code',monospace !important;
  font-size: .83rem !important; border-radius: 8px !important;
  border: 1.5px solid #E0E0E0 !important; line-height: 1.6 !important;
  color: #2E2E2E !important; -webkit-text-fill-color: #2E2E2E !important;
  background: #fff !important;
}
.stTextArea textarea:focus {
  border-color: #F04E37 !important;
  box-shadow: 0 0 0 3px rgba(240,78,55,.1) !important;
  outline: none !important;
}
[data-testid="stFileUploaderDropzone"] {
  border-radius: 10px !important;
  border: 2px dashed rgba(240,78,55,.4) !important;
  background: #FFF3F1 !important;
  transition: border-color .2s !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: #F04E37 !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: #FFF3F1 !important;
  border-right: 1px solid rgba(240,78,55,.2) !important;
}
[data-testid="stSidebar"] section { padding-top: 1rem !important; }

/* ── Finding cards ────────────────────────────────────────────────────────── */
.scard {
  border-radius: 10px; padding: 16px 20px; margin-bottom: 12px;
  border: 1px solid #E0E0E0; background: #fff; color: #2E2E2E !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.scard.critical { border-left: 4px solid #F04E37; background: #FFF3F1; }
.scard.high     { border-left: 4px solid #FF7A59; background: #fff9f7; }
.scard.medium   { border-left: 4px solid #f59e0b; background: #fffdf0; }
.scard.low      { border-left: 4px solid #3b82f6; background: #f5f8ff; }
.scard.info     { border-left: 4px solid #9ca3af; background: #f9fafb; }
.scard-title  { font-weight: 700; font-size: .97rem; color: #2E2E2E; margin-bottom: 5px; }
.scard-meta   { font-size: .69rem; font-weight: 700; letter-spacing: .09em;
                text-transform: uppercase; color: #666; margin-bottom: 10px; }
.scard-desc   { font-size: .87rem; color: #2E2E2E; line-height: 1.65; margin-bottom: 10px; }
.scard-rec    { background: #FFF3F1; border: 1px solid rgba(240,78,55,.2);
                border-radius: 8px; padding: 9px 13px; font-size: .84rem;
                color: #c03020; margin-bottom: 6px; }
.scard-affects{ font-size: .78rem; color: #F04E37; font-weight: 600; margin-bottom: 6px; }
.scard-q      { font-size: .78rem; color: #666; font-style: italic; margin-top: 6px; }

/* ── Pills ────────────────────────────────────────────────────────────────── */
.pill {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: .68rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
}
.pill-critical { background: #F04E37; color: #fff !important; -webkit-text-fill-color: #fff !important; }
.pill-high     { background: #FFE5DF; color: #c03020 !important; -webkit-text-fill-color: #c03020 !important; border: 1px solid rgba(240,78,55,.3); }
.pill-medium   { background: #fef3c7; color: #92400e !important; -webkit-text-fill-color: #92400e !important; }
.pill-low      { background: #dbeafe; color: #1d4ed8 !important; -webkit-text-fill-color: #1d4ed8 !important; }
.pill-info     { background: #F5F5F5; color: #666 !important;    -webkit-text-fill-color: #666 !important; }

/* ── Stats row ────────────────────────────────────────────────────────────── */
.statrow { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
.stat {
  flex: 1; min-width: 76px; background: #fff; border: 1px solid #E0E0E0;
  border-radius: 10px; padding: 14px 10px; text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.stat .n { font-size: 1.85rem; font-weight: 800; line-height: 1.1; }
.stat .l { font-size: .67rem; font-weight: 700; letter-spacing: .07em;
           text-transform: uppercase; color: #666; margin-top: 4px; }
.stat-c .n { color: #F04E37; }
.stat-h .n { color: #FF7A59; }
.stat-m .n { color: #f59e0b; }
.stat-l .n { color: #3b82f6; }
.stat-i .n { color: #9ca3af; }
.stat-t .n { color: #2E2E2E; }

/* ── Memory cards ─────────────────────────────────────────────────────────── */
.memcard {
  background: #fff; border: 1px solid #E0E0E0;
  border-radius: 10px; padding: 14px 10px; text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.memcard.live { border-color: #F04E37; background: #FFF3F1; }
.memcard .ic  { font-size: 1.25rem; }
.memcard .nm  { font-size: .76rem; font-weight: 700; color: #2E2E2E; margin-top: 4px; }
.memcard .sz  { font-size: .67rem; color: #666; }
.memcard .ls  { font-size: .71rem; font-weight: 700; color: #F04E37; margin-top: 2px; }

/* ── ADR cards ────────────────────────────────────────────────────────────── */
.adrcard {
  background: #fff; border: 1px solid #E0E0E0;
  border-radius: 10px; padding: 18px 20px; margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.adrnum   { font-size: .71rem; font-weight: 700; color: #F04E37; letter-spacing: .08em; text-transform: uppercase; }
.adrtitle { font-size: 1rem; font-weight: 700; color: #2E2E2E; margin: 4px 0; }
.adrstatus{
  display: inline-block; background: #FFF3F1; color: #F04E37;
  border: 1px solid rgba(240,78,55,.3); border-radius: 999px;
  padding: 2px 10px; font-size: .69rem; font-weight: 700;
}

/* ── Section headings (H2 left bar — Orange DNA spec) ────────────────────────── */
.fc-h2 {
  font-size: 1.05rem; font-weight: 700; color: #2E2E2E;
  border-left: 4px solid #F04E37; padding-left: 12px;
  margin: 20px 0 12px; line-height: 1.4;
}
.fc-h3 {
  font-size: .92rem; font-weight: 700; color: #2E2E2E;
  border-left: 3px solid #FF7A59; padding-left: 10px;
  margin: 16px 0 8px;
}

/* ── Section rule (Orange DNA orange divider) ────────────────────────────────── */
.fc-rule { border: none; border-top: 2px solid #F04E37; opacity: .25; margin: 1.2rem 0; }

/* ── Metrics (native Streamlit) ───────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: #fff; border: 1px solid #E0E0E0;
  border-radius: 10px; padding: 14px !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
[data-testid="stMetricValue"] {
  color: #F04E37 !important; -webkit-text-fill-color: #F04E37 !important;
  font-weight: 800 !important;
}
[data-testid="stMetricLabel"] {
  color: #666 !important; -webkit-text-fill-color: #666 !important;
}

/* ── Expander ─────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid #E0E0E0 !important; border-radius: 10px !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.04) !important;
}
[data-testid="stExpander"] > details > summary {
  font-weight: 600 !important; color: #2E2E2E !important;
  padding: 12px 16px !important;
}
[data-testid="stExpander"] > details > summary:hover { color: #F04E37 !important; }

/* ── Alert banners ────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
  border-radius: 10px !important; border-left-width: 4px !important;
}
/* Success → Orange DNA orange tint */
[data-testid="stAlert"][kind="success"] {
  background: #FFF3F1 !important; border-color: #F04E37 !important;
}
/* Info → neutral */
[data-testid="stAlert"][kind="info"] {
  background: #F5F5F5 !important; border-color: #E0E0E0 !important;
}

/* ── Code ─────────────────────────────────────────────────────────────────── */
code {
  background: #FFF3F1 !important; color: #c03020 !important;
  border-radius: 4px !important; padding: 1px 5px !important;
  font-size: .88em !important;
}

/* ── Divider ──────────────────────────────────────────────────────────────── */
hr { border: none !important; border-top: 1px solid #E0E0E0 !important; margin: 1rem 0 !important; }

/* ── Caption ──────────────────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"],
small, .caption { color: #666 !important; -webkit-text-fill-color: #666 !important; }

/* ── Toggle ───────────────────────────────────────────────────────────────── */
[data-testid="stToggleSwitch"][aria-checked="true"] > div:first-child {
  background: #F04E37 !important;
}

/* ── Progress / spinner ───────────────────────────────────────────────────── */
[data-testid="stSpinner"] > div { border-top-color: #F04E37 !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
SEV_CSS  = {Severity.CRITICAL:"critical",Severity.HIGH:"high",Severity.MEDIUM:"medium",Severity.LOW:"low",Severity.INFO:"info"}
SEV_PILL = {Severity.CRITICAL:"pill-critical",Severity.HIGH:"pill-high",Severity.MEDIUM:"pill-medium",Severity.LOW:"pill-low",Severity.INFO:"pill-info"}
ENV_MAP  = {"anthropic":"ANTHROPIC_API_KEY","openai":"OPENAI_API_KEY","google":"GEMINI_API_KEY","mistral":"MISTRAL_API_KEY"}

EXAMPLE = """# E-commerce Order Processing System

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

# ── Helpers (defined BEFORE any UI code) ──────────────────────────────────────

def rand_msgs(lang: str) -> dict:
    """Return loading message pools for the given language."""
    def pool(prefix: str, count: int) -> list[str]:
        return [TRANSLATIONS[f"{prefix}.{i}"][lang] for i in range(1, count + 1)
                if f"{prefix}.{i}" in TRANSLATIONS]
    return {
        "review":    pool("loading.review", 10),
        "squad":     pool("loading.squad", 10),
        "synth":     pool("loading.synth", 5),
        "adr":       pool("loading.adr", 5),
        "ocr":       pool("loading.ocr", 5),
        "structure": pool("loading.structure", 5),
    }

def rand_msg(pool: list[str]) -> str:
    return random.choice(pool) if pool else "Loading..."

def _build_md(r: ReviewResult) -> str:
    s = r.summary
    lines = ["# Architecture Review Report", f"\n> Model: `{r.model_used}`\n",
        "## Summary\n", "| Severity | Count |", "|----------|-------|",
        f"| 🔴 Critical | {s.critical_count} |", f"| 🟠 High | {s.high_count} |",
        f"| 🟡 Medium | {s.medium_count} |", f"| 🔵 Low | {s.low_count} |",
        f"| ⚪ Info | {s.info_count} |", f"| **Total** | **{s.total_findings}** |",
        f"\n## Overall Assessment\n\n{s.overall_assessment}"]
    if r.senior_architect_questions:
        lines += ["\n## Opening Questions\n"] + [f"- {q}" for q in r.senior_architect_questions]
    lines.append("\n## Findings\n")
    for f in r.findings:
        cat = f.category.value.upper().replace("_", " ")
        lines += [f"\n### {f.severity.value.upper()} — {f.title}",
                  f"\n**Category:** {cat}\n\n{f.description}\n"]
        if f.affected_components:
            lines.append(f"**Affected:** {', '.join(f.affected_components)}\n")
        lines.append(f"**Recommendation:** {f.recommendation}\n")
        if f.questions_to_ask:
            lines += ["**Questions:**"] + [f"- {q}" for q in f.questions_to_ask]
    if r.recommended_adrs:
        lines += ["\n## Recommended ADRs\n"] + [f"{i}. {a}" for i, a in enumerate(r.recommended_adrs, 1)]
    return "\n".join(lines)

def _build_zip(ar: ADRGenerationResult) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for adr in ar.adrs:
            num = str(adr.number).zfill(4)
            slug = re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", adr.title.lower())).strip("-")[:60]
            d = "\n".join(f"* {x}" for x in adr.decision_drivers) or "* _(not specified)_"
            p = "\n".join(f"* {x}" for x in adr.consequences_positive) or "* _(none)_"
            n = "\n".join(f"* {x}" for x in adr.consequences_negative) or "* _(none)_"
            body = "\n".join([f"# {num}. {adr.title}\n", f"Date: {adr.date}\n",
                f"## Status\n\n{adr.status.value.capitalize()}\n",
                f"## Context\n\n{adr.context}\n", f"## Decision Drivers\n\n{d}\n",
                f"## Decision\n\n{adr.decision}\n",
                f"## Positive Consequences\n\n{p}\n", f"## Negative Consequences\n\n{n}\n",
            ] + (["## Links\n"] + [f"* {lk}" for lk in adr.links] if adr.links else []))
            zf.writestr(f"{num}-{slug}.md", body)
    buf.seek(0)
    return buf.read()

def _structure_ocr(raw_text: str, model: str) -> str:
    import litellm
    prompt = f"""You received raw text extracted via OCR from an architecture diagram or document.
Reconstruct it into clean, structured Markdown describing the software architecture.
Rules:
- Use ## headings: Components, Flow, Infrastructure, Integrations
- Use bullet points with component names and brief descriptions
- Preserve technical names exactly (e.g. "Microsoft Entra ID", "Copilot Studio", "Azure Service Bus")
- Describe implied flows/connections under ## Flow
- Remove OCR noise, keep all meaningful technical terms
- Output ONLY the Markdown, no preamble

RAW OCR TEXT:
---
{raw_text}
---"""
    try:
        r = litellm.completion(model=model,
            messages=[{"role":"system","content":"You reconstruct architecture descriptions from OCR. Output only clean Markdown."},
                      {"role":"user","content":prompt}],
            temperature=0.1, max_tokens=2048)
        result = (r.choices[0].message.content or "").strip()
        if result.startswith("```"):
            result = "\n".join(l for l in result.splitlines() if not l.startswith("```")).strip()
        return result if result else raw_text
    except Exception:
        return raw_text

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;padding:4px 0 12px">
      <span style="font-size:1.2rem">🏗️</span>
      <span style="font-weight:800;font-size:1rem;color:#2E2E2E">arch-review</span>
    </div>
    """, unsafe_allow_html=True)

    # Language toggle
    lang_choice = st.radio(
        "🌐 Language", ["🇺🇸 English", "🇧🇷 Português"],
        horizontal=True, label_visibility="collapsed"
    )
    lang = "pt" if "Português" in lang_choice else "en"
    st.session_state["lang"] = lang
    t = get_t(lang)
    msgs = rand_msgs(lang)

    st.markdown('<hr class="fc-rule">', unsafe_allow_html=True)

    # Model
    st.markdown(f'<div class="fc-h3">{t("sidebar.model")}</div>', unsafe_allow_html=True)
    selected_model = st.selectbox(
        t("sidebar.model"), list(SUPPORTED_MODELS.keys()),
        index=0, label_visibility="collapsed"
    )
    provider = SUPPORTED_MODELS.get(selected_model, "")
    st.caption(f"{t('sidebar.provider')} `{provider}`")

    # API Key
    api_key = st.text_input(
        "🔑 API Key", type="password",
        placeholder=t("sidebar.apikey.ph")
    )
    if api_key:
        os.environ[ENV_MAP.get(provider, "OPENAI_API_KEY")] = api_key
        st.success(t("sidebar.apikey.ok"))

    st.markdown('<hr class="fc-rule">', unsafe_allow_html=True)

    # Review options
    st.markdown(f'<div class="fc-h3">{t("sidebar.focus")}</div>', unsafe_allow_html=True)
    focus_areas = st.multiselect(
        t("sidebar.focus"), [c.value for c in FindingCategory],
        default=[], help=t("sidebar.focus.help"),
        label_visibility="collapsed"
    )
    gen_adrs = st.toggle(t("sidebar.adrs"), value=True)

    st.markdown('<hr class="fc-rule">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:.72rem;color:#666;line-height:1.8">'
        '🏗️ <a href="https://github.com/juliopessan/arch-review-assistant" '
        'style="color:#F04E37;font-weight:600">arch-review</a> · MIT<br>'
        'by <strong style="color:#2E2E2E">Orange DNA</strong>'
        '</div>',
        unsafe_allow_html=True
    )

# ── App header bar (Orange DNA orange) ───────────────────────────────────────────
st.markdown(f"""
<div class="fc-topbar">
  <div class="fc-topbar-brand">
    <span class="fc-topbar-logo">🏗️ arch-review</span>
    <span class="fc-topbar-tag">Multi-Agent AI</span>
  </div>
  <span class="fc-topbar-meta">by Orange DNA · MIT</span>
</div>
""", unsafe_allow_html=True)

# ── Hero ───────────────────────────────────────────────────────────────────────
lang_val = st.session_state.get("lang", "en")
hero_sub = (
    "7 specialized agents — Security, Reliability, Cost, Observability, "
    "Scalability, Performance, Maintainability — running in parallel, learning from every review."
    if lang_val == "en" else
    "7 agentes especializados — Segurança, Confiabilidade, Custo, Observabilidade, "
    "Escalabilidade, Performance, Manutenibilidade — rodando em paralelo, aprendendo a cada revisão."
)
st.markdown(f"""
<div class="fc-hero">
  <div class="fc-hero-title">Architecture <span>Review</span></div>
  <div class="fc-hero-sub">{hero_sub}</div>
  <div class="fc-hero-badges">
    <span class="fc-chip orange">🎯 Agent Manager</span>
    <span class="fc-chip orange">🔐 Security</span>
    <span class="fc-chip orange">🛡️ Reliability</span>
    <span class="fc-chip orange">💰 Cost</span>
    <span class="fc-chip orange">📡 Observability</span>
    <span class="fc-chip orange">📈 Scalability</span>
    <span class="fc-chip orange">⚡ Performance</span>
    <span class="fc-chip orange">🔧 Maintainability</span>
    <span class="fc-chip orange">🧠 Synthesizer</span>
    <span class="fc-chip">✦ Self-Evolving Memory</span>
    <span class="fc-chip">⚡ Parallel Execution</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_review, tab_squad, tab_findings, tab_adrs, tab_export, tab_memory = st.tabs([
    f"🔍 {t('tab.review')}",
    f"🤖 {t('tab.squad')}",
    f"📋 {t('tab.findings')}",
    f"📄 {t('tab.adrs')}",
    f"📤 {t('tab.export')}",
    f"🧠 {t('tab.memory')}",
])

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: REVIEW                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_review:
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        st.markdown(f'<div class="fc-h2">{t("review.arch.title")}</div>', unsafe_allow_html=True)
        arch_text = st.text_area("arch", height=280, label_visibility="collapsed",
            placeholder=t("review.arch.ph"),
            value=st.session_state.get("arch_prefill", ""))
        st.session_state.pop("arch_prefill", None)
        context = st.text_input(t("review.ctx"), placeholder=t("review.ctx.ph"))

    with col_r:
        st.markdown(f'<div class="fc-h2">{t("review.upload.title")}</div>', unsafe_allow_html=True)
        st.caption(f"{t('review.upload.cap')} {', '.join('.' + f for f in get_supported_formats())}")
        uploaded = st.file_uploader("Upload", type=get_supported_formats(), label_visibility="collapsed")

        if uploaded:
            with st.spinner(rand_msg(msgs["ocr"])):
                try:
                    raw_text = extract_from_bytes(uploaded.read(), uploaded.name)
                except Exception as exc:
                    st.error(f"⚠️ {exc}")
                    raw_text = None

            if raw_text:
                with st.spinner(rand_msg(msgs["structure"])):
                    structured = _structure_ocr(raw_text, selected_model)
                st.session_state["arch_prefill"] = structured
                st.success(f"{t('review.extracted')} `{uploaded.name}`")
                with st.expander(t("review.preview.struct"), expanded=True):
                    st.markdown(structured)
                with st.expander(t("review.preview.raw")):
                    st.code(raw_text, language="text")
                if st.button(t("review.use_input"), use_container_width=True, type="primary"):
                    st.rerun()

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("review.load_ex"), use_container_width=True):
                st.session_state["arch_prefill"] = EXAMPLE; st.rerun()
        with c2:
            if st.button(t("review.clear"), use_container_width=True):
                for k in ["review_result","adr_result","squad_log","arch_prefill"]:
                    st.session_state.pop(k, None)
                st.rerun()

    st.divider()
    no_key = not api_key and not any(os.environ.get(k) for k in ENV_MAP.values())
    b1, b2, b3 = st.columns([1,1,2])
    with b1:
        run_squad  = st.button(t("review.btn_squad"), type="primary",   use_container_width=True, disabled=not arch_text.strip())
    with b2:
        run_single = st.button(t("review.btn_quick"), type="secondary", use_container_width=True, disabled=not arch_text.strip())
    with b3:
        if no_key:              st.warning(t("review.no_key"))
        elif not arch_text.strip(): st.info(t("review.no_text"))

    if run_single and arch_text.strip():
        arch_inp = ArchitectureInput(description=arch_text, context=context or None,
                                      focus_areas=[FindingCategory(f) for f in focus_areas])
        with st.spinner(rand_msg(msgs["review"])):
            try:
                r = ReviewEngine(model=selected_model).review(arch_inp)
                st.session_state["review_result"] = r
                st.session_state.pop("adr_result", None)
            except Exception as exc:
                st.error(f"❌ {exc}"); st.stop()
        if gen_adrs:
            with st.spinner(rand_msg(msgs["adr"])):
                try: st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(r)
                except Exception as exc: st.warning(f"ADR: {exc}")
        st.success(t("review.done")); st.rerun()

    if run_squad and arch_text.strip():
        st.session_state.update({"squad_arch": arch_text, "squad_ctx": context,
                                   "squad_running": True, "squad_log": []})
        for k in ["review_result","adr_result"]: st.session_state.pop(k, None)
        st.rerun()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: SQUAD OFFICE                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_squad:
    import streamlit.components.v1 as components
    from squad_office import build_squad_office_html, build_agent_states, build_plan_dict

    log: list[dict] = st.session_state.get("squad_log", [])
    review_result   = st.session_state.get("review_result")
    plan_snap       = review_result.orchestration_plan if review_result else None
    plan_dict       = build_plan_dict(plan_snap)
    agent_states    = build_agent_states(log)

    # Manager state
    if plan_snap:
        agent_states["manager_agent"] = {"status": "done", "count": 0}
    elif st.session_state.get("squad_running"):
        agent_states["manager_agent"] = {"status": "running", "count": 0}

    office_html = build_squad_office_html(agent_states, lang=lang, plan=plan_dict)
    components.html(office_html, height=620, scrolling=False)

    # Result summary below canvas
    if review_result and "squad:" in review_result.model_used:
        s = review_result.summary
        st.success(f"{t('squad.complete')} **{s.total_findings} {t('squad.total_findings')}** · {s.critical_count} {t('squad.critical')} · {s.high_count} {t('squad.high')}")
        if s.top_risk:
            st.warning(f"{t('squad.top_risk')} **{esc(s.top_risk)}**")
        st.info(t("review.squad.trigger"))
    elif not st.session_state.get("squad_running"):
        st.caption(t("squad.no_result"))

    if st.session_state.get("squad_running"):
        arch_inp = ArchitectureInput(
            description=st.session_state.get("squad_arch", ""),
            context=st.session_state.get("squad_ctx") or None,
        )
        q: Queue = Queue()

        def _run(q):
            """Run ReviewSquad in a dedicated thread with its own event loop."""
            import asyncio as _aio
            # Import from the already-loaded module to guarantee same class identity
            # (prevents Pydantic "different OrchestrationPlanSnapshot" validation error)
            from arch_review.squad.squad import ReviewSquad

            class EventSquad(ReviewSquad):
                """Emits UI events per agent without changing squad logic."""
                async def _run_agent(self, agent_name, system_prompt, user_prompt):
                    q.put({"event": "start", "agent": agent_name})
                    result = await super()._run_agent(agent_name, system_prompt, user_prompt)
                    q.put({
                        "event": "done" if not result.error else "error",
                        "agent": agent_name,
                        "count": len(result.findings),
                        "error": result.error or "",
                    })
                    return result

            # Create fresh event loop for this thread (avoids asyncio conflicts)
            loop = _aio.new_event_loop()
            _aio.set_event_loop(loop)
            try:
                sq = EventSquad(model=selected_model)
                q.put({"event": "start", "agent": "manager_agent"})
                review = loop.run_until_complete(sq._review_async(arch_inp))
                q.put({"event": "done", "agent": "manager_agent", "count": 0})
                q.put({"event": "result", "result": review})
            except Exception as exc:
                import traceback
                q.put({"event": "error", "agent": "squad", "error": str(exc)})
                q.put({"event": "error_detail", "traceback": traceback.format_exc()})
            finally:
                loop.close()
                q.put({"event": "finished"})

        t_thread = threading.Thread(target=_run, args=(q,), daemon=True)
        t_thread.start()
        error_detail = None
        with st.spinner(rand_msg(msgs["squad"])):
            while True:
                try:
                    ev = q.get(timeout=180)
                except Empty:
                    st.error("Squad timed out after 3 minutes."); break

                if ev["event"] in ("start", "done", "error"):
                    log.append(ev)
                    st.session_state["squad_log"] = log
                elif ev["event"] == "error_detail":
                    error_detail = ev.get("traceback", "")
                elif ev["event"] == "result":
                    st.session_state["review_result"] = ev["result"]
                elif ev["event"] == "finished":
                    break

        st.session_state["squad_running"] = False

        # Show error if squad failed
        if not st.session_state.get("review_result") and any(
            e.get("event") == "error" for e in log
        ):
            err_msg = next(
                (e.get("error", "") for e in log if e.get("event") == "error"), ""
            )
            st.error(f"❌ Squad failed: {err_msg}")
            if error_detail:
                with st.expander("🔍 Error details"):
                    st.code(error_detail, language="text")
            st.stop()

        if gen_adrs and "review_result" in st.session_state:
            with st.spinner(rand_msg(msgs["adr"])):
                try:
                    st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(
                        st.session_state["review_result"]
                    )
                except Exception:
                    pass
        st.rerun()

    if "review_result" in st.session_state:
        r = st.session_state["review_result"]
        if "squad:" in r.model_used:
            s = r.summary
            st.success(f"{t('squad.complete')} **{s.total_findings} {t('squad.total_findings')}** · {s.critical_count} {t('squad.critical')} · {s.high_count} {t('squad.high')}")
            if s.top_risk: st.warning(f"{t('squad.top_risk')} **{esc(s.top_risk)}**")
            st.info(t("review.squad.trigger"))
    else:
        st.info(t("squad.no_result"))


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: FINDINGS                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_findings:
    if "review_result" not in st.session_state:
        st.info(t("findings.no_result"))
    else:
        r: ReviewResult = st.session_state["review_result"]
        s = r.summary
        st.markdown(f"""
        <div class="statrow">
          <div class="stat stat-c"><div class="n">{s.critical_count}</div><div class="l">{t('findings.stat.critical')}</div></div>
          <div class="stat stat-h"><div class="n">{s.high_count}</div><div class="l">{t('findings.stat.high')}</div></div>
          <div class="stat stat-m"><div class="n">{s.medium_count}</div><div class="l">{t('findings.stat.medium')}</div></div>
          <div class="stat stat-l"><div class="n">{s.low_count}</div><div class="l">{t('findings.stat.low')}</div></div>
          <div class="stat stat-i"><div class="n">{s.info_count}</div><div class="l">{t('findings.stat.info')}</div></div>
          <div class="stat stat-t"><div class="n">{s.total_findings}</div><div class="l">{t('findings.stat.total')}</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"{t('findings.model')} `{r.model_used}`")

        # ── Agent Manager Plan (shown only for squad reviews) ──────────────────
        if r.orchestration_plan and "squad:" in r.model_used:
            plan = r.orchestration_plan
            with st.expander("🎯 Agent Manager Plan", expanded=False):
                pc1, pc2, pc3 = st.columns(3)
                pc1.metric("Architecture", plan.architecture_type)
                pc2.metric("Complexity", plan.complexity.upper())
                pc3.metric("Agents Active", f"{len(plan.active_agents)}/7")

                if plan.top_risks:
                    st.markdown("**Top risks detected before agents ran:**")
                    for i, risk in enumerate(plan.top_risks, 1):
                        st.markdown(f"**{i}.** {risk}")

                if plan.compliance_flags or plan.cloud_providers:
                    fc1, fc2 = st.columns(2)
                    if plan.compliance_flags:
                        fc1.markdown(f"**Compliance:** {', '.join(plan.compliance_flags)}")
                    if plan.cloud_providers:
                        fc2.markdown(f"**Cloud:** {', '.join(plan.cloud_providers)}")

                if plan.agent_focus_notes:
                    st.markdown("**Agent focus directives:**")
                    focus_map = {"security_agent":"🔐","reliability_agent":"🛡️","cost_agent":"💰","observability_agent":"📡"}
                    for agent, note in plan.agent_focus_notes.items():
                        ic = focus_map.get(agent, "🤖")
                        prio = plan.agent_priorities.get(agent, "normal").upper()
                        prio_colors = {"CRITICAL":"#dc2626","HIGH":"#ea580c","NORMAL":"#6b7280","LOW":"#9ca3af"}
                        color = prio_colors.get(prio, "#6b7280")
                        st.markdown(f'{ic} **{agent.replace("_"," ").title()}** <span style="color:{color};font-size:.75rem;font-weight:700">[{prio}]</span> — {note}', unsafe_allow_html=True)

                if plan.skipped_agents:
                    st.caption(f"⏭ Skipped (irrelevant): {', '.join(plan.skipped_agents)}")

        if s.overall_assessment:
            with st.expander(t("findings.assessment"), expanded=True):
                st.write(s.overall_assessment)
        if r.senior_architect_questions:
            with st.expander(t("findings.questions")):
                for i, q in enumerate(r.senior_architect_questions, 1):
                    st.markdown(f"**{i}.** {q}")

        st.markdown(t("findings.title"))
        sev_filter = st.multiselect(t("findings.filter"), [sv.value for sv in Severity],
            default=[sv.value for sv in Severity], label_visibility="collapsed")
        filtered = [f for f in r.findings if f.severity.value in sev_filter]

        for f in filtered:
            css = SEV_CSS[f.severity]; pill = SEV_PILL[f.severity]
            cat = f.category.value.upper().replace("_", " ")
            comps = f'<div class="scard-affects">{t("findings.affects")} {esc(", ".join(f.affected_components))}</div>' if f.affected_components else ""
            qs_html = "".join(f'&ldquo;{esc(q)}&rdquo; &nbsp;' for q in f.questions_to_ask)
            refs = f'<div class="scard-q">📚 {esc(" · ".join(f.references))}</div>' if f.references else ""
            st.markdown(f"""<div class="scard {css}">
              <div class="scard-meta"><span class="pill {pill}">{f.severity.value}</span> &nbsp; {esc(cat)}</div>
              <div class="scard-title">{esc(f.title)}</div>
              <div class="scard-desc">{esc(f.description)}</div>
              {comps}<div class="scard-rec">{t('findings.rec_prefix')} {esc(f.recommendation)}</div>
              {f'<div class="scard-q">💬 {qs_html}</div>' if qs_html else ""}{refs}
            </div>""", unsafe_allow_html=True)

        if r.recommended_adrs:
            st.markdown(t("findings.adrs_title"))
            for i, a in enumerate(r.recommended_adrs, 1):
                st.markdown(f"**{i}.** {a}")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: ADRs                                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_adrs:
    if "review_result" not in st.session_state:
        st.info(t("adrs.no_result"))
    elif "adr_result" not in st.session_state:
        c1, c2 = st.columns([1,3])
        with c1:
            if st.button(t("adrs.generate"), type="primary", use_container_width=True):
                with st.spinner(rand_msg(msgs["adr"])):
                    try:
                        st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(st.session_state["review_result"])
                        st.rerun()
                    except Exception as exc: st.error(str(exc))
        with c2: st.info(t("adrs.not_yet"))
    else:
        ar: ADRGenerationResult = st.session_state["adr_result"]
        st.success(f"✅ {ar.total_generated} {t('adrs.generated')} `{ar.model_used}`")
        for adr in ar.adrs:
            num = str(adr.number).zfill(4)
            with st.expander(f"ADR-{num} — {adr.title}"):
                st.markdown(f'<div class="adrcard"><div class="adrnum">ADR-{num}</div><div class="adrtitle">{esc(adr.title)}</div><span class="adrstatus">{adr.status.value}</span></div>', unsafe_allow_html=True)
                if adr.context:
                    st.markdown(t("adrs.context")); st.write(adr.context)
                if adr.decision_drivers:
                    st.markdown(t("adrs.drivers"))
                    for d in adr.decision_drivers: st.markdown(f"- {d}")
                if adr.considered_options:
                    st.markdown(t("adrs.options"))
                    for opt in adr.considered_options:
                        o1, o2 = st.columns(2)
                        o1.markdown(f"**{opt.title}**"); o1.write(opt.description)
                        if opt.pros:
                            for p in opt.pros: o1.markdown(f"✅ {p}")
                        if opt.cons:
                            for c in opt.cons: o2.markdown(f"⚠️ {c}")
                if adr.decision:
                    st.markdown(t("adrs.decision")); st.success(adr.decision)
                pc, nc = st.columns(2)
                for c in adr.consequences_positive: pc.markdown(f"✅ {c}")
                for c in adr.consequences_negative: nc.markdown(f"⚠️ {c}")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: EXPORT                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_export:
    if "review_result" not in st.session_state:
        st.info(t("export.no_result"))
    else:
        r: ReviewResult = st.session_state["review_result"]
        st.markdown(t("export.title"))
        e1, e2 = st.columns(2)
        with e1:
            st.markdown(t("export.json_desc"))
            st.download_button("⬇️ review.json", r.model_dump_json(indent=2), "arch-review.json","application/json", use_container_width=True)
        with e2:
            st.markdown(t("export.md_desc"))
            st.download_button("⬇️ review.md", _build_md(r), "arch-review.md","text/markdown", use_container_width=True)
        if "adr_result" in st.session_state:
            st.divider()
            st.markdown(t("export.adr_title"))
            a = st.session_state["adr_result"]
            st.download_button(f"⬇️ {a.total_generated} {t('export.adr_zip')}", _build_zip(a), "adrs.zip","application/zip", use_container_width=True)
            st.caption(t("export.adr_hint"))
        st.divider()
        st.markdown(t("export.preview"))
        st.code(_build_md(r), language="markdown")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: MEMORY + EVOLUTION DASHBOARD                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_memory:
    from arch_review.squad.memory import DEFAULT_MEMORY_DIR, AgentMemory, SquadMemory
    mem   = DEFAULT_MEMORY_DIR
    alist = [
        "security_agent", "reliability_agent", "cost_agent", "observability_agent",
        "scalability_agent", "performance_agent", "maintainability_agent", "synthesizer_agent",
    ]
    alist_full = alist + ["manager_agent"]
    AGENT_META_MEM = {
        "security_agent":        {"ic": "🔐", "nm": t("agent.security.nm")},
        "reliability_agent":     {"ic": "🛡️", "nm": t("agent.reliability.nm")},
        "cost_agent":            {"ic": "💰", "nm": t("agent.cost.nm")},
        "observability_agent":   {"ic": "📡", "nm": t("agent.observability.nm")},
        "scalability_agent":     {"ic": "📈", "nm": "Scalability" if lang == "en" else "Escalabilidade"},
        "performance_agent":     {"ic": "⚡", "nm": "Performance"},
        "maintainability_agent": {"ic": "🔧", "nm": "Maintainability" if lang == "en" else "Manutenibilidade"},
        "synthesizer_agent":     {"ic": "🧠", "nm": t("agent.synthesizer.nm")},
        "manager_agent":         {"ic": "🎯", "nm": "Agent Manager"},
    }

    st.markdown(t("memory.title"))
    st.caption(t("memory.caption"))

    # ── Agent status cards (9 agents: 3 rows of 3) ───────────────────────────
    for row_agents in [alist_full[:3], alist_full[3:6], alist_full[6:]]:
        mcols = st.columns(len(row_agents))
        for i, nm in enumerate(row_agents):
            a = AGENT_META_MEM[nm]; f = mem / f"{nm}.md"
            exists = f.exists()
            sz = f"{f.stat().st_size:,}b" if exists else "—"
            ls = f.read_text().count("## Lesson") if exists else 0
            with mcols[i]:
                css = "live" if exists else ""
                st.markdown(f'<div class="memcard {css}"><div class="ic">{a["ic"]}</div><div class="nm">{a["nm"]}</div><div class="sz">{sz}</div><div class="ls">{ls} {t("memory.lessons")}</div></div>', unsafe_allow_html=True)

    sqf = mem / "SQUAD_MEMORY.md"
    if sqf.exists():
        rv = sqf.read_text().count("## Review [")
        pt = sqf.read_text().count("## Cross-Agent Pattern")
        st.info(f"📊 **SQUAD_MEMORY.md** — {rv} {t('memory.reviews')} · {pt} {t('memory.patterns')}")

    st.divider()

    # ── Evolution Dashboard ────────────────────────────────────────────────────
    st.markdown(t("memory.evo.title"))
    st.caption(t("memory.evo.caption"))

    sq_mem   = SquadMemory(mem)
    sq_stats = sq_mem.get_stats()

    if sq_stats["reviews"] == 0:
        st.markdown(f"""
        <div style="background:#f5f3ff;border:1.5px dashed #c7d2fe;border-radius:14px;
        padding:32px;text-align:center">
          <div style="font-size:2.5rem;margin-bottom:12px">🌱</div>
          <div style="font-weight:700;font-size:1rem;color:#4338ca;margin-bottom:6px">
            {t("memory.evo.no_reviews")}
          </div>
          <div style="font-size:.83rem;color:#6b7280;margin-top:8px">
            <code>arch-review squad review -i architecture.md</code>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Squad-level stat row
        s1,s2,s3,s4,s5,s6 = st.columns(6)
        def _sc(col, number, label, color="#4f46e5"):
            col.markdown(f'<div class="stat"><div class="n" style="color:{color}">{number}</div><div class="l">{label}</div></div>', unsafe_allow_html=True)

        total_lessons = sum(AgentMemory(n, mem).get_stats()["lessons"] for n in alist)
        _sc(s1, sq_stats["reviews"],        t("memory.evo.reviews"),  "#4f46e5")
        _sc(s2, total_lessons,              t("memory.evo.lessons"),  "#16a34a")
        _sc(s3, sq_stats["cross_patterns"], t("memory.evo.patterns"), "#0891b2")
        _sc(s4, sq_stats["total_findings"], t("memory.evo.findings"), "#ea580c")
        _sc(s5, sq_stats["total_criticals"],t("memory.evo.criticals"),"#dc2626")
        _sc(s6, sq_stats["avg_findings"],   t("memory.evo.avg"),      "#6b7280")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(t("memory.evo.agent_title"))

        def _agent_evo_card(nm):
            a     = AGENT_META_MEM[nm]
            stats = AgentMemory(nm, mem).get_stats()
            ls    = stats["lessons"]
            pt    = stats["patterns"]
            last  = stats["last_updated"] or t("memory.evo.never")
            if ls == 0:   level, color = t("memory.evo.fresh"),       "#9ca3af"
            elif ls < 3:  level, color = t("memory.evo.growing"),     "#16a34a"
            elif ls < 8:  level, color = t("memory.evo.experienced"), "#0891b2"
            else:         level, color = t("memory.evo.expert"),      "#7c3aed"
            bar_w = min(int(ls / 10 * 100), 100)
            st.markdown(f"""
            <div style="background:#fff;border:1.5px solid #E0E0E0;border-radius:10px;
            padding:14px 10px;text-align:center">
              <div style="font-size:1.4rem;margin-bottom:4px">{a["ic"]}</div>
              <div style="font-weight:700;font-size:.8rem;color:#2E2E2E">{a["nm"]}</div>
              <div style="font-size:.7rem;font-weight:700;color:{color};margin:5px 0 3px">{level}</div>
              <div style="background:#F5F5F5;border-radius:999px;height:4px;margin:5px 0">
                <div style="background:{color};height:4px;border-radius:999px;width:{bar_w}%"></div>
              </div>
              <div style="font-size:.67rem;color:#666;margin-top:4px">
                {ls} {t("memory.evo.lessons_lbl")} · {pt} {t("memory.evo.patterns_lbl")}
              </div>
              <div style="font-size:.64rem;color:#9ca3af;margin-top:2px">
                {t("memory.evo.last")} {last}
              </div>
            </div>
            """, unsafe_allow_html=True)

        for row_nms in [alist_full[:3], alist_full[3:6], alist_full[6:]]:
            acols = st.columns(len(row_nms))
            for i, nm in enumerate(row_nms):
                with acols[i]:
                    _agent_evo_card(nm)

        st.divider()
        st.markdown(t("memory.evo.how_title"))
        st.markdown(f'<div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:12px;padding:20px 24px;font-size:.87rem;color:#374151;line-height:1.7">{t("memory.evo.how_body")}</div>', unsafe_allow_html=True)

    st.divider()

    # ── Run Time section ───────────────────────────────────────────────────────
    rt_title = "#### ⏱️ Run Time" if lang == "en" else "#### ⏱️ Tempo de Execução"
    st.markdown(rt_title)
    rt_caption = "Performance metrics for the last squad review — duration, tokens, cost, and ROI." \
        if lang == "en" else \
        "Métricas de performance da última revisão — duração, tokens, custo e ROI."
    st.caption(rt_caption)

    rm = st.session_state.get("review_result") and st.session_state["review_result"].run_metrics

    if not rm:
        no_run_label = "No squad review yet. Run a Squad Review from the Review tab." \
            if lang == "en" else \
            "Nenhuma revisão de squad ainda. Execute uma Revisão com Squad na aba Revisão."
        st.markdown(f"""
        <div style="background:#f9fafb;border:1.5px dashed #e5e7eb;border-radius:14px;
        padding:28px;text-align:center">
          <div style="font-size:2rem;margin-bottom:10px">⏱️</div>
          <div style="font-size:.9rem;color:#6b7280">{no_run_label}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # ── Top metric row ─────────────────────────────────────────────────────
        def fmt_s(s: float) -> str:
            if s < 60: return f"{s:.1f}s"
            return f"{int(s//60)}m {int(s%60)}s"

        lbl_total  = "Total Time"         if lang=="en" else "Tempo Total"
        lbl_mgr    = "Manager"            if lang=="en" else "Gerente"
        lbl_squad  = "Squad (parallel)"   if lang=="en" else "Squad (paralelo)"
        lbl_synth  = "Synthesizer"        if lang=="en" else "Sintetizador"
        lbl_tokens = "Tokens Used"        if lang=="en" else "Tokens Usados"
        lbl_cost   = "Est. Cost"          if lang=="en" else "Custo Est."
        lbl_roi    = "vs Manual Review"   if lang=="en" else "vs Revisão Manual"

        r1, r2, r3, r4, r5, r6, r7 = st.columns(7)
        def _rt_card(col, number, label, color="#4f46e5", sub=""):
            sub_html = f'<div style="font-size:.65rem;color:#9ca3af;margin-top:1px">{sub}</div>' if sub else ""
            col.markdown(
                f'<div class="stat"><div class="n" style="color:{color};font-size:1.4rem">{number}</div>'
                f'<div class="l">{label}</div>{sub_html}</div>',
                unsafe_allow_html=True
            )

        _rt_card(r1, fmt_s(rm.total_duration_s),  lbl_total,  "#4f46e5")
        _rt_card(r2, fmt_s(rm.phase_manager_s),   lbl_mgr,    "#6366f1",
                 "Phase 0" if lang=="en" else "Fase 0")
        _rt_card(r3, fmt_s(rm.phase_parallel_s),  lbl_squad,  "#0891b2",
                 "wall-clock" if lang=="en" else "relógio de parede")
        _rt_card(r4, fmt_s(rm.phase_synth_s),     lbl_synth,  "#7c3aed")
        _rt_card(r5, f"{rm.tokens_total:,}",       lbl_tokens, "#ea580c",
                 f"↑{rm.tokens_in_total:,} ↓{rm.tokens_out_total:,}")
        _rt_card(r6, f"${rm.cost_usd:.4f}",        lbl_cost,   "#16a34a")

        # ROI card
        saved = max(0.0, 600.0 - rm.cost_usd)
        ratio = int(saved / max(rm.cost_usd, 0.001))
        roi_val = f"{ratio}x" if ratio < 9999 else "∞"
        r7.markdown(
            f'<div class="stat"><div class="n" style="color:#16a34a;font-size:1.4rem">{roi_val}</div>'
            f'<div class="l">{lbl_roi}</div>'
            f'<div style="font-size:.65rem;color:#9ca3af;margin-top:1px">${saved:,.0f} {"saved" if lang=="en" else "economizados"}</div></div>',
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Per-agent timeline bars ────────────────────────────────────────────
        agent_title = "**Agent Timeline**" if lang=="en" else "**Timeline dos Agentes**"
        st.markdown(agent_title)

        AGENT_ICONS = {
            "manager_agent": "🎯", "security_agent": "🔐",
            "reliability_agent": "🛡️", "cost_agent": "💰",
            "observability_agent": "📡", "synthesizer_agent": "🧠",
            "scalability_agent": "📈", "performance_agent": "⚡",
            "maintainability_agent": "🔧",
        }
        AGENT_LABELS = {
            "en": {"manager_agent":"Manager","security_agent":"Security",
                   "reliability_agent":"Reliability","cost_agent":"Cost",
                   "observability_agent":"Observability","synthesizer_agent":"Synthesizer",
                   "scalability_agent":"Scalability","performance_agent":"Performance",
                   "maintainability_agent":"Maintainability"},
            "pt": {"manager_agent":"Gerente","security_agent":"Segurança",
                   "reliability_agent":"Confiabilidade","cost_agent":"Custo",
                   "observability_agent":"Observabilidade","synthesizer_agent":"Sintetizador",
                   "scalability_agent":"Escalabilidade","performance_agent":"Performance",
                   "maintainability_agent":"Manutenibilidade"},
        }
        PHASE_COLORS = {"manager":"#6366f1","parallel":"#0891b2","synthesizer":"#7c3aed"}

        max_dur = max((a.duration_s for a in rm.agents), default=1.0)

        for agent in rm.agents:
            ic   = AGENT_ICONS.get(agent.agent_name, "🤖")
            nm   = AGENT_LABELS[lang].get(agent.agent_name, agent.agent_name)
            bar  = min(int(agent.duration_s / max(max_dur, 0.01) * 100), 100)
            col  = PHASE_COLORS.get(agent.phase, "#6b7280")
            toks = f"{agent.tokens_in:,} in · {agent.tokens_out:,} out · ${agent.cost_usd:.4f}" \
                   if agent.tokens_total > 0 else \
                   ("no token data" if lang=="en" else "sem dados de token")
            err_html = f'<span style="color:#dc2626;font-size:.7rem">⚠️ {esc(agent.error[:60])}</span>' \
                       if agent.error else ""
            findings_html = f'<span style="color:{col};font-weight:700">{agent.findings_count} {"findings" if lang=="en" else "achados"}</span>' \
                            if agent.findings_count else ""

            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
              <div style="width:24px;text-align:center;font-size:1rem;flex-shrink:0">{ic}</div>
              <div style="width:110px;flex-shrink:0">
                <div style="font-weight:600;font-size:.82rem;color:#111">{nm}</div>
                <div style="font-size:.68rem;color:#9ca3af">{fmt_s(agent.duration_s)}</div>
              </div>
              <div style="flex:1;min-width:0">
                <div style="background:#f3f4f6;border-radius:999px;height:8px;overflow:hidden">
                  <div style="background:{col};height:8px;border-radius:999px;width:{bar}%;
                  transition:width .5s ease"></div>
                </div>
                <div style="font-size:.68rem;color:#6b7280;margin-top:3px">{toks} {findings_html} {err_html}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Pricing footnote ───────────────────────────────────────────────────
        note_en = "Cost estimated using Claude Sonnet 4 pricing: $3/M input tokens · $15/M output tokens. " \
                  "Manual review baseline: senior architect at $150/h × 4h = $600."
        note_pt = "Custo estimado com preços do Claude Sonnet 4: $3/M tokens de entrada · $15/M de saída. " \
                  "Baseline de revisão manual: arquiteto sênior a $150/h × 4h = $600."
        st.caption(f"ℹ️ {note_en if lang=='en' else note_pt}")

        # ── Model & started at ─────────────────────────────────────────────────
        started_label = "Started at" if lang=="en" else "Iniciado em"
        model_label   = "Model"      if lang=="en" else "Modelo"
        st.caption(f"{started_label}: `{rm.started_at[:19].replace('T',' ')} UTC` · {model_label}: `{rm.model_used}`")

    st.divider()

    # ── File viewer ────────────────────────────────────────────────────────────
    sel = st.selectbox(t("memory.view"), alist_full, format_func=lambda n: f"{AGENT_META_MEM[n]['ic']} {AGENT_META_MEM[n]['nm']}")
    mf  = mem / f"{sel}.md"
    if mf.exists():
        t1, t2 = st.tabs([t("memory.full"), t("memory.lessons_only")])
        with t1: st.code(mf.read_text(), language="markdown")
        with t2:
            txt = mf.read_text()
            sec = txt.split("---", 1)[1].strip() if "---" in txt else f"({t('memory.no_yet')})"
            st.code(sec, language="markdown")
    else:
        st.info(t("memory.no_yet"))

    st.markdown(t("memory.squad_mem"))
    if sqf.exists(): st.code(sqf.read_text(), language="markdown")
    else:            st.info(t("memory.no_squad"))

    st.divider()
    if st.button(t("memory.reset_btn"), type="secondary"):
        if st.session_state.get("_reset_ok"):
            for nm in alist:
                f = mem / f"{nm}.md"
                if f.exists(): f.unlink()
                AgentMemory(nm, mem)
            if sqf.exists(): sqf.unlink()
            SquadMemory(mem)
            st.session_state.pop("_reset_ok", None)
            st.success(t("memory.reset_ok")); st.rerun()
        else:
            st.session_state["_reset_ok"] = True
            st.warning(t("memory.reset_confirm"))
