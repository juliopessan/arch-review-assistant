<div align="center">

# 🏗️ arch-review

### AI-Powered Architecture Review Assistant

**4 specialized agents · parallel execution · self-evolving memory · PDF/image upload with OCR**

[![CI](https://github.com/juliopessan/arch-review-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/juliopessan/arch-review-assistant/actions)
[![Security](https://github.com/juliopessan/arch-review-assistant/actions/workflows/security.yml/badge.svg)](https://github.com/juliopessan/arch-review-assistant/actions)
[![Python](https://img.shields.io/pypi/pyversions/arch-review)](https://pypi.org/project/arch-review)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Demo](#web-ui) · [Quick Start](#quick-start) · [How it works](#how-it-works) · [Contributing](CONTRIBUTING.md)

</div>

---

## What is arch-review?

**arch-review** submits your architecture to a squad of 4 specialized AI agents that run in **parallel** — each an expert in a different dimension. They find what a single LLM call misses.

Paste a description, upload a PDF or diagram image, and get back:

- **Severity-ranked findings** with concrete recommendations
- **Questions a principal architect would ask** in a real review
- **Architecture Decision Records (ADRs)** auto-generated from findings
- **Agents that learn** from every review and improve over time

No boilerplate. No generic advice. Every finding is specific to *your* architecture.

---

## The Squad

```
┌─────────────┐  ┌─────────────────┐  ┌────────────┐  ┌─────────────────┐
│ 🔐 Security │  │ 🛡️ Reliability   │  │ 💰 Cost    │  │ 📡 Observability│
│             │  │                 │  │            │  │                 │
│ Auth        │  │ SPOFs           │  │ FinOps     │  │ Logs            │
│ Secrets     │  │ Resilience      │  │ Sizing     │  │ Metrics         │
│ Compliance  │  │ Failover        │  │ Transfer   │  │ Tracing         │
└──────┬──────┘  └────────┬────────┘  └─────┬──────┘  └───────┬─────────┘
       │                  │                  │                  │
       └──────────────────┴──────────────────┴──────────────────┘
                                    │
                           ┌────────▼────────┐
                           │  🧠 Synthesizer  │
                           │                 │
                           │ Cross-patterns  │
                           │ Root causes     │
                           │ Priority matrix │
                           └────────┬────────┘
                                    │
                           ┌────────▼────────┐
                           │  ReviewResult   │
                           │  + ADRs         │
                           └─────────────────┘
```

Each agent has its own **memory file** (`~/.arch-review/memory/`). After every review, agents append lessons and patterns — the squad gets sharper the more you use it.

---

## Quick Start

### 1. Install system dependency (required)

```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt-get install tesseract-ocr

# Windows
# https://github.com/UB-Mannheim/tesseract/wiki
```

### 2. Install arch-review

```bash
pip install -e "git+https://github.com/juliopessan/arch-review-assistant#egg=arch-review&subdirectory=."
# or clone:
git clone https://github.com/juliopessan/arch-review-assistant
cd arch-review-assistant && pip install -e .
```

### 3. Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Claude (recommended)
export OPENAI_API_KEY=sk-...          # GPT-4o
export GEMINI_API_KEY=...             # Gemini
# Ollama needs no key — just run `ollama serve`
```

### 4. Run

```bash
# Web UI (recommended)
streamlit run web/app.py

# CLI — quick review
arch-review review -i architecture.md

# CLI — full squad
arch-review squad review -i architecture.md

# CLI — generate ADRs
arch-review adr generate -i architecture.md
```

---

## Web UI

The Streamlit interface ships with the project:

- **Upload any file** — `.pdf`, `.png`, `.jpg`, `.md`, `.mmd`, `.txt`
- **OCR extraction** — scanned PDFs and architecture images → structured Markdown
- **Live Squad Office** — watch 4 agents run in real time with status cards
- **EN / PT-BR** — full bilingual UI, switch in one click
- **Funny loading messages** — because waiting shouldn't be boring
- **Export** — JSON (for CI/CD), Markdown (for Confluence/Notion), ADR zip

```bash
streamlit run web/app.py
# Opens at http://localhost:8501
```

### Docker

```bash
docker build -t arch-review .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=sk-ant-... arch-review
```

### Deploy to Railway / Render (free tier)

Fork → connect to [Railway](https://railway.app) or [Render](https://render.com) → set env vars → deploy. The `Procfile` handles the rest.

---

## How it works

### Single Review (quick)
One optimized LLM call with a structured prompt. Returns findings in ~10s.

```bash
arch-review review -i architecture.md --focus security --focus reliability
```

### Squad Review (deep)
4 agents run in parallel via `asyncio.gather()`. Each has:
- A specialized system prompt for their domain
- Memory of past lessons from previous reviews
- Access to squad-level cross-pattern history

The Synthesizer deduplicates, finds root causes, and re-prioritizes by business impact.

```bash
arch-review squad review -i architecture.md
```

### Memory System
After every squad review:

```
~/.arch-review/memory/
  security_agent.md       ← "Lesson [2025-01-15]: Always check JWT expiry..."
  reliability_agent.md    ← "Pattern [2025-01-16]: Shared DBs = hidden SPOF..."
  cost_agent.md
  observability_agent.md
  synthesizer_agent.md
  SQUAD_MEMORY.md         ← cross-agent patterns + review history
```

Lessons inject into every new review — the agents get smarter over time.

**Evolution levels per agent:**

| Level | Lessons | What it means |
|---|---|---|
| 🌱 Fresh | 0 | Default prompts, no personalization |
| 🟢 Growing | 1–2 | Starting to recognize your patterns |
| 🔵 Experienced | 3–7 | Calibrated to your stack and failure modes |
| 🟣 Expert | 8+ | Deeply personalized — misses very little |

The **Evolution Dashboard** in the Memory tab tracks this in real time:
total reviews, lessons learned per agent, cross-patterns discovered, and findings caught across sessions.

### ADR Generation
Findings are converted into Architecture Decision Records following the [MADR](https://adr.github.io/madr/) format:

```bash
arch-review adr generate -i architecture.md -o docs/adr
git add docs/adr && git commit -m "docs: add ADRs from architecture review"
```

---

## Supported Models

Any [LiteLLM](https://docs.litellm.ai/docs/providers)-compatible model:

| Provider | Models |
|---|---|
| **Anthropic** | `claude-sonnet-4-20250514` *(default)*, `claude-opus-4-20250514` |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` |
| **Google** | `gemini/gemini-1.5-pro`, `gemini/gemini-1.5-flash` |
| **Mistral** | `mistral/mistral-large-latest` |
| **Ollama** | `ollama/llama3`, `ollama/mistral` *(local, no key needed)* |

```bash
arch-review review -i arch.md --model gpt-4o
arch-review squad review -i arch.md --model ollama/llama3
```

---

## Input Formats

Anything that describes your architecture:

| Format | Example |
|---|---|
| Plain text | Component list + flow description |
| Mermaid diagram | `flowchart LR ...` |
| PDF (text layer) | Architecture spec document |
| PDF (scanned) | Photographed whiteboard diagram |
| Image | `.png`, `.jpg` architecture screenshot |
| Markdown | `architecture.md` from your repo |

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

> `arch-review` exits with code `2` when critical findings are found — blocks the pipeline automatically.

---

## CLI Reference

```
arch-review review        Run a single-agent review
arch-review squad review  Run the 4-agent squad review
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
│   ├── engine.py           ← Single-agent review engine
│   ├── models.py           ← Pydantic data models
│   ├── adr_generator.py    ← ADR generation engine
│   ├── squad/
│   │   ├── squad.py        ← 4-agent parallel orchestrator
│   │   ├── memory.py       ← Agent memory system
│   │   └── prompts.py      ← Specialized agent prompts
│   ├── utils/
│   │   ├── json_parser.py  ← Robust JSON parser (handles OCR output)
│   │   └── extractor.py    ← PDF/image text extraction + OCR
│   └── output/
│       ├── formatter.py    ← Terminal output
│       └── adr_writer.py   ← MADR file writer
├── web/
│   ├── app.py              ← Streamlit Web UI
│   └── i18n.py             ← EN/PT-BR translations
├── tests/                  ← 68 tests
├── examples/               ← Sample architecture files
└── docs/                   ← Publishing guide
```

---

## Roadmap

- [x] Single-agent review (CLI + Web UI)
- [x] 4-agent squad with parallel execution
- [x] Self-evolving memory system per agent
- [x] ADR generator (MADR format)
- [x] PDF/image upload with OCR
- [x] LLM-structured OCR output
- [x] Streamlit Web UI with Squad Office
- [x] EN / PT-BR bilingual interface
- [x] Docker + Railway/Render deploy
- [x] GitHub Actions CI + Security scanning
- [ ] `arch-review diff` — compare two architecture versions
- [ ] opensquad skill — `/opensquad install arch-review`
- [ ] PyPI publish — `pip install arch-review`
- [ ] Mermaid diagram parser (component-level findings)
- [ ] Slack / Teams bot integration

---

## Contributing

Found a finding the squad missed? Improved a prompt? Added a new language?

See [CONTRIBUTING.md](CONTRIBUTING.md) — PRs are welcome and issues are responded to fast.

```bash
git clone https://github.com/juliopessan/arch-review-assistant
cd arch-review-assistant
pip install -e ".[dev]"
pytest  # 68 tests
```

---

## License

MIT — use it, fork it, build on it.

---

<div align="center">

**If arch-review saved you time in a review, consider giving it a ⭐**

Built by [@juliopessan](https://github.com/juliopessan) · Inspired by [opensquad](https://github.com/renatoasse/opensquad)

</div>
