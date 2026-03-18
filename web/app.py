"""Architecture Review Assistant — Streamlit Web UI."""

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
from arch_review.squad import ReviewSquad

# ── Security helper ────────────────────────────────────────────────────────────
def e(text: str) -> str:
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

/* Squad Office */
.agent-card{background:#f8fafc;border:1.5px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;transition:all .3s}
.agent-running{border-color:#6366f1;background:#eef2ff;box-shadow:0 0 0 3px rgba(99,102,241,.15)}
.agent-done   {border-color:#22c55e;background:#f0fdf4}
.agent-error  {border-color:#ef4444;background:#fef2f2}
.agent-idle   {border-color:#e2e8f0;background:#f8fafc;opacity:.6}
.agent-emoji  {font-size:28px;display:block;margin-bottom:6px}
.agent-label  {font-weight:600;font-size:13px;color:#1e293b}
.agent-status {font-size:11px;color:#64748b;margin-top:3px}
.agent-count  {font-size:11px;font-weight:600;color:#6366f1;margin-top:3px}
.pipeline-arrow{font-size:22px;color:#94a3b8;text-align:center;padding-top:28px}
.memory-badge {background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:4px 10px;font-size:11px;color:#166534;display:inline-block;margin:2px}
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
ICONS = {
    Severity.CRITICAL:"🔴", Severity.HIGH:"🟠",
    Severity.MEDIUM:"🟡", Severity.LOW:"🔵", Severity.INFO:"⚪",
}
CSS_CLASS = {
    Severity.CRITICAL:"sev-critical", Severity.HIGH:"sev-high",
    Severity.MEDIUM:"sev-medium",  Severity.LOW:"sev-low", Severity.INFO:"sev-info",
}
ENV_MAP = {
    "anthropic":"ANTHROPIC_API_KEY","openai":"OPENAI_API_KEY",
    "google":"GEMINI_API_KEY","mistral":"MISTRAL_API_KEY",
}
AGENT_META = {
    "security_agent":      {"emoji":"🔐","label":"Security",      "desc":"Auth · Secrets · Compliance"},
    "reliability_agent":   {"emoji":"🛡️","label":"Reliability",    "desc":"SPOFs · Resilience · Failover"},
    "cost_agent":          {"emoji":"💰","label":"Cost",            "desc":"FinOps · Sizing · Transfer"},
    "observability_agent": {"emoji":"📡","label":"Observability",   "desc":"Logs · Metrics · Tracing"},
    "synthesizer_agent":   {"emoji":"🧠","label":"Synthesizer",     "desc":"Cross-patterns · Priority"},
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
        st.success(f"✓ `{env_var}` set")

    st.subheader("🎯 Focus Areas")
    focus_areas = st.multiselect(
        "Limit review to (optional)",
        [c.value for c in FindingCategory], default=[],
    )

    st.subheader("📄 ADR Generator")
    generate_adrs = st.toggle("Generate ADRs after review", value=True)

    st.divider()
    st.caption("📖 [GitHub](https://github.com/juliopessan/arch-review-assistant) · MIT")

# ── Main ───────────────────────────────────────────────────────────────────────
st.title("🏗️ Architecture Review Assistant")
st.caption("Single-agent review or full 4-agent squad with memory evolution.")

tab_input, tab_squad, tab_findings, tab_adrs, tab_export, tab_memory = st.tabs([
    "📝 Input", "🤖 Squad Office", "🔍 Findings", "📄 ADRs", "📤 Export", "🧠 Memory"
])

# ── Tab: Input ─────────────────────────────────────────────────────────────────
with tab_input:
    col1, col2 = st.columns([3, 1])
    with col1:
        arch_text = st.text_area(
            "Architecture description", height=360,
            placeholder="Paste your architecture — prose, Mermaid, bullet points...",
        )
    with col2:
        st.markdown("**Context (optional)**")
        context_text = st.text_area(
            "Context", height=160, label_visibility="collapsed",
            placeholder="e.g. LGPD compliance. ~500 users. Azure.",
        )
        if st.button("📋 Load example", use_container_width=True):
            st.session_state["load_example"] = True
            st.rerun()
        if st.button("🗑️ Clear all", use_container_width=True):
            for k in ["review_result","adr_result","squad_result","squad_log"]:
                st.session_state.pop(k, None)
            st.rerun()

    if st.session_state.pop("load_example", False):
        arch_text = EXAMPLE_ARCH

    st.divider()
    no_key = not api_key and not any(os.environ.get(k) for k in ENV_MAP.values())

    c1, c2, c3 = st.columns(3)
    with c1:
        run_single = st.button(
            "⚡ Quick Review",
            type="secondary", use_container_width=True,
            disabled=not arch_text.strip(),
            help="Single LLM call — fast, good for quick checks.",
        )
    with c2:
        run_squad = st.button(
            "🤖 Squad Review",
            type="primary", use_container_width=True,
            disabled=not arch_text.strip(),
            help="4 specialized agents in parallel — deeper, ~60s.",
        )
    with c3:
        if not arch_text.strip():
            st.info("Paste an architecture to begin.")
        elif no_key:
            st.warning("⚠️ Set an API key in the sidebar.")

    # ── Quick (single) review ──────────────────────────────────────────────────
    if run_single and arch_text.strip():
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
                st.error(f"❌ {exc}"); st.stop()

        if generate_adrs:
            with st.spinner("Generating ADRs..."):
                try:
                    st.session_state["adr_result"] = ADRGenerator(
                        model=selected_model
                    ).from_review(result)
                except Exception as exc:
                    st.warning(f"ADR generation failed: {exc}")

        st.success("✅ Done — see **Findings** tab.")
        st.rerun()

    # ── Squad review ───────────────────────────────────────────────────────────
    if run_squad and arch_text.strip():
        st.session_state["squad_arch"] = arch_text
        st.session_state["squad_context"] = context_text
        st.session_state["squad_running"] = True
        st.session_state["squad_log"] = []
        for k in ["review_result","adr_result"]:
            st.session_state.pop(k, None)
        st.rerun()


# ── Tab: Squad Office ──────────────────────────────────────────────────────────
with tab_squad:
    st.subheader("🤖 Squad Office — Virtual Workspace")
    st.caption("4 agents run in parallel, then the Synthesizer consolidates findings.")

    # Agent state display
    agent_keys  = list(AGENT_META.keys())
    spec_agents = agent_keys[:4]
    synth_agent = agent_keys[4]

    squad_log: list[dict] = st.session_state.get("squad_log", [])

    def _agent_status(name: str) -> tuple[str, str, int]:
        """Return (css_class, status_text, finding_count) for an agent."""
        events = [e for e in squad_log if e.get("agent") == name]
        if any(e["event"] == "error" for e in events):
            return "agent-error", "❌ error", 0
        if any(e["event"] == "done" for e in events):
            count = next((e.get("count",0) for e in events if e["event"]=="done"), 0)
            return "agent-done", "✅ done", count
        if any(e["event"] == "start" for e in events):
            return "agent-running", "⏳ running...", 0
        return "agent-idle", "waiting", 0

    # Render 4 parallel agents
    cols = st.columns([1, 0.12, 1, 0.12, 1, 0.12, 1, 0.15, 1])
    agent_cols = [cols[0], cols[2], cols[4], cols[6]]
    arrow_cols = [cols[1], cols[3], cols[5]]
    synth_col  = cols[8]

    for i, name in enumerate(spec_agents):
        meta = AGENT_META[name]
        css, status, count = _agent_status(name)
        with agent_cols[i]:
            count_html = f'<div class="agent-count">{count} findings</div>' if count else ""
            st.markdown(
                f'<div class="agent-card {css}">'
                f'<span class="agent-emoji">{meta["emoji"]}</span>'
                f'<div class="agent-label">{meta["label"]}</div>'
                f'<div class="agent-status">{meta["desc"]}</div>'
                f'<div class="agent-status">{status}</div>'
                f'{count_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
        if i < 3:
            with arrow_cols[i]:
                st.markdown('<div class="pipeline-arrow">⟶</div>', unsafe_allow_html=True)

    # Synthesizer
    st.markdown("")
    synth_css, synth_status, synth_count = _agent_status(synth_agent)
    sc1, sc2, sc3 = st.columns([2, 1, 2])
    with sc2:
        meta = AGENT_META[synth_agent]
        count_html = f'<div class="agent-count">{synth_count} final findings</div>' if synth_count else ""
        st.markdown(
            f'<div class="agent-card {synth_css}" style="margin-top:8px">'
            f'<span class="agent-emoji">{meta["emoji"]}</span>'
            f'<div class="agent-label">{meta["label"]}</div>'
            f'<div class="agent-status">{meta["desc"]}</div>'
            f'<div class="agent-status">{synth_status}</div>'
            f'{count_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Run squad if triggered ─────────────────────────────────────────────────
    if st.session_state.get("squad_running"):
        arch_text_sq = st.session_state.get("squad_arch","")
        ctx_sq       = st.session_state.get("squad_context","")
        log_placeholder = st.empty()
        result_placeholder = st.empty()

        arch_input = ArchitectureInput(
            description=arch_text_sq,
            context=ctx_sq or None,
        )

        # Run squad in thread, stream events via queue
        event_q: Queue = Queue()

        def _run_squad_threaded(q: Queue) -> None:
            """Run squad and push events into the queue for live UI updates."""
            import asyncio
            import json as _json

            async def _run():
                from arch_review.squad.squad import ReviewSquad as _Squad

                squad = _Squad(model=selected_model)
                arch  = arch_input.description
                ctx   = arch_input.context or ""
                sp    = squad.squad_memory.get_recurring_patterns()

                # Manually wire async calls so we can emit events
                tasks = []
                for name, system, prompt_fn in squad.AGENTS:
                    lessons = squad.agent_memories[name].get_lessons_section()
                    prompt  = prompt_fn(arch, ctx, lessons, sp)
                    q.put({"event":"start","agent":name})
                    tasks.append((name, system, prompt))

                async def _call(name, system, prompt):
                    import litellm as _litellm
                    try:
                        resp = await asyncio.to_thread(
                            _litellm.completion,
                            model=squad.model,
                            messages=[
                                {"role":"system","content":system},
                                {"role":"user",  "content":prompt},
                            ],
                            temperature=squad.temperature,
                            max_tokens=squad.max_tokens,
                        )
                        raw  = resp.choices[0].message.content or ""
                        data = squad._parse_json(raw, name)
                        count = len(data.get("findings",[]))
                        q.put({"event":"done","agent":name,"count":count,"data":data})
                        return name, data
                    except Exception as ex:
                        q.put({"event":"error","agent":name,"error":str(ex)})
                        return name, {"findings":[], "agent_insight":"", "lesson_for_memory":""}

                results = await asyncio.gather(*[_call(n,s,p) for n,s,p in tasks])

                all_findings = []
                insights     = []
                agent_results_list = []
                for name, data in results:
                    from arch_review.squad.squad import AgentResult as _AR
                    ar = _AR(agent_name=name)
                    ar.findings = data.get("findings",[])
                    ar.insight  = data.get("agent_insight","")
                    ar.lesson   = data.get("lesson_for_memory","")
                    agent_results_list.append(ar)
                    all_findings.extend(ar.findings)
                    if ar.insight:
                        insights.append(f"[{name}] {ar.insight}")

                # Synthesizer
                q.put({"event":"start","agent":"synthesizer_agent"})
                synth_mem    = squad.agent_memories["synthesizer_agent"]
                from arch_review.squad.prompts import build_synthesizer_prompt as _bsp, SYNTHESIZER_SYSTEM as _SS
                synth_prompt = _bsp(arch, ctx, _json.dumps(all_findings,indent=2), insights,
                                    synth_mem.get_lessons_section(), sp)
                import litellm as _litellm
                try:
                    sr = await asyncio.to_thread(
                        _litellm.completion,
                        model=squad.model,
                        messages=[
                            {"role":"system","content":_SS},
                            {"role":"user",  "content":synth_prompt},
                        ],
                        temperature=squad.temperature,
                        max_tokens=squad.max_tokens,
                    )
                    sraw  = sr.choices[0].message.content or ""
                    sdata = squad._parse_json(sraw, "synthesizer_agent")
                    q.put({"event":"done","agent":"synthesizer_agent",
                           "count":len(sdata.get("findings",[])),"data":sdata})
                except Exception as ex:
                    q.put({"event":"error","agent":"synthesizer_agent","error":str(ex)})
                    sdata = {"findings":all_findings}

                # Build final result
                final_findings = squad._build_findings(sdata.get("findings", all_findings))
                summary        = squad._build_summary(final_findings,
                                                       sdata.get("overall_assessment",""))
                from arch_review.models import ReviewResult as _RR
                review = _RR(
                    input=arch_input,
                    findings=final_findings,
                    summary=summary,
                    senior_architect_questions=sdata.get("senior_architect_questions",[]),
                    recommended_adrs=sdata.get("recommended_adrs",[]),
                    model_used=f"squad:{squad.model}",
                )

                # Update memories
                squad._update_memories(
                    agent_results_list,
                    sdata.get("lesson_for_memory",""),
                    arch[:100],
                    sdata.get("cross_patterns",[]),
                    summary,
                )

                q.put({"event":"result","result":review})

            asyncio.run(_run())
            q.put({"event":"finished"})

        thread = threading.Thread(target=_run_squad_threaded, args=(event_q,), daemon=True)
        thread.start()

        # Poll queue and update UI live
        with st.spinner(""):
            while True:
                try:
                    ev = event_q.get(timeout=120)
                except Empty:
                    st.error("Squad timed out."); break

                if ev["event"] == "start":
                    squad_log.append(ev)
                    st.session_state["squad_log"] = squad_log
                elif ev["event"] in ("done", "error"):
                    squad_log.append(ev)
                    st.session_state["squad_log"] = squad_log
                elif ev["event"] == "result":
                    st.session_state["review_result"] = ev["result"]
                elif ev["event"] == "finished":
                    break

        st.session_state["squad_running"] = False

        if generate_adrs and "review_result" in st.session_state:
            with st.spinner("Generating ADRs from squad findings..."):
                try:
                    st.session_state["adr_result"] = ADRGenerator(
                        model=selected_model
                    ).from_review(st.session_state["review_result"])
                except Exception as exc:
                    st.warning(f"ADR generation failed: {exc}")

        st.rerun()

    # Show result summary if available
    if "review_result" in st.session_state and not st.session_state.get("squad_running"):
        r = st.session_state["review_result"]
        if "squad:" in r.model_used:
            s = r.summary
            st.success(
                f"✅ Squad complete — **{s.total_findings} findings** "
                f"({s.critical_count} critical · {s.high_count} high)"
            )
            if r.summary.top_risk:
                st.warning(f"⚠️ Top risk: **{r.summary.top_risk}**")
            st.info("See the **Findings** tab for the full report.")


# ── Tab: Findings ──────────────────────────────────────────────────────────────
with tab_findings:
    if "review_result" not in st.session_state:
        st.info("Run a review first (Input tab).")
    else:
        result: ReviewResult = st.session_state["review_result"]
        s = result.summary

        m1,m2,m3,m4,m5,m6 = st.columns(6)
        m1.metric("🔴 Critical", s.critical_count)
        m2.metric("🟠 High",     s.high_count)
        m3.metric("🟡 Medium",   s.medium_count)
        m4.metric("🔵 Low",      s.low_count)
        m5.metric("⚪ Info",     s.info_count)
        m6.metric("📊 Total",    s.total_findings)
        st.caption(f"Model: `{result.model_used}`")
        st.divider()

        with st.expander("📋 Overall Assessment", expanded=True):
            st.write(s.overall_assessment)

        if result.senior_architect_questions:
            with st.expander("❓ Opening Questions"):
                for i,q in enumerate(result.senior_architect_questions,1):
                    st.markdown(f"**{i}.** {q}")

        st.subheader("Findings")
        sev_filter = st.multiselect(
            "Filter by severity",
            [sv.value for sv in Severity],
            default=[sv.value for sv in Severity], horizontal=True,
        )
        filtered = [f for f in result.findings if f.severity.value in sev_filter]

        for finding in filtered:
            css  = CSS_CLASS[finding.severity]
            icon = ICONS[finding.severity]
            cat  = finding.category.value.upper().replace("_"," ")
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
            for i,t in enumerate(result.recommended_adrs,1):
                st.markdown(f"**{i}.** {t}")


# ── Tab: ADRs ──────────────────────────────────────────────────────────────────
with tab_adrs:
    if "review_result" not in st.session_state:
        st.info("Run a review first.")
    elif "adr_result" not in st.session_state:
        c1,c2 = st.columns([1,3])
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
            st.info("ADRs not yet generated. Click to generate.")
    else:
        adr_result: ADRGenerationResult = st.session_state["adr_result"]
        st.success(f"✅ {adr_result.total_generated} ADR(s) — `{adr_result.model_used}`")

        for adr in adr_result.adrs:
            num = str(adr.number).zfill(4)
            with st.expander(f"📄 ADR-{num} — {adr.title}", expanded=False):
                cl,cr = st.columns(2)
                cl.markdown(f"**Status:** `{adr.status.value}`")
                cr.markdown(f"**Date:** {adr.date}")
                st.markdown("**Context**"); st.write(adr.context)
                if adr.decision_drivers:
                    st.markdown("**Decision Drivers**")
                    for d in adr.decision_drivers: st.markdown(f"- {d}")
                if adr.considered_options:
                    st.markdown("**Options Considered**")
                    for opt in adr.considered_options:
                        st.markdown(f"**{opt.title}**"); st.write(opt.description)
                        oc1,oc2 = st.columns(2)
                        if opt.pros:
                            oc1.markdown("✅ **Pros**")
                            for p in opt.pros: oc1.markdown(f"- {p}")
                        if opt.cons:
                            oc2.markdown("⚠️ **Cons**")
                            for c in opt.cons: oc2.markdown(f"- {c}")
                st.markdown("**Decision**"); st.success(adr.decision)
                if adr.consequences_positive or adr.consequences_negative:
                    pc,nc = st.columns(2)
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
        ec1,ec2 = st.columns(2)
        with ec1:
            st.markdown("**JSON** — for CI/CD")
            st.download_button("⬇️ review.json", result.model_dump_json(indent=2),
                               "arch-review.json","application/json",use_container_width=True)
        with ec2:
            st.markdown("**Markdown** — Confluence / Notion")
            st.download_button("⬇️ review.md", _build_md(result),
                               "arch-review.md","text/markdown",use_container_width=True)
        if "adr_result" in st.session_state:
            st.divider()
            st.subheader("📄 Export ADRs")
            adr_result: ADRGenerationResult = st.session_state["adr_result"]
            st.download_button(
                f"⬇️ {adr_result.total_generated} ADR(s) as .zip",
                _build_adr_zip(adr_result),"adrs.zip","application/zip",
                use_container_width=True,
            )
            st.caption("Unzip into `docs/adr/` and commit.")
        st.divider()
        st.subheader("👁️ Markdown Preview")
        st.code(_build_md(result), language="markdown")


# ── Tab: Memory ────────────────────────────────────────────────────────────────
with tab_memory:
    st.subheader("🧠 Agent Memory & Evolution")
    st.caption("Stored in `~/.arch-review/memory/`. Agents learn from every review.")

    from arch_review.squad.memory import DEFAULT_MEMORY_DIR, AgentMemory, SquadMemory

    mem_dir = DEFAULT_MEMORY_DIR
    agents_list = [
        "security_agent","reliability_agent","cost_agent",
        "observability_agent","synthesizer_agent"
    ]

    # Memory file status
    status_cols = st.columns(5)
    for i, name in enumerate(agents_list):
        meta = AGENT_META[name]
        mem_file = mem_dir / f"{name}.md"
        exists = mem_file.exists()
        size = f"{mem_file.stat().st_size:,}b" if exists else "not created"
        lessons = mem_file.read_text().count("## Lesson") if exists else 0
        with status_cols[i]:
            color = "#f0fdf4" if exists else "#f8fafc"
            border = "#86efac" if exists else "#e2e8f0"
            st.markdown(
                f'<div style="background:{color};border:1px solid {border};'
                f'border-radius:10px;padding:12px;text-align:center">'
                f'<div style="font-size:22px">{meta["emoji"]}</div>'
                f'<div style="font-weight:600;font-size:12px">{meta["label"]}</div>'
                f'<div style="font-size:11px;color:#64748b">{size}</div>'
                f'<div style="font-size:11px;color:#6366f1">{lessons} lessons</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # Squad memory
    squad_mem_file = mem_dir / "SQUAD_MEMORY.md"
    if squad_mem_file.exists():
        reviews = squad_mem_file.read_text().count("## Review [")
        patterns = squad_mem_file.read_text().count("## Cross-Agent Pattern")
        st.markdown(
            f'<div style="background:#fefce8;border:1px solid #fde047;border-radius:10px;'
            f'padding:14px;margin-bottom:16px">'
            f'<span style="font-size:18px">📊</span> '
            f'<strong>SQUAD_MEMORY.md</strong> — '
            f'{reviews} reviews recorded · {patterns} cross-agent patterns'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Agent memory viewer
    st.subheader("View Agent Memory")
    selected_agent = st.selectbox(
        "Select agent", agents_list,
        format_func=lambda n: f"{AGENT_META[n]['emoji']} {AGENT_META[n]['label']}",
    )
    mem_file = mem_dir / f"{selected_agent}.md"
    if mem_file.exists():
        tab_a, tab_b = st.tabs(["📖 Full Memory", "📝 Lessons Only"])
        with tab_a:
            st.code(mem_file.read_text(), language="markdown")
        with tab_b:
            content = mem_file.read_text()
            lessons_section = content.split("---",1)[1] if "---" in content else "(no lessons yet)"
            st.code(lessons_section.strip(), language="markdown")
    else:
        st.info(f"Memory for `{selected_agent}` not yet created — run a squad review first.")

    # Squad memory viewer
    st.subheader("Squad Memory")
    if squad_mem_file.exists():
        st.code(squad_mem_file.read_text(), language="markdown")
    else:
        st.info("No squad memory yet — run a squad review first.")

    # Reset button
    st.divider()
    if st.button("🗑️ Reset all agent memories", type="secondary"):
        if st.session_state.get("confirm_reset"):
            for a in agents_list:
                f = mem_dir / f"{a}.md"
                if f.exists(): f.unlink()
                AgentMemory(a, mem_dir)
            sq = mem_dir / "SQUAD_MEMORY.md"
            if sq.exists(): sq.unlink()
            SquadMemory(mem_dir)
            st.session_state.pop("confirm_reset", None)
            st.success("✓ All memories reset to defaults.")
            st.rerun()
        else:
            st.session_state["confirm_reset"] = True
            st.warning("⚠️ Click again to confirm reset. This cannot be undone.")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_md(result: ReviewResult) -> str:
    s = result.summary
    lines = [
        "# Architecture Review Report",
        f"\n> Model: `{result.model_used}`\n",
        "## Summary\n",
        "| Severity | Count |","|----------|-------|",
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
        cat = f.category.value.upper().replace("_"," ")
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
        lines += ["\n## Recommended ADRs\n"] + [f"{i}. {a}" for i,a in enumerate(result.recommended_adrs,1)]
    return "\n".join(lines)


def _build_adr_zip(adr_result: ADRGenerationResult) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for adr in adr_result.adrs:
            num  = str(adr.number).zfill(4)
            slug = re.sub(r"[\s_]+"  ,"-",re.sub(r"[^\w\s-]","",adr.title.lower())).strip("-")[:60]
            drivers = "\n".join(f"* {d}" for d in adr.decision_drivers) or "* _(not specified)_"
            pos     = "\n".join(f"* {c}" for c in adr.consequences_positive) or "* _(none)_"
            neg     = "\n".join(f"* {c}" for c in adr.consequences_negative) or "* _(none)_"
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
