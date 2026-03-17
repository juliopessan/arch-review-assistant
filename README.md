# arch-review — Architecture Review Assistant

> AI-powered architecture reviews that think like a principal engineer.

[![CI](https://github.com/your-org/arch-review-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/arch-review-assistant/actions)
[![PyPI](https://img.shields.io/pypi/v/arch-review)](https://pypi.org/project/arch-review)
[![Python](https://img.shields.io/pypi/pyversions/arch-review)](https://pypi.org/project/arch-review)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

**arch-review** submits your architecture description to an LLM trained to think like a 
principal architect. It returns structured findings — ranked by severity — covering security gaps, 
reliability risks, missing observability, undocumented trade-offs, and more.

Unlike generic AI chats, every finding is specific to your architecture, includes a concrete 
recommendation, and comes with the questions a senior architect would ask in a real review.

---

## Quick start

```bash
pip install arch-review

# Set your provider key (example: Anthropic)
export ANTHROPIC_API_KEY=sk-ant-...

# Review an architecture file
arch-review review -i my-architecture.md

# Or pipe from stdin
cat architecture.txt | arch-review review --stdin

# Focus on security and reliability only
arch-review review -i arch.md --focus security --focus reliability

# Use a different model (OpenAI, Mistral, Ollama...)
arch-review review -i arch.md --model gpt-4o

# Export as Markdown report
arch-review review -i arch.md -o markdown --output-file review.md

# See a sample architecture to try
arch-review example
```

---

## What it finds

| Category | Examples |
|---|---|
| **Security** | Missing auth, exposed secrets, no rate limiting, no WAF |
| **Reliability** | SPOFs, no multi-AZ, no circuit breakers, shared databases |
| **Scalability** | Synchronous chains, no caching, database bottlenecks |
| **Observability** | Missing tracing, no alerting, local log files |
| **Missing ADRs** | Undocumented technology choices and trade-offs |
| **Cost** | Over-provisioned instances, missing auto-scaling |
| **Maintainability** | Coupling, missing contracts, monolithic deployments |

---

## Supported models

```
arch-review models
```

Works with any provider supported by [LiteLLM](https://docs.litellm.ai/docs/providers):

| Provider | Example models |
|---|---|
| Anthropic | `claude-sonnet-4-20250514` (default), `claude-opus-4-20250514` |
| OpenAI | `gpt-4o`, `gpt-4o-mini` |
| Google | `gemini/gemini-1.5-pro` |
| Mistral | `mistral/mistral-large-latest` |
| Ollama (local) | `ollama/llama3`, `ollama/mistral` |

Set the appropriate API key as an environment variable before running:

```bash
export ANTHROPIC_API_KEY=...   # Anthropic
export OPENAI_API_KEY=...      # OpenAI
export GEMINI_API_KEY=...      # Google
# Ollama needs no key — just run ollama serve locally
```

---

## Input formats

arch-review accepts any text format that describes your architecture:

- **Plain text** — prose description of components and flows
- **Mermaid diagrams** — paste your `.mmd` file directly
- **Structured markdown** — component lists, flow descriptions, infrastructure notes
- **JSON** — machine-generated architecture specs

The richer the description, the better the findings. Include:
- Component names and their responsibilities
- Communication patterns (sync vs async, protocols)
- Data stores and their access patterns
- Infrastructure details (cloud provider, regions, instance types)
- Business context and constraints

---

## Output formats

### Terminal (default)
Color-coded findings with severity icons, recommendations, and questions — 
optimized for reading in a real review session.

### Markdown (`-o markdown`)
Clean report suitable for Confluence, Notion, or GitHub wikis.

### JSON (`-o json`)
Machine-readable output for integration into CI/CD pipelines:

```bash
# Fail the pipeline if critical findings are found
arch-review review -i arch.md -o json | jq '.summary.critical_count'
```

> arch-review exits with code `2` when critical findings are found — 
> useful for blocking deployments.

---

## Use in CI/CD

```yaml
# .github/workflows/arch-review.yml
- name: Architecture Review
  run: |
    pip install arch-review
    arch-review review -i docs/architecture.md --focus security --focus reliability
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

---

## Python API

```python
from arch_review.engine import ReviewEngine
from arch_review.models import ArchitectureInput, FindingCategory

engine = ReviewEngine(model="claude-sonnet-4-20250514")

result = engine.review(ArchitectureInput(
    description=open("architecture.md").read(),
    context="LGPD compliance required. Single-cloud Azure.",
    focus_areas=[FindingCategory.SECURITY, FindingCategory.RELIABILITY],
))

for finding in result.findings:
    print(f"[{finding.severity.value.upper()}] {finding.title}")
    print(f"  → {finding.recommendation}\n")
```

---

## Development

```bash
git clone https://github.com/your-org/arch-review-assistant
cd arch-review-assistant
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add prompts, output formats, or examples.

---

## Roadmap

- [ ] ADR generator from findings (`arch-review adr generate`)
- [ ] Mermaid diagram parser for more precise component-level findings
- [ ] Compare two architecture versions (`arch-review diff`)
- [ ] OWASP Top 10 specialized reviewer
- [ ] Web UI for team reviews
- [ ] Slack / Teams bot integration

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built for architects who are tired of inconsistent reviews and forgotten trade-offs.*
