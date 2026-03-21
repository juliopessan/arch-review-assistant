<div align="center">

# 🏗️ arch-review

### AI-Powered Architecture Review Assistant

**7 specialized agents · parallel execution · self-evolving memory · PDF/image upload with OCR**

[![CI](https://github.com/juliopessan/arch-review-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/juliopessan/arch-review-assistant/actions)
[![Security](https://github.com/juliopessan/arch-review-assistant/actions/workflows/security.yml/badge.svg)](https://github.com/juliopessan/arch-review-assistant/actions)
[![Python](https://img.shields.io/pypi/pyversions/arch-review)](https://pypi.org/project/arch-review)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Demo](#web-ui) · [Quick Start](#quick-start) · [How it works](#how-it-works) · [Supported Models](#supported-models) · [Contributing](CONTRIBUTING.md)

</div>

---

## What is arch-review?

**arch-review** submits your architecture to a squad of **7 specialized AI agents** that run in **parallel** — each an expert in a different dimension. They find what a single LLM call misses.

Paste a description, upload a PDF or diagram image, and get back:

- **Severity-ranked findings** with concrete recommendations
- **Questions a principal architect would ask** in a real review
- **Architecture Decision Records (ADRs)** auto-generated from findings
- **Agents that learn** from every review and improve over time
- **Run Time report** — per-agent timing, tokens, cost, and ROI vs. manual review

No boilerplate. No generic advice. Every finding is specific to *your* architecture.

---

## The Squad (9 agents total)

```
                         ┌──────────────────┐
                         │  🎯 Agent Manager │  Phase 0 — analyzes architecture,
                         │                  │  sets priorities, injects focus
                         └────────┬─────────┘
                                  │ delegates (walks desk-to-desk)
       ┌──────────┬───────────────┼───────────────┬──────────┬──────────┬──────────┐
       │          │               │               │          │          │          │
┌──────▼──────┐ ┌─▼────────────┐ ┌▼──────────┐ ┌─▼──────────────┐ ┌───▼──────┐ ┌─▼────────────┐ ┌─▼──────────────────┐
│ 🔐 Security │ │ 🛡️ Reliability│ │ 💰 Cost   │ │ 📡 Observability│ │📈 Scalab.│ │ ⚡ Performance│ │ 🔧 Maintainability  │
│ Auth        │ │ SPOFs        │ │ FinOps    │ │ Logs · Traces  │ │Bottleneck│ │ N+1 · Cache  │ │ Coupling · Debt     │
│ Secrets     │ │ Resilience   │ │ Sizing    │ │ Alerts · SLOs  │ │Stateless │ │ Latency · CDN│ │ Testability         │
│ Compliance  │ │ Failover     │ │ Transfer  │ │ Runbooks       │ │Queues    │ │ Critical path│ │ Deploy complexity   │
└──────┬──────┘ └──────┬───────┘ └────┬──────┘ └───────┬────────┘ └────┬─────┘ └──────┬───────┘ └──────┬─────────────┘
       └────────────────┴─────────────┴────────────────┴───────────────┴──────────────┴────────────────┘
                                                         │ all 7 run in parallel
                                                ┌────────▼────────┐
                                                │  🧠 Synthesizer  │  Deduplicates · root causes
                                                │                 │  re-prioritizes by impact
                                                └────────┬────────┘
                                                         │
                                                ┌────────▼────────┐
                                                │  ReviewResult   │
                                                │  + ADRs + Runs  │
                                                └─────────────────┘
```

The **Agent Manager** (Phase 0) uses smart activation rules — it disables `cost_agent` for on-prem/air-gapped systems, `performance_agent` for non-user-facing batch jobs, etc. — so every review is lean and relevant to the architecture at hand.

Each agent has its own **memory file**. After every review, agents append lessons and patterns — the squad gets sharper with use.

---

## Quick Start

### 1. Install system dependency (required for OCR)

```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt-get install tesseract-ocr

# Windows — https://github.com/UB-Mannheim/tesseract/wiki
```

### 2. Clone and install

```bash
git clone https://github.com/juliopessan/arch-review-assistant
cd arch-review-assistant
pip install -e .
```

### 3. Set your API key

```bash
# Anthropic (default)
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export OPENAI_API_KEY=sk-...

# Google Gemini
export GEMINI_API_KEY=...

# OpenRouter (free Chinese models — no credit card needed)
export OPENROUTER_API_KEY=sk-or-v1-...

# Ollama — no key needed, just run: ollama serve
```

> Keys can also be entered directly in the Web UI sidebar — they are saved for the session and restored on every rerun.

### 4. Run

```bash
# Web UI (recommended)
streamlit run web/app.py

# CLI — single-agent quick review
arch-review review -i architecture.md

# CLI — full 7-agent squad
arch-review squad review -i architecture.md

# CLI — generate ADRs
arch-review adr generate -i architecture.md
```

---

## Web UI

```bash
streamlit run web/app.py
# Opens at http://localhost:8501
```

### Tabs

| Tab | What you get |
|-----|-------------|
| 🔍 **Review** | Upload file or paste architecture → run single-agent or full squad |
| 🤖 **Squad** | Live Squad Office canvas — watch agents work in real time |
| 📋 **Findings** | Severity-ranked cards with recommendations and architect questions |
| 📄 **ADRs** | Auto-generated Architecture Decision Records per finding |
| 📤 **Export** | JSON, Markdown, or ADR zip download |
| 🧠 **Memory** | Agent evolution dashboard, lesson history, memory file viewer, Run Time |

### Squad Office

A **pixel-art animated canvas** where each of the 9 agents is a character at a desk:

- **State machine**: `idle → walk → sit → working → done / error`
- **Agent Manager walks desk-to-desk** delivering tasks before returning to his seat
- **Think-bubbles** with 25 domain-specific funny messages per agent:

| Agent | Example bubbles |
|-------|----------------|
| 🎯 Manager | `"Your problem now!"` · `"Slack: 47 msgs"` · `"Mic drop 🎤"` |
| 🔐 Security | `"Credentials in ENV?!"` · `"We are so hacked"` · `"Zero trust. Even me."` |
| 🛡️ Reliability | `"One AZ?? WHY"` · `"3am incident!"` · `"Chaos monkey: me"` |
| 💰 Cost | `"t3.large for cron?"` · `"Orphan volumes 👻"` · `"AWS called us"` |
| 📡 Observability | `"tail -f /dev/null"` · `"PagerDuty: RIP"` · `"Alert fatigue!"` |
| 📈 Scalability | `"Thundering herd!"` · `"Single DB? Bold."` · `"Stateful... hmm"` |
| ⚡ Performance | `"N+1 query!! 😤"` · `"Cache hit: 0%"` · `"Users left. Bye."` |
| 🔧 Maintainability | `"Friday deploys?!"` · `"Test coverage: 4%"` · `"YOLO deploy: oops"` |
| 🧠 Synthesizer | `"The plot thickens"` · `"TLDR: fix the DB"` · `"Ooh, they overlap!"` |

- **60fps game loop** via `requestAnimationFrame`
- **Sparkle particles** on completion state
- **4-row layout**: Manager → 4 specialists → 3 new agents → Synthesizer
- **Auto-height**: ResizeObserver reports actual canvas height to Streamlit iframe

### Run Time Section (Memory tab)

After every squad review:

| Metric | Details |
|--------|---------|
| Total Time | End-to-end wall clock |
| Manager (Phase 0) | Agent Manager analysis duration |
| Squad (parallel) | Parallel wall-clock for all specialists |
| Synthesizer | Final synthesis duration |
| Tokens Used | Input + output per agent |
| Est. Cost | Dynamic — priced to the selected model |
| ROI | Savings vs. $600 manual review baseline |

Cost is calculated using a model pricing table matched by substring — `gemini-2.5-flash` at $0.30/M, OpenRouter `:free` models at $0.00, etc.

### API Key Persistence

Keys entered in the sidebar are saved in `st.session_state` per provider (`arch_anthropic`, `arch_openrouter`, etc.) and restored to `os.environ` on every rerun. A **"Clear saved keys"** button wipes all stored credentials. For permanent persistence across browser sessions, use `~/.streamlit/secrets.toml`.

### Design System

The UI uses the **Orange DNA design system**:
- Primary: `#F04E37` (orange) · Dark: `#2E2E2E` · Tint: `#FFF3F1`
- Configured via `.streamlit/config.toml` (native Streamlit theming)
- Orange topbar, pill-style tabs, provider badges per model
- `FREE` badge shown for OpenRouter `:free` models

---

## Supported Models

Via [LiteLLM](https://docs.litellm.ai/docs/providers). Model and API key are selected in the sidebar — the sidebar shows a colored provider badge and a `FREE` tag for zero-cost models.

### Anthropic

| Model | Notes |
|-------|-------|
| `claude-sonnet-4-20250514` | Default — best balance |
| `claude-opus-4-20250514` | Highest quality |
| `claude-haiku-4-5-20251001` | Fastest / cheapest |

### Google Gemini *(updated March 2026)*

| Model | Notes |
|-------|-------|
| `gemini/gemini-3.1-pro-preview` | Flagship, state-of-the-art |
| `gemini/gemini-3.1-flash-preview` | Frontier performance, lower cost |
| `gemini/gemini-2.5-pro` | Stable, deep reasoning |
| `gemini/gemini-2.5-flash` | Stable, recommended for high-volume |
| `gemini/gemini-2.5-flash-lite` | Cheapest Google model ($0.10/M input) |

> `gemini-1.5-pro` / `gemini-1.5-flash` are retired — they return 404.

### OpenAI

| Model | Notes |
|-------|-------|
| `gpt-4o` | Strong reasoning |
| `gpt-4o-mini` | Budget option |

### Mistral

| Model | Notes |
|-------|-------|
| `mistral/mistral-large-latest` | European alternative |

### OpenRouter — Chinese Free Models 🆓

Get your key at [openrouter.ai](https://openrouter.ai) — no credit card needed for `:free` models.

**Best for agentic tasks / architecture reasoning:**

| Model | Strengths |
|-------|-----------|
| `openrouter/deepseek/deepseek-chat-v3-0324:free` | SOTA reasoning, 128K ctx |
| `openrouter/deepseek/deepseek-r1-zero:free` | Deep chain-of-thought |
| `openrouter/z-ai/glm-4.5-air:free` | MoE + switchable thinking mode |
| `openrouter/stepfun/step-3.5-flash:free` | 196B MoE, 11B active — very fast |

**Best for vision / OCR (architecture diagram upload):**

| Model | Strengths |
|-------|-----------|
| `openrouter/qwen/qwen2.5-vl-3b-instruct:free` | Native vision + OCR |
| `openrouter/moonshotai/kimi-vl-a3b-thinking:free` | Vision + reasoning |

### Ollama (local)

| Model | Notes |
|-------|-------|
| `ollama/llama3` | No API key, fully offline |
| `ollama/mistral` | No API key, fully offline |

---

## How it works

### Agent Manager (Phase 0)

Before the specialists run, the Manager:
1. Classifies architecture type, complexity, cloud providers, compliance flags
2. Sets per-agent priorities (`critical / high / normal / low`)
3. Writes focus notes referencing actual component names from the description
4. Disables irrelevant agents with a reason logged

### Parallel Execution

7 specialists run via `asyncio.gather()`. Each receives:
- A specialized system prompt for their domain
- The Manager's focus note
- Memory of past lessons from previous reviews
- Squad-level cross-pattern history

### Memory System

```
~/.arch-review/memory/
  manager_agent.md         ← architecture plan patterns
  security_agent.md        ← "Lesson: Always check JWT expiry..."
  reliability_agent.md     ← "Pattern: Shared DBs = hidden SPOF..."
  cost_agent.md
  observability_agent.md
  scalability_agent.md
  performance_agent.md
  maintainability_agent.md
  synthesizer_agent.md
  SQUAD_MEMORY.md          ← cross-agent patterns + review history
```

**Evolution levels:**

| Level | Lessons | Meaning |
|-------|---------|---------|
| 🌱 Fresh | 0 | Default prompts |
| 🟢 Growing | 1–2 | Recognizing your patterns |
| 🔵 Experienced | 3–7 | Calibrated to your stack |
| 🟣 Expert | 8+ | Deeply personalized |

---

## Input Formats

| Format | Example |
|--------|---------|
| Plain text | Component list + flow description |
| Mermaid diagram | `flowchart LR ...` |
| PDF (text layer) | Architecture spec document |
| PDF (scanned) | Photographed whiteboard or diagram |
| Image | `.png`, `.jpg` screenshot |
| Markdown | `architecture.md` from your repo |

See `examples/innomotics-architecture.md` for a real-world SAP Commerce Cloud / Innomotics example extracted from a complex architecture diagram via OCR.

---

## CI/CD Integration

```yaml
# .github/workflows/arch-review.yml
- name: Architecture Review
  run: |
    pip install -e .
    arch-review review -i docs/architecture.md --focus security
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

> `arch-review` exits with code `2` on critical findings — blocks pipelines automatically.

---

## CLI Reference

```
arch-review review        Run a single-agent review
arch-review squad review  Run the 7-agent squad review
arch-review squad memory  View/inspect agent memory files
arch-review history       View local CLI execution history
arch-review adr generate  Generate ADRs from review findings
arch-review models        List all supported LLM models
arch-review example       Print an example architecture
```

---

## Project Structure

```
arch-review-assistant/
├── src/arch_review/
│   ├── engine.py              ← Single-agent review + SUPPORTED_MODELS
│   ├── models.py              ← Pydantic models + _MODEL_PRICING + _model_cost()
│   ├── adr_generator.py       ← ADR generation engine
│   ├── squad/
│   │   ├── squad.py           ← 7-agent parallel orchestrator + RunMetrics
│   │   ├── manager.py         ← Agent Manager (Phase 0) + smart activation rules
│   │   ├── memory.py          ← Per-agent memory system
│   │   └── prompts.py         ← 9 agent system prompts + build_*_prompt functions
│   ├── utils/
│   │   ├── json_parser.py     ← Robust JSON parser (handles OCR + Mermaid output)
│   │   └── extractor.py       ← PDF/image extraction + Tesseract OCR
│   └── output/
│       ├── formatter.py       ← Terminal output formatter
│       └── adr_writer.py      ← MADR file writer
├── web/
│   ├── app.py                 ← Streamlit Web UI (Orange DNA design system)
│   ├── squad_office.py        ← Pixel-art Squad Office canvas (JS/HTML)
│   └── i18n.py                ← EN / PT-BR translations
├── .streamlit/
│   └── config.toml            ← Orange DNA Streamlit theme
├── examples/
│   ├── ecommerce-basic.md
│   └── innomotics-architecture.md
└── tests/                     ← 77 tests
```

---

## Roadmap

- [x] Single-agent review (CLI + Web UI)
- [x] 7-agent squad with parallel execution
- [x] Agent Manager (Phase 0) with smart activation rules
- [x] Self-evolving memory per agent (9 memory files)
- [x] ADR generator (MADR format)
- [x] PDF/image upload with OCR + LLM structuring
- [x] Squad Office pixel-art animated canvas (60fps, state machine, think-bubbles)
- [x] EN / PT-BR bilingual interface
- [x] Run Time — timing, tokens, dynamic cost per model, ROI
- [x] OpenRouter Chinese free models (DeepSeek V3/R1, GLM-4.5, Qwen VL, Kimi VL, StepFun)
- [x] Google Gemini 3.x / 2.5 models (March 2026)
- [x] Persistent API key storage per session
- [x] Orange DNA design system
- [x] Agent-specific think-bubbles (funny, 25 msgs per agent)
- [x] Docker + Railway/Render deploy
- [x] GitHub Actions CI + Security scanning
- [ ] `arch-review diff` — compare two architecture versions
- [ ] PyPI publish — `pip install arch-review`
- [ ] Public demo URL
- [ ] opensquad skill — `/opensquad install arch-review`
- [ ] Slack / Teams bot integration

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — PRs welcome.

```bash
git clone https://github.com/juliopessan/arch-review-assistant
cd arch-review-assistant
pip install -e ".[dev]"
pytest  # 77 tests
```

---

## License

MIT — use it, fork it, build on it.

---

<div align="center">

**If arch-review saved you time in a review, consider giving it a ⭐**

Built by [@juliopessan](https://github.com/juliopessan) · Inspired by [opensquad](https://github.com/renatoasse/opensquad)
by **Orange DNA**

</div>
