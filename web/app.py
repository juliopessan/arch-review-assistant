"""Architecture Review Assistant — Streamlit Web UI v3."""

from __future__ import annotations

import html, io, os, re, sys, threading, zipfile
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

from arch_review.adr_generator import ADRGenerator
from arch_review.engine import SUPPORTED_MODELS, ReviewEngine
from arch_review.models import ArchitectureInput, FindingCategory, ReviewResult, Severity
from arch_review.models_adr import ADRGenerationResult
from arch_review.squad import ReviewSquad

# ── Tesseract required check (fail fast with friendly UI) ─────────────────────
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

# ── Minimal, surgical CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
/* Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Base */
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif !important; }
.main .block-container { max-width: 1100px !important; padding: 2rem 2rem 4rem !important; }
#MainMenu, footer { display: none !important; }

/* Typography */
h1 { font-size: 2.2rem !important; font-weight: 700 !important; letter-spacing: -.03em !important; margin-bottom: .25rem !important; }
h2 { font-size: 1.3rem !important; font-weight: 600 !important; margin: 1.5rem 0 .75rem !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; }
p, li { font-size: .94rem !important; line-height: 1.65 !important; }

/* Hero badge */
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: #f0f0ff; border: 1px solid #c7d2fe;
  color: #4338ca; border-radius: 999px;
  padding: 4px 14px; font-size: .75rem; font-weight: 600;
  letter-spacing: .04em; text-transform: uppercase; margin-bottom: 1rem;
}

/* Severity cards */
.scard {
  border-radius: 12px; padding: 16px 20px; margin-bottom: 14px;
  border: 1px solid #e5e7eb; background: #fff;
}
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

.pill {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: .7rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
}
.pill-critical { background: #fee2e2; color: #b91c1c; }
.pill-high     { background: #ffedd5; color: #c2410c; }
.pill-medium   { background: #fef9c3; color: #a16207; }
.pill-low      { background: #dbeafe; color: #1d4ed8; }
.pill-info     { background: #f3f4f6; color: #6b7280; }

/* Stat row */
.statrow { display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }
.stat {
  flex: 1; min-width: 80px; background: #fff; border: 1px solid #e5e7eb;
  border-radius: 12px; padding: 14px 10px; text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.stat .n { font-size: 1.9rem; font-weight: 800; line-height: 1; }
.stat .l { font-size: .7rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: #9ca3af; margin-top: 3px; }
.stat-c .n { color: #dc2626; } .stat-h .n { color: #ea580c; }
.stat-m .n { color: #ca8a04; } .stat-l .n { color: #2563eb; }
.stat-i .n { color: #9ca3af; } .stat-t .n { color: #4f46e5; }

/* Agent cards */
.agentrow { display: flex; gap: 10px; align-items: flex-start; }
.agentcard {
  flex: 1; background: #fff; border: 1.5px solid #e5e7eb;
  border-radius: 14px; padding: 16px 12px; text-align: center;
  transition: all .25s ease;
}
.agentcard.idle    { opacity: .45; }
.agentcard.running { border-color: #6366f1; background: #f5f3ff; box-shadow: 0 0 0 3px rgba(99,102,241,.1); }
.agentcard.done    { border-color: #16a34a; background: #f0fdf4; }
.agentcard.error   { border-color: #dc2626; background: #fef2f2; }
.agentcard .ic     { font-size: 1.6rem; margin-bottom: 6px; }
.agentcard .nm     { font-size: .82rem; font-weight: 700; color: #111; }
.agentcard .ds     { font-size: .68rem; color: #9ca3af; margin-top: 2px; line-height: 1.4; }
.agentcard .st     { font-size: .72rem; color: #6b7280; margin-top: 5px; }
.agentcard .ct     { font-size: .75rem; font-weight: 700; color: #4f46e5; margin-top: 3px; }
.arrow { font-size: 1.1rem; color: #d1d5db; padding-top: 22px; }

/* Memory cards */
.memcard {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
  padding: 14px 10px; text-align: center;
}
.memcard.live { border-color: #16a34a; background: #f0fdf4; }
.memcard .ic  { font-size: 1.3rem; }
.memcard .nm  { font-size: .78rem; font-weight: 700; color: #111; margin-top: 4px; }
.memcard .sz  { font-size: .68rem; color: #9ca3af; }
.memcard .ls  { font-size: .72rem; font-weight: 700; color: #4f46e5; margin-top: 2px; }

/* ADR card */
.adrcard {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
  padding: 18px 20px; margin-bottom: 10px;
}
.adrnum   { font-size: .72rem; font-weight: 700; color: #4f46e5; letter-spacing: .07em; text-transform: uppercase; }
.adrtitle { font-size: 1rem; font-weight: 700; color: #111; margin: 4px 0; }
.adrstatus{ display: inline-block; background: #eff6ff; color: #1d4ed8; border-radius: 999px; padding: 2px 10px; font-size: .7rem; font-weight: 700; }

/* File uploader cleanup */
[data-testid="stFileUploaderDropzone"] { border-radius: 12px !important; border: 1.5px dashed #c7d2fe !important; background: #fafbff !important; }
[data-testid="stFileUploaderDropzoneInstructions"] { color: #6366f1 !important; }

/* Textarea */
.stTextArea textarea { font-family: 'JetBrains Mono','Fira Code',monospace !important; font-size: .82rem !important; border-radius: 10px !important; border: 1.5px solid #e5e7eb !important; }
.stTextArea textarea:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,.1) !important; }

/* Buttons */
.stButton > button { border-radius: 10px !important; font-weight: 600 !important; font-size: .88rem !important; transition: all .15s !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px !important; border-bottom: 2px solid #f3f4f6 !important; }
.stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0 !important; font-size: .85rem !important; font-weight: 500 !important; padding: 8px 16px !important; color: #6b7280 !important; }
.stTabs [aria-selected="true"] { color: #4f46e5 !important; background: #f5f3ff !important; border-bottom: 2px solid #4f46e5 !important; }

/* Divider */
hr { border: none !important; border-top: 1px solid #f3f4f6 !important; margin: 1.5rem 0 !important; }

/* Code */
code { background: #f5f3ff !important; color: #4338ca !important; border-radius: 4px !important; padding: 1px 5px !important; }

/* Expander */
[data-testid="stExpander"] { border: 1px solid #e5e7eb !important; border-radius: 12px !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
SEV_LABEL = {Severity.CRITICAL:"🔴 CRITICAL",Severity.HIGH:"🟠 HIGH",Severity.MEDIUM:"🟡 MEDIUM",Severity.LOW:"🔵 LOW",Severity.INFO:"⚪ INFO"}
SEV_CSS   = {Severity.CRITICAL:"critical",Severity.HIGH:"high",Severity.MEDIUM:"medium",Severity.LOW:"low",Severity.INFO:"info"}
SEV_PILL  = {Severity.CRITICAL:"pill-critical",Severity.HIGH:"pill-high",Severity.MEDIUM:"pill-medium",Severity.LOW:"pill-low",Severity.INFO:"pill-info"}
ENV_MAP   = {"anthropic":"ANTHROPIC_API_KEY","openai":"OPENAI_API_KEY","google":"GEMINI_API_KEY","mistral":"MISTRAL_API_KEY"}
AGENTS    = {
    "security_agent":      {"ic":"🔐","nm":"Security",     "ds":"Auth · Secrets · Compliance"},
    "reliability_agent":   {"ic":"🛡️","nm":"Reliability",   "ds":"SPOFs · Resilience · Failover"},
    "cost_agent":          {"ic":"💰","nm":"Cost",           "ds":"FinOps · Sizing · Transfer"},
    "observability_agent": {"ic":"📡","nm":"Observability",  "ds":"Logs · Metrics · Tracing"},
    "synthesizer_agent":   {"ic":"🧠","nm":"Synthesizer",    "ds":"Patterns · Priority · ADRs"},
}
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

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    selected_model = st.selectbox("Model", list(SUPPORTED_MODELS.keys()), index=0, label_visibility="collapsed")
    provider = SUPPORTED_MODELS.get(selected_model,"")
    st.caption(f"Provider: `{provider}`")
    api_key = st.text_input("API Key", type="password", placeholder="sk-ant-... / sk-... etc.", label_visibility="collapsed")
    if api_key:
        os.environ[ENV_MAP.get(provider,"OPENAI_API_KEY")] = api_key
        st.success("✓ API key set")
    st.divider()
    focus_areas = st.multiselect("Focus areas", [c.value for c in FindingCategory], default=[], help="Leave empty = all categories")
    gen_adrs = st.toggle("Auto-generate ADRs", value=True)
    st.divider()
    st.caption("🏗️ [arch-review](https://github.com/juliopessan/arch-review-assistant) · MIT")

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="badge">✦ Multi-Agent · Self-Evolving · Open Source</div>', unsafe_allow_html=True)
st.title("Architecture Review Assistant")
st.markdown("**4 specialized AI agents** — Security, Reliability, Cost, Observability — run in parallel and learn from every review.", unsafe_allow_html=False)
st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_review, tab_squad, tab_findings, tab_adrs, tab_export, tab_memory = st.tabs([
    "✦ Review", "🤖 Squad", "🔍 Findings", "📄 ADRs", "📤 Export", "🧠 Memory"
])

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: REVIEW                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_review:
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        st.markdown("#### 📝 Architecture Description")
        arch_text = st.text_area(
            "arch", height=280, label_visibility="collapsed",
            placeholder="Paste your architecture — components, flows, Mermaid diagram, bullet points...",
            value=st.session_state.get("arch_prefill",""),
        )
        st.session_state.pop("arch_prefill", None)
        context = st.text_input("🌐 Business context (optional)", placeholder="e.g. LGPD compliance · 500 users · Azure single-region")

    with col_r:
        st.markdown("#### 📂 Upload File")
        st.caption(f"Supported: {', '.join('.' + f for f in get_supported_formats())}")
        uploaded = st.file_uploader("Upload", type=get_supported_formats(), label_visibility="collapsed")

        if uploaded:
            with st.spinner(f"Extracting from `{uploaded.name}`..."):
                try:
                    text = extract_from_bytes(uploaded.read(), uploaded.name)
                    st.session_state["arch_prefill"] = text
                    st.success(f"✅ {len(text):,} chars extracted")
                    with st.expander("Preview"):
                        st.code(text[:600] + ("…" if len(text) > 600 else ""), language="text")
                    if st.button("↑ Use as input", use_container_width=True, type="secondary"):
                        st.rerun()
                except Exception as exc:
                    st.error(f"⚠️ {exc}")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📋 Load example", use_container_width=True):
                st.session_state["arch_prefill"] = EXAMPLE
                st.rerun()
        with c2:
            if st.button("🗑️ Clear all", use_container_width=True):
                for k in ["review_result","adr_result","squad_log","arch_prefill"]: st.session_state.pop(k,None)
                st.rerun()

    st.divider()
    no_key = not api_key and not any(os.environ.get(k) for k in ENV_MAP.values())
    b1, b2, b3 = st.columns([1,1,2])
    with b1:
        run_squad  = st.button("🤖 Squad Review",  type="primary",   use_container_width=True, disabled=not arch_text.strip())
    with b2:
        run_single = st.button("⚡ Quick Review",  type="secondary", use_container_width=True, disabled=not arch_text.strip())
    with b3:
        if no_key:       st.warning("⚠️ Set your API key in the sidebar first.")
        elif not arch_text.strip(): st.info("Paste an architecture description to begin.")

    # Single review
    if run_single and arch_text.strip():
        arch_inp = ArchitectureInput(description=arch_text, context=context or None,
                                      focus_areas=[FindingCategory(f) for f in focus_areas])
        with st.spinner(f"Reviewing with `{selected_model}`..."):
            try:
                r = ReviewEngine(model=selected_model).review(arch_inp)
                st.session_state["review_result"] = r
                st.session_state.pop("adr_result", None)
            except Exception as exc:
                st.error(f"❌ {exc}"); st.stop()
        if gen_adrs:
            with st.spinner("Generating ADRs..."):
                try: st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(r)
                except Exception as exc: st.warning(f"ADR generation: {exc}")
        st.success("✅ Done — open the **Findings** tab."); st.rerun()

    # Squad trigger
    if run_squad and arch_text.strip():
        st.session_state.update({"squad_arch": arch_text, "squad_ctx": context,
                                   "squad_running": True, "squad_log": []})
        for k in ["review_result","adr_result"]: st.session_state.pop(k,None)
        st.rerun()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: SQUAD OFFICE                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_squad:
    st.markdown("#### 🤖 Squad Office — Virtual Workspace")
    st.caption("4 agents run in parallel. The Synthesizer consolidates findings. Each agent learns from every review.")

    log: list[dict] = st.session_state.get("squad_log", [])

    def _state(name: str):
        evts = [v for v in log if v.get("agent") == name]
        if any(v["event"]=="error" for v in evts): return "error","❌ failed",0
        if any(v["event"]=="done"  for v in evts):
            c = next((v.get("count",0) for v in evts if v["event"]=="done"),0)
            return "done","✅ done",c
        if any(v["event"]=="start" for v in evts): return "running","⏳ running…",0
        return "idle","waiting",0

    spec = list(AGENTS.keys())[:4]
    synth = list(AGENTS.keys())[4]

    # 4 parallel agents
    cols9 = st.columns(9)
    ac = [cols9[0],cols9[2],cols9[4],cols9[6]]
    for i, name in enumerate(spec):
        a = AGENTS[name]; css,st_,cnt = _state(name)
        cnt_html = f'<div class="ct">{cnt} findings</div>' if cnt else ""
        with ac[i]:
            st.markdown(f'<div class="agentcard {css}"><div class="ic">{a["ic"]}</div><div class="nm">{a["nm"]}</div><div class="ds">{a["ds"]}</div><div class="st">{st_}</div>{cnt_html}</div>', unsafe_allow_html=True)
        if i < 3:
            with cols9[i*2+1]:
                st.markdown('<div class="arrow" style="padding-top:22px">→</div>', unsafe_allow_html=True)

    # Synthesizer
    st.markdown("<br>", unsafe_allow_html=True)
    _, sc, _ = st.columns([2,1,2])
    with sc:
        a = AGENTS[synth]; css,st_,cnt = _state(synth)
        cnt_html = f'<div class="ct">{cnt} final</div>' if cnt else ""
        st.markdown(f'<div class="agentcard {css}"><div class="ic">{a["ic"]}</div><div class="nm">{a["nm"]}</div><div class="ds">{a["ds"]}</div><div class="st">{st_}</div>{cnt_html}</div>', unsafe_allow_html=True)

    st.divider()

    # ── Run squad ──────────────────────────────────────────────────────────────
    if st.session_state.get("squad_running"):
        arch_inp = ArchitectureInput(
            description=st.session_state.get("squad_arch",""),
            context=st.session_state.get("squad_ctx") or None,
        )
        q: Queue = Queue()

        def _run(q):
            import asyncio, json as _j
            from arch_review.squad.squad import ReviewSquad as _SQ, AgentResult as _AR
            from arch_review.squad.prompts import build_synthesizer_prompt as _bsp, SYNTHESIZER_SYSTEM as _SS
            from arch_review.utils.json_parser import sanitize_architecture_input as _san
            import litellm as _ll

            async def _a():
                sq = _SQ(model=selected_model)
                arch = _san(arch_inp.description); ctx = arch_inp.context or ""
                sp = sq.squad_memory.get_recurring_patterns()
                tasks = []
                for nm,sys_p,pfn in sq.AGENTS:
                    q.put({"event":"start","agent":nm})
                    tasks.append((nm,sys_p,pfn(arch,ctx,sq.agent_memories[nm].get_lessons_section(),sp)))

                async def _call(nm,sys_p,prompt):
                    try:
                        r = await asyncio.to_thread(_ll.completion,model=sq.model,
                            messages=[{"role":"system","content":sys_p},{"role":"user","content":prompt}],
                            temperature=sq.temperature,max_tokens=sq.max_tokens)
                        d = sq._parse_json(r.choices[0].message.content or "",nm)
                        q.put({"event":"done","agent":nm,"count":len(d.get("findings",[])),"data":d})
                        return nm,d
                    except Exception as ex:
                        q.put({"event":"error","agent":nm,"error":str(ex)})
                        return nm,{"findings":[],"agent_insight":"","lesson_for_memory":""}

                res = await asyncio.gather(*[_call(n,s,p) for n,s,p in tasks])
                af,ins,ars = [],[],[]
                for nm,d in res:
                    ar = _AR(agent_name=nm); ar.findings=d.get("findings",[]); ar.insight=d.get("agent_insight",""); ar.lesson=d.get("lesson_for_memory","")
                    ars.append(ar); af.extend(ar.findings)
                    if ar.insight: ins.append(f"[{nm}] {ar.insight}")

                q.put({"event":"start","agent":"synthesizer_agent"})
                sm = sq.agent_memories["synthesizer_agent"]
                sp2 = _bsp(arch,ctx,_j.dumps(af,indent=2),ins,sm.get_lessons_section(),sp)
                try:
                    sr = await asyncio.to_thread(_ll.completion,model=sq.model,
                        messages=[{"role":"system","content":_SS},{"role":"user","content":sp2}],
                        temperature=sq.temperature,max_tokens=sq.max_tokens)
                    sd = sq._parse_json(sr.choices[0].message.content or "","synthesizer_agent")
                    q.put({"event":"done","agent":"synthesizer_agent","count":len(sd.get("findings",[])),"data":sd})
                except Exception as ex:
                    q.put({"event":"error","agent":"synthesizer_agent","error":str(ex)}); sd={"findings":af}

                from arch_review.models import ReviewResult as _RR
                ff = sq._build_findings(sd.get("findings",af))
                sm2 = sq._build_summary(ff,sd.get("overall_assessment",""))
                rv = _RR(input=arch_inp,findings=ff,summary=sm2,
                    senior_architect_questions=sd.get("senior_architect_questions",[]),
                    recommended_adrs=sd.get("recommended_adrs",[]),model_used=f"squad:{sq.model}")
                sq._update_memories(ars,sd.get("lesson_for_memory",""),arch[:100],sd.get("cross_patterns",[]),sm2)
                q.put({"event":"result","result":rv})

            asyncio.run(_a())
            q.put({"event":"finished"})

        t = threading.Thread(target=_run, args=(q,), daemon=True)
        t.start()
        with st.spinner("Squad running — agents working in parallel (~30–60s)..."):
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
            with st.spinner("Generating ADRs..."):
                try: st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(st.session_state["review_result"])
                except Exception: pass
        st.rerun()

    if "review_result" in st.session_state:
        r = st.session_state["review_result"]
        if "squad:" in r.model_used:
            s = r.summary
            st.success(f"✅ Squad complete — **{s.total_findings} findings** · {s.critical_count} critical · {s.high_count} high")
            if s.top_risk: st.warning(f"⚠️ Top risk: **{esc(s.top_risk)}**")
    else:
        st.info("Start a **Squad Review** from the Review tab to see live agent activity here.")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: FINDINGS                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_findings:
    if "review_result" not in st.session_state:
        st.info("Run a review first — use the **Review** tab.")
    else:
        r: ReviewResult = st.session_state["review_result"]
        s = r.summary

        # Stat row
        st.markdown(f"""
        <div class="statrow">
          <div class="stat stat-c"><div class="n">{s.critical_count}</div><div class="l">Critical</div></div>
          <div class="stat stat-h"><div class="n">{s.high_count}</div><div class="l">High</div></div>
          <div class="stat stat-m"><div class="n">{s.medium_count}</div><div class="l">Medium</div></div>
          <div class="stat stat-l"><div class="n">{s.low_count}</div><div class="l">Low</div></div>
          <div class="stat stat-i"><div class="n">{s.info_count}</div><div class="l">Info</div></div>
          <div class="stat stat-t"><div class="n">{s.total_findings}</div><div class="l">Total</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Model: `{r.model_used}`")

        if s.overall_assessment:
            with st.expander("📋 Overall Assessment", expanded=True):
                st.write(s.overall_assessment)

        if r.senior_architect_questions:
            with st.expander("❓ Opening Questions"):
                for i,q in enumerate(r.senior_architect_questions,1):
                    st.markdown(f"**{i}.** {q}")

        st.markdown("#### Findings")
        sev_filter = st.multiselect("Filter by severity", [sv.value for sv in Severity], default=[sv.value for sv in Severity], label_visibility="collapsed")
        filtered = [f for f in r.findings if f.severity.value in sev_filter]

        for f in filtered:
            css = SEV_CSS[f.severity]; pill = SEV_PILL[f.severity]
            cat = f.category.value.upper().replace("_"," ")
            comps = f'<div class="scard-affects">🔗 Affects: {esc(", ".join(f.affected_components))}</div>' if f.affected_components else ""
            qs_html = "".join(f'&ldquo;{esc(q)}&rdquo; &nbsp;' for q in f.questions_to_ask)
            refs = f'<div class="scard-q">📚 {esc(" · ".join(f.references))}</div>' if f.references else ""
            st.markdown(f"""
            <div class="scard {css}">
              <div class="scard-meta"><span class="pill {pill}">{f.severity.value}</span> &nbsp; {esc(cat)}</div>
              <div class="scard-title">{esc(f.title)}</div>
              <div class="scard-desc">{esc(f.description)}</div>
              {comps}
              <div class="scard-rec">✅ {esc(f.recommendation)}</div>
              {f'<div class="scard-q">💬 {qs_html}</div>' if qs_html else ""}
              {refs}
            </div>
            """, unsafe_allow_html=True)

        if r.recommended_adrs:
            st.markdown("#### 📌 Recommended ADRs")
            for i,t in enumerate(r.recommended_adrs,1):
                st.markdown(f"**{i}.** {t}")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: ADRs                                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_adrs:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    elif "adr_result" not in st.session_state:
        c1,c2 = st.columns([1,3])
        with c1:
            if st.button("⚡ Generate ADRs", type="primary", use_container_width=True):
                with st.spinner("Generating..."):
                    try:
                        st.session_state["adr_result"] = ADRGenerator(model=selected_model).from_review(st.session_state["review_result"])
                        st.rerun()
                    except Exception as exc: st.error(str(exc))
        with c2: st.info("ADRs not yet generated.")
    else:
        ar: ADRGenerationResult = st.session_state["adr_result"]
        st.success(f"✅ {ar.total_generated} ADR(s) generated — `{ar.model_used}`")
        for adr in ar.adrs:
            num = str(adr.number).zfill(4)
            with st.expander(f"ADR-{num} — {adr.title}"):
                st.markdown(f'<div class="adrcard"><div class="adrnum">ADR-{num}</div><div class="adrtitle">{esc(adr.title)}</div><span class="adrstatus">{adr.status.value}</span></div>', unsafe_allow_html=True)
                if adr.context:
                    st.markdown("**Context**"); st.write(adr.context)
                if adr.decision_drivers:
                    st.markdown("**Decision Drivers**")
                    for d in adr.decision_drivers: st.markdown(f"- {d}")
                if adr.considered_options:
                    st.markdown("**Options Considered**")
                    for opt in adr.considered_options:
                        o1,o2 = st.columns(2)
                        o1.markdown(f"**{opt.title}**"); o1.write(opt.description)
                        if opt.pros:
                            for p in opt.pros: o1.markdown(f"✅ {p}")
                        if opt.cons:
                            for c in opt.cons: o2.markdown(f"⚠️ {c}")
                if adr.decision:
                    st.markdown("**Decision**"); st.success(adr.decision)
                pc,nc = st.columns(2)
                for c in adr.consequences_positive: pc.markdown(f"✅ {c}")
                for c in adr.consequences_negative: nc.markdown(f"⚠️ {c}")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: EXPORT                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_export:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    else:
        r: ReviewResult = st.session_state["review_result"]
        st.markdown("#### Export Review")
        e1,e2 = st.columns(2)
        with e1:
            st.markdown("**JSON** — for CI/CD")
            st.download_button("⬇️ review.json", r.model_dump_json(indent=2), "arch-review.json","application/json",use_container_width=True)
        with e2:
            st.markdown("**Markdown** — Confluence / Notion / GitHub")
            st.download_button("⬇️ review.md", _build_md(r), "arch-review.md","text/markdown",use_container_width=True)
        if "adr_result" in st.session_state:
            st.divider()
            st.markdown("#### Export ADRs")
            a = st.session_state["adr_result"]
            st.download_button(f"⬇️ {a.total_generated} ADR(s) as .zip", _build_zip(a),"adrs.zip","application/zip",use_container_width=True)
            st.caption("Unzip into `docs/adr/` and commit.")
        st.divider()
        st.markdown("**Markdown Preview**")
        st.code(_build_md(r), language="markdown")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB: MEMORY                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_memory:
    from arch_review.squad.memory import DEFAULT_MEMORY_DIR, AgentMemory, SquadMemory
    mem = DEFAULT_MEMORY_DIR
    alist = list(AGENTS.keys())

    st.markdown("#### 🧠 Agent Memory")
    st.caption(f"Stored in `{mem}`. Agents learn from every squad review.")

    mcols = st.columns(5)
    for i,nm in enumerate(alist):
        a = AGENTS[nm]; f = mem/f"{nm}.md"
        exists = f.exists()
        sz = f"{f.stat().st_size:,}b" if exists else "—"
        ls = f.read_text().count("## Lesson") if exists else 0
        with mcols[i]:
            st.markdown(f'<div class="memcard {"live" if exists else ""}"><div class="ic">{a["ic"]}</div><div class="nm">{a["nm"]}</div><div class="sz">{sz}</div><div class="ls">{ls} lessons</div></div>', unsafe_allow_html=True)

    sqf = mem/"SQUAD_MEMORY.md"
    if sqf.exists():
        rv = sqf.read_text().count("## Review [")
        pt = sqf.read_text().count("## Cross-Agent Pattern")
        st.info(f"📊 **SQUAD_MEMORY.md** — {rv} reviews · {pt} cross-agent patterns")

    st.divider()
    sel = st.selectbox("View memory file", alist, format_func=lambda n: f"{AGENTS[n]['ic']} {AGENTS[n]['nm']}")
    mf = mem/f"{sel}.md"
    if mf.exists():
        t1,t2 = st.tabs(["Full","Lessons only"])
        with t1: st.code(mf.read_text(), language="markdown")
        with t2:
            txt = mf.read_text(); sec = txt.split("---",1)[1].strip() if "---" in txt else "(no lessons yet)"
            st.code(sec, language="markdown")
    else:
        st.info("No memory yet — run a squad review first.")

    st.markdown("**Squad Memory**")
    if sqf.exists(): st.code(sqf.read_text(), language="markdown")
    else: st.info("No squad memory yet.")

    st.divider()
    if st.button("🗑️ Reset memories", type="secondary"):
        if st.session_state.get("_reset_ok"):
            for nm in alist:
                f = mem/f"{nm}.md"
                if f.exists(): f.unlink()
                AgentMemory(nm, mem)
            if sqf.exists(): sqf.unlink()
            SquadMemory(mem)
            st.session_state.pop("_reset_ok",None)
            st.success("✓ All memories reset."); st.rerun()
        else:
            st.session_state["_reset_ok"] = True
            st.warning("Click again to confirm — cannot be undone.")


# ── Helpers ────────────────────────────────────────────────────────────────────
def _build_md(r: ReviewResult) -> str:
    s = r.summary
    lines = ["# Architecture Review Report",f"\n> Model: `{r.model_used}`\n",
        "## Summary\n","| Severity | Count |","|----------|-------|",
        f"| 🔴 Critical | {s.critical_count} |",f"| 🟠 High | {s.high_count} |",
        f"| 🟡 Medium | {s.medium_count} |",f"| 🔵 Low | {s.low_count} |",
        f"| ⚪ Info | {s.info_count} |",f"| **Total** | **{s.total_findings}** |",
        f"\n## Overall Assessment\n\n{s.overall_assessment}"]
    if r.senior_architect_questions:
        lines += ["\n## Opening Questions\n"]+[f"- {q}" for q in r.senior_architect_questions]
    lines.append("\n## Findings\n")
    for f in r.findings:
        cat = f.category.value.upper().replace("_"," ")
        lines += [f"\n### {SEV_LABEL[f.severity]} — {f.title}",
            f"\n**Category:** {cat}\n\n{f.description}\n"]
        if f.affected_components: lines.append(f"**Affected:** {', '.join(f.affected_components)}\n")
        lines.append(f"**Recommendation:** {f.recommendation}\n")
        if f.questions_to_ask: lines += ["**Questions:**"]+[f"- {q}" for q in f.questions_to_ask]
    if r.recommended_adrs:
        lines += ["\n## Recommended ADRs\n"]+[f"{i}. {a}" for i,a in enumerate(r.recommended_adrs,1)]
    return "\n".join(lines)

def _build_zip(ar: ADRGenerationResult) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for adr in ar.adrs:
            num = str(adr.number).zfill(4)
            slug = re.sub(r"[\s_]+","-",re.sub(r"[^\w\s-]","",adr.title.lower())).strip("-")[:60]
            d = "\n".join(f"* {x}" for x in adr.decision_drivers) or "* _(not specified)_"
            p = "\n".join(f"* {x}" for x in adr.consequences_positive) or "* _(none)_"
            n = "\n".join(f"* {x}" for x in adr.consequences_negative) or "* _(none)_"
            body = "\n".join([f"# {num}. {adr.title}\n",f"Date: {adr.date}\n",
                f"## Status\n\n{adr.status.value.capitalize()}\n",
                f"## Context\n\n{adr.context}\n",f"## Decision Drivers\n\n{d}\n",
                f"## Decision\n\n{adr.decision}\n",
                f"## Positive Consequences\n\n{p}\n",f"## Negative Consequences\n\n{n}\n",
            ]+(["## Links\n"]+[f"* {lk}" for lk in adr.links] if adr.links else []))
            zf.writestr(f"{num}-{slug}.md", body)
    buf.seek(0); return buf.read()
