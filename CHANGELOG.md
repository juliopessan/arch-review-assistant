# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-03-17

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
