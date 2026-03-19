"""Architecture Review Assistant — Streamlit Web UI v3 with i18n."""

from __future__ import annotations

import html, io, os, re, sys, threading, zipfile, random
from pathlib import Path
from queue import Empty, Queue

import streamlit as st

st.set_page_config(
    page_title="arch-review",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from arch_review.adr_generator import ADRGenerator
from arch_review.engine import SUPPORTED_MODELS, ReviewEngine
from arch_review.models import ArchitectureInput, FindingCategory, ReviewResult, Severity
from arch_review.models_adr import ADRGenerationResult
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

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif !important; }
.main .block-container { max-width: 1100px !important; padding: 2rem 2rem 4rem !important; }
#MainMenu, footer { display: none !important; }
h1 { font-size: 2.2rem !important; font-weight: 700 !important; letter-spacing: -.03em !important; margin-bottom: .25rem !important; }
h2 { font-size: 1.3rem !important; font-weight: 600 !important; margin: 1.5rem 0 .75rem !important; }
.badge { display: inline-flex; align-items: center; gap: 6px; background: #f0f0ff; border: 1px solid #c7d2fe; color: #4338ca; border-radius: 999px; padding: 4px 14px; font-size: .75rem; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; margin-bottom: 1rem; }
.scard { border-radius: 12px; padding: 16px 20px; margin-bottom: 14px; border: 1px solid #e5e7eb; background: #fff; }
.scard.critical { border-left: 4px solid #dc2626; background: #fff7f7; }
.scard.high     { border-left: 4px solid #ea580c; background: #fff8f5; }
.scard.medium   { border-left: 4px solid #ca8a04; background: #fffdf0; }
.scard.low      { border-left: 4px solid #2563eb; background: #f5f8ff; }
.scard.info     { border-left: 4px solid #6b7280; background: #f9fafb; }
.scard-title  { font-weight: 700; font-size: .97rem; color: #111; margin-bottom: 4px; }
.scard-meta   { font-size: .72rem; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: #9ca3af; margin-bottom: 10px; }
.scard-desc   { font-size: .87rem; color: #374151; line-height: 1.6; margin-bottom: 10px; }
.scard-rec    { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 9px 13px; font-size: .84rem; color: #166534; margin-bottom: 6px; }
.scard-affects{ font-size: .78rem; color: #4f46e5; margin-bottom: 6px; }
.scard-q      { font-size: .78rem; color: #6b7280; font-style: italic; margin-top: 6px; }
.pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: .7rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.pill-critical { background: #fee2e2; color: #b91c1c; }
.pill-high     { background: #ffedd5; color: #c2410c; }
.pill-medium   { background: #fef9c3; color: #a16207; }
.pill-low      { background: #dbeafe; color: #1d4ed8; }
.pill-info     { background: #f3f4f6; color: #6b7280; }
.statrow { display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }
.stat { flex: 1; min-width: 80px; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.stat .n { font-size: 1.9rem; font-weight: 800; line-height: 1; }
.stat .l { font-size: .7rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: #9ca3af; margin-top: 3px; }
.stat-c .n{color:#dc2626} .stat-h .n{color:#ea580c} .stat-m .n{color:#ca8a04} .stat-l .n{color:#2563eb} .stat-i .n{color:#9ca3af} .stat-t .n{color:#4f46e5}
.agentcard { flex: 1; background: #fff; border: 1.5px solid #e5e7eb; border-radius: 14px; padding: 16px 12px; text-align: center; transition: all .25s ease; }
.agentcard.idle    { opacity: .45; }
.agentcard.running { border-color: #6366f1; background: #f5f3ff; box-shadow: 0 0 0 3px rgba(99,102,241,.1); }
.agentcard.done    { border-color: #16a34a; background: #f0fdf4; }
.agentcard.error   { border-color: #dc2626; background: #fef2f2; }
.agentcard .ic { font-size: 1.6rem; margin-bottom: 6px; }
.agentcard .nm { font-size: .82rem; font-weight: 700; color: #111; }
.agentcard .ds { font-size: .68rem; color: #9ca3af; margin-top: 2px; line-height: 1.4; }
.agentcard .st { font-size: .72rem; color: #6b7280; margin-top: 5px; }
.agentcard .ct { font-size: .75rem; font-weight: 700; color: #4f46e5; margin-top: 3px; }
.arrow { font-size: 1.1rem; color: #d1d5db; padding-top: 22px; }
.memcard { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px 10px; text-align: center; }
.memcard.live { border-color: #16a34a; background: #f0fdf4; }
.memcard .ic { font-size: 1.3rem; }
.memcard .nm { font-size: .78rem; font-weight: 700; color: #111; margin-top: 4px; }
.memcard .sz { font-size: .68rem; color: #9ca3af; }
.memcard .ls { font-size: .72rem; font-weight: 700; color: #4f46e5; margin-top: 2px; }
.adrcard { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px 20px; margin-bottom: 10px; }
.adrnum   { font-size: .72rem; font-weight: 700; color: #4f46e5; letter-spacing: .07em; text-transform: uppercase; }
.adrtitle { font-size: 1rem; font-weight: 700; color: #111; margin: 4px 0; }
.adrstatus{ display: inline-block; background: #eff6ff; color: #1d4ed8; border-radius: 999px; padding: 2px 10px; font-size: .7rem; font-weight: 700; }
[data-testid="stFileUploaderDropzone"] { border-radius: 12px !important; border: 1.5px dashed #c7d2fe !important; background: #fafbff !important; }
.stTextArea textarea { font-family: 'JetBrains Mono','Fira Code',monospace !important; font-size: .82rem !important; border-radius: 10px !important; border: 1.5px solid #e5e7eb !important; }
.stTextArea textarea:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,.1) !important; }
.stButton > button { border-radius: 10px !important; font-weight: 600 !important; font-size: .88rem !important; transition: all .15s !important; }
.stTabs [data-baseweb="tab-list"] { gap: 4px !important; border-bottom: 2px solid #f3f4f6 !important; }
.stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0 !important; font-size: .85rem !important; font-weight: 500 !important; padding: 8px 16px !important; color: #6b7280 !important; }
.stTabs [aria-selected="true"] { color: #4f46e5 !important; background: #f5f3ff !important; border-bottom: 2px solid #4f46e5 !important; }
hr { border: none !important; border-top: 1px solid #f3f4f6 !important; margin: 1.5rem 0 !important; }
code { background: #f5f3ff !important; color: #4338ca !important; border-radius: 4px !important; padding: 1px 5px !important; }
[data-testid="stExpander"] { border: 1px solid #e5e7eb !important; border-radius: 12px !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
SEV_CSS  = {Severity.CRITICAL:"critical",Severity.HIGH:"high",Severity.MEDIUM:"medium",Severity.LOW:"low",Severity.INFO:"info"}
SEV_PILL = {Severity.CRITICAL:"pill-critical",Severity.HIGH:"pill-high",Severity.MEDIUM:"pill-medium",Severity.LOW:"pill-low",Severity.INFO:"pill-info"}
ENV_MAP  = {"anthropic":"ANTHROPIC_API_KEY","openai":"OPENAI_API_KEY","google":"GEMINI_API_KEY","mistral":"MISTRAL_API_KEY"}
PRIORITY_PILL = {"critical":"pill-critical","high":"pill-high","medium":"pill-medium","low":"pill-low"}

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

def priority_badge(priority: str) -> str:
    css = PRIORITY_PILL.get(priority.lower(), "pill-info")
    return f'<span class="pill {css}">{esc(priority)}</span>'

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
    # Language toggle — first thing in sidebar
    lang_choice = st.radio("🌐", ["🇺🇸 English", "🇧🇷 Português"], horizontal=True, label_visibility="collapsed")
    lang = "pt" if "Português" in lang_choice else "en"
    st.session_state["lang"] = lang
    t = get_t(lang)
    msgs = rand_msgs(lang)

    st.markdown(f"## {t('sidebar.settings')}")
    selected_model = st.selectbox(t("sidebar.model"), list(SUPPORTED_MODELS.keys()), index=0, label_visibility="collapsed")
    provider = SUPPORTED_MODELS.get(selected_model, "")
    st.caption(f"{t('sidebar.provider')} `{provider}`")

    api_key = st.text_input(t("sidebar.apikey"), type="password",
        placeholder=t("sidebar.apikey.ph"), label_visibility="collapsed")
    if api_key:
        os.environ[ENV_MAP.get(provider, "OPENAI_API_KEY")] = api_key
        st.success(t("sidebar.apikey.ok"))

    st.divider()
    focus_areas = st.multiselect(t("sidebar.focus"), [c.value for c in FindingCategory],
        default=[], help=t("sidebar.focus.help"))
    gen_adrs = st.toggle(t("sidebar.adrs"), value=True)
    st.divider()
    st.caption("🏗️ [arch-review](https://github.com/juliopessan/arch-review-assistant) · MIT")

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown(f'<div class="badge">{t("app.badge")}</div>', unsafe_allow_html=True)
st.title(t("app.title"))
st.markdown(t("app.subtitle"))
st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_review, tab_squad, tab_findings, tab_adrs, tab_export, tab_memory = st.tabs([
    t("tab.review"), t("tab.squad"), t("tab.findings"),
    t("tab.adrs"),   t("tab.export"), t("tab.memory"),
])

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: REVIEW                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_review:
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        st.markdown(t("review.arch.title"))
        arch_text = st.text_area("arch", height=280, label_visibility="collapsed",
            placeholder=t("review.arch.ph"),
            value=st.session_state.get("arch_prefill", ""))
        st.session_state.pop("arch_prefill", None)
        context = st.text_input(t("review.ctx"), placeholder=t("review.ctx.ph"))

    with col_r:
        st.markdown(t("review.upload.title"))
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
    st.markdown(t("squad.title"))
    st.caption(t("squad.caption"))

    AGENTS = {
        "manager_agent":       {"ic":"🎯","nm":"Agent Manager",              "ds":"Classify context, prioritize agents, inject focus"},
        "security_agent":      {"ic":"🔐","nm":t("agent.security.nm"),     "ds":t("agent.security.ds")},
        "reliability_agent":   {"ic":"🛡️","nm":t("agent.reliability.nm"),   "ds":t("agent.reliability.ds")},
        "cost_agent":          {"ic":"💰","nm":t("agent.cost.nm"),           "ds":t("agent.cost.ds")},
        "observability_agent": {"ic":"📡","nm":t("agent.observability.nm"),  "ds":t("agent.observability.ds")},
        "synthesizer_agent":   {"ic":"🧠","nm":t("agent.synthesizer.nm"),    "ds":t("agent.synthesizer.ds")},
    }

    log: list[dict] = st.session_state.get("squad_log", [])

    def _state(name: str):
        evts = [v for v in log if v.get("agent") == name]
        if any(v["event"]=="error" for v in evts): return "error", t("squad.error"), 0
        if any(v["event"]=="done"  for v in evts):
            c = next((v.get("count",0) for v in evts if v["event"]=="done"), 0)
            return "done", t("squad.done"), c
        if any(v["event"]=="start" for v in evts): return "running", t("squad.running"), 0
        return "idle", t("squad.idle"), 0

    spec = ["security_agent", "reliability_agent", "cost_agent", "observability_agent"]
    synth = "synthesizer_agent"
    manager = "manager_agent"
    cols11 = st.columns(11)
    ac = [cols11[2], cols11[4], cols11[6], cols11[8]]

    with cols11[0]:
        a = AGENTS[manager]; css, st_, cnt = _state(manager)
        st.markdown(f'<div class="agentcard {css}"><div class="ic">{a["ic"]}</div><div class="nm">{a["nm"]}</div><div class="ds">{a["ds"]}</div><div class="st">{st_}</div></div>', unsafe_allow_html=True)
    with cols11[1]:
        st.markdown('<div class="arrow" style="padding-top:22px">→</div>', unsafe_allow_html=True)

    for i, name in enumerate(spec):
        a = AGENTS[name]; css, st_, cnt = _state(name)
        cnt_html = f'<div class="ct">{cnt} {t("squad.findings")}</div>' if cnt else ""
        with ac[i]:
            st.markdown(f'<div class="agentcard {css}"><div class="ic">{a["ic"]}</div><div class="nm">{a["nm"]}</div><div class="ds">{a["ds"]}</div><div class="st">{st_}</div>{cnt_html}</div>', unsafe_allow_html=True)
        if i < 3:
            with cols11[(i+1)*2+1]:
                st.markdown('<div class="arrow" style="padding-top:22px">→</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    _, sc, _ = st.columns([2,1,2])
    with sc:
        a = AGENTS[synth]; css, st_, cnt = _state(synth)
        cnt_html = f'<div class="ct">{cnt} {t("squad.final")}</div>' if cnt else ""
        st.markdown(f'<div class="agentcard {css}"><div class="ic">{a["ic"]}</div><div class="nm">{a["nm"]}</div><div class="ds">{a["ds"]}</div><div class="st">{st_}</div>{cnt_html}</div>', unsafe_allow_html=True)

    st.divider()

    if st.session_state.get("squad_running"):
        arch_inp = ArchitectureInput(
            description=st.session_state.get("squad_arch",""),
            context=st.session_state.get("squad_ctx") or None,
        )
        q: Queue = Queue()

        def _run(q):
            import asyncio, json as _j
            from arch_review.squad.manager import AgentManager as _MG
            from arch_review.squad.squad import ReviewSquad as _SQ, AgentResult as _AR
            from arch_review.squad.prompts import build_synthesizer_prompt as _bsp, SYNTHESIZER_SYSTEM as _SS
            from arch_review.utils.json_parser import sanitize_architecture_input as _san
            import litellm as _ll

            async def _a():
                sq = _SQ(model=selected_model)
                mg = _MG()
                arch = _san(arch_inp.description); ctx = arch_inp.context or ""
                sp = sq.squad_memory.get_recurring_patterns()
                plan = mg.create_plan(arch_inp)
                q.put({"event":"start","agent":"manager_agent","plan":plan.model_dump()})
                q.put({"event":"done","agent":"manager_agent","count":len(plan.top_risks),"plan":plan.model_dump()})
                active_agents = {item.agent_name for item in plan.agent_plans if item.active}
                tasks = []
                for nm, sys_p, pfn in sq.AGENTS:
                    if nm not in active_agents:
                        q.put({"event":"done","agent":nm,"count":0,"skipped":True})
                        continue
                    q.put({"event":"start","agent":nm})
                    prompt = pfn(arch, ctx, sq.agent_memories[nm].get_lessons_section(), sp)
                    prompt = sq._inject_manager_guidance(prompt, plan, nm)
                    tasks.append((nm, sys_p, prompt))

                async def _call(nm, sys_p, prompt):
                    try:
                        r = await asyncio.to_thread(_ll.completion, model=sq.model,
                            messages=[{"role":"system","content":sys_p},{"role":"user","content":prompt}],
                            temperature=sq.temperature, max_tokens=sq.max_tokens)
                        d = sq._parse_json(r.choices[0].message.content or "", nm)
                        q.put({"event":"done","agent":nm,"count":len(d.get("findings",[])),"data":d})
                        return nm, d
                    except Exception as ex:
                        q.put({"event":"error","agent":nm,"error":str(ex)})
                        return nm, {"findings":[],"agent_insight":"","lesson_for_memory":""}

                res = await asyncio.gather(*[_call(n,s,p) for n,s,p in tasks])
                af, ins, ars = [], [], []
                for nm, d in res:
                    ar = _AR(agent_name=nm); ar.findings=d.get("findings",[]); ar.insight=d.get("agent_insight",""); ar.lesson=d.get("lesson_for_memory","")
                    ars.append(ar); af.extend(ar.findings)
                    if ar.insight: ins.append(f"[{nm}] {ar.insight}")

                q.put({"event":"start","agent":"synthesizer_agent"})
                sm = sq.agent_memories["synthesizer_agent"]
                sp2 = _bsp(arch, ctx, _j.dumps(af,indent=2), ins, sm.get_lessons_section(), sp)
                try:
                    sr = await asyncio.to_thread(_ll.completion, model=sq.model,
                        messages=[{"role":"system","content":_SS},{"role":"user","content":sp2}],
                        temperature=sq.temperature, max_tokens=sq.max_tokens)
                    sd = sq._parse_json(sr.choices[0].message.content or "", "synthesizer_agent")
                    q.put({"event":"done","agent":"synthesizer_agent","count":len(sd.get("findings",[])),"data":sd})
                except Exception as ex:
                    q.put({"event":"error","agent":"synthesizer_agent","error":str(ex)}); sd={"findings":af}

                from arch_review.models import ReviewResult as _RR
                ff = sq._build_findings(sd.get("findings", af))
                sm2 = sq._build_summary(ff, sd.get("overall_assessment",""))
                rv = _RR(input=arch_inp, findings=ff, summary=sm2,
                    senior_architect_questions=sd.get("senior_architect_questions",[]),
                    recommended_adrs=sd.get("recommended_adrs",[]), orchestration_plan=plan, model_used=f"squad:{sq.model}")
                sq._update_memories(ars, sd.get("lesson_for_memory",""), arch[:100], sd.get("cross_patterns",[]), sm2, plan)
                q.put({"event":"result","result":rv})

            asyncio.run(_a())
            q.put({"event":"finished"})

        t_thread = threading.Thread(target=_run, args=(q,), daemon=True)
        t_thread.start()
        squad_spinner = rand_msg(msgs["squad"])
        with st.spinner(squad_spinner):
            while True:
                try: ev = q.get(timeout=180)
                except Empty: st.error("Squad timed out."); break
                if ev["event"] in ("start","done","error"):
                    log.append(ev); st.session_state["squad_log"] = log
                elif ev["event"] == "result":
                    st.session_state["review_result"] = ev["result"]
                elif ev["event"] == "finished":
                    break

        st.session_state["squad_running"] = False
        if gen_adrs and "review_result" in st.session_state:
            with st.spinner(rand_msg(msgs["adr"])):
                try: st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(st.session_state["review_result"])
                except Exception: pass
        st.rerun()

    if "review_result" in st.session_state:
        r = st.session_state["review_result"]
        if "squad:" in r.model_used:
            s = r.summary
            st.success(f"{t('squad.complete')} **{s.total_findings} {t('squad.total_findings')}** · {s.critical_count} {t('squad.critical')} · {s.high_count} {t('squad.high')}")
            if s.top_risk: st.warning(f"{t('squad.top_risk')} **{esc(s.top_risk)}**")
            if r.orchestration_plan:
                plan = r.orchestration_plan
                with st.expander("🎯 Agent Manager Plan", expanded=True):
                    st.markdown(f"**Architecture type:** {esc(plan.architecture_type)}")
                    st.markdown(f"**Complexity:** {esc(plan.complexity)}")
                    if plan.compliance_flags:
                        st.markdown(f"**Compliance:** {esc(', '.join(plan.compliance_flags))}")
                    if plan.cloud_providers:
                        st.markdown(f"**Cloud:** {esc(', '.join(plan.cloud_providers))}")
                    if plan.top_risks:
                        st.markdown("**Top pre-review risks:**")
                        for risk in plan.top_risks:
                            st.markdown(f"- {esc(risk)}")
                    st.caption(plan.manager_briefing)
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

        if r.orchestration_plan:
            plan = r.orchestration_plan
            with st.expander("🎯 Agent Manager Plan", expanded=False):
                st.markdown(f"**Briefing:** {esc(plan.manager_briefing)}")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Architecture type:** {esc(plan.architecture_type)}")
                    st.markdown(f"**Complexity:** {esc(plan.complexity)}")
                    if plan.compliance_flags:
                        st.markdown(f"**Compliance flags:** {esc(', '.join(plan.compliance_flags))}")
                with c2:
                    if plan.cloud_providers:
                        st.markdown(f"**Cloud providers:** {esc(', '.join(plan.cloud_providers))}")
                    if plan.top_risks:
                        st.markdown("**Top detected risks before execution:**")
                        for risk in plan.top_risks:
                            st.markdown(f"- {esc(risk)}")

                st.markdown("**Per-agent focus**")
                for agent_plan in plan.agent_plans:
                    st.markdown(
                        f"{priority_badge(agent_plan.priority)} **{esc(agent_plan.agent_name)}** — {esc(agent_plan.rationale)}",
                        unsafe_allow_html=True,
                    )
                    for area in agent_plan.focus_areas:
                        st.markdown(f"  - {esc(area)}")
                skipped = [item.agent_name for item in plan.agent_plans if not item.active]
                if skipped:
                    st.markdown(f"**Skipped agents:** {esc(', '.join(skipped))}")

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
    alist = ["manager_agent","security_agent","reliability_agent","cost_agent","observability_agent","synthesizer_agent"]
    AGENT_META_MEM = {
        "manager_agent":       {"ic":"🎯","nm":"Agent Manager"},
        "security_agent":      {"ic":"🔐","nm":t("agent.security.nm")},
        "reliability_agent":   {"ic":"🛡️","nm":t("agent.reliability.nm")},
        "cost_agent":          {"ic":"💰","nm":t("agent.cost.nm")},
        "observability_agent": {"ic":"📡","nm":t("agent.observability.nm")},
        "synthesizer_agent":   {"ic":"🧠","nm":t("agent.synthesizer.nm")},
    }

    st.markdown(t("memory.title"))
    st.caption(t("memory.caption"))

    # ── Agent status cards ─────────────────────────────────────────────────────
    mcols = st.columns(6)
    for i, nm in enumerate(alist):
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
        acols = st.columns(6)
        for i, nm in enumerate(alist):
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
            with acols[i]:
                st.markdown(f"""
                <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:14px;
                padding:16px 12px;text-align:center">
                  <div style="font-size:1.6rem;margin-bottom:6px">{a["ic"]}</div>
                  <div style="font-weight:700;font-size:.82rem;color:#111">{a["nm"]}</div>
                  <div style="font-size:.72rem;font-weight:700;color:{color};margin:6px 0 4px">{level}</div>
                  <div style="background:#f3f4f6;border-radius:999px;height:5px;margin:6px 0">
                    <div style="background:{color};height:5px;border-radius:999px;width:{bar_w}%"></div>
                  </div>
                  <div style="font-size:.68rem;color:#6b7280;margin-top:6px">
                    {ls} {t("memory.evo.lessons_lbl")} · {pt} {t("memory.evo.patterns_lbl")}
                  </div>
                  <div style="font-size:.65rem;color:#9ca3af;margin-top:2px">
                    {t("memory.evo.last")} {last}
                  </div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()
        st.markdown(t("memory.evo.how_title"))
        st.markdown(f'<div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:12px;padding:20px 24px;font-size:.87rem;color:#374151;line-height:1.7">{t("memory.evo.how_body")}</div>', unsafe_allow_html=True)

    st.divider()

    # ── File viewer ────────────────────────────────────────────────────────────
    sel = st.selectbox(t("memory.view"), alist, format_func=lambda n: f"{AGENT_META_MEM[n]['ic']} {AGENT_META_MEM[n]['nm']}")
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
