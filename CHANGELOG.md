# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] — 2026-03-18

### Added
- `ReviewSquad` — 4 specialized agents running in parallel via `asyncio`
  - `SecurityAgent` — OWASP, auth, secrets, compliance, attack vectors
  - `ReliabilityAgent` — SPOFs, resilience, cascading failures, RTO/RPO
  - `CostAgent` — FinOps, right-sizing, data transfer, scaling economics
  - `ObservabilityAgent` — logs, metrics, tracing, alerting, incident readiness
  - `SynthesizerAgent` — deduplication, root cause grouping, cross-pattern detection
- Memory & continuous evolution system
  - Each agent has an `AGENT.md` file that persists lessons across reviews
  - `SQUAD_MEMORY.md` tracks cross-agent patterns and review history
  - Memories stored in `~/.arch-review/memory/` by default
  - Agents inject past lessons into every new review prompt
- `arch-review squad review` CLI command
- `arch-review squad memory` — view, inspect, and reset agent memory files
- 22 new tests covering memory system and squad orchestration (53 total)
- Graceful degradation: squad continues if individual agents fail

## [0.3.0] — 2026-03-17

### Added
- Streamlit Web UI (`web/app.py`) — full review + ADR + export in browser
- Model selector, API key input, focus area filter in sidebar
- Severity-coded findings with recommendations and architect questions
- ADR viewer with expandable options, pros/cons, consequences
- Export as JSON, Markdown report, or ADR zip
- Dockerfile for containerized deploy
- Procfile for Railway / Render one-click deploy
- `.streamlit/config.toml` with brand theme
- `requirements.txt` for PaaS platforms

### Added
- `arch-review adr generate` — generates MADR-formatted ADRs from review findings
- `ADRGenerator` engine with LiteLLM multi-provider support
- `ADRWriter` — outputs numbered `.md` files following MADR format
- `--preview` flag for terminal preview without writing files
- `--from-review` flag to generate ADRs from a previous JSON review output
- `--start-number` flag for sequencing into existing ADR directories
- 16 new tests covering ADR models, generator, and writer (31 total)

## [0.1.0] — 2025-01-01

### Added
- Initial release
- CLI with `review`, `models`, and `example` commands
- Multi-provider LLM support via LiteLLM (Anthropic, OpenAI, Google, Mistral, Ollama)
- Structured finding output (severity, category, recommendations, questions)
- Terminal, Markdown, and JSON output formats
- Senior architect opening questions
- Recommended ADR generation
- Example architectures (e-commerce, HR SaaS)
- GitHub Actions CI (Python 3.10 / 3.11 / 3.12)
