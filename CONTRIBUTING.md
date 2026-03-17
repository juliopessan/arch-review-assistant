# Contributing to Architecture Review Assistant

Thank you for considering a contribution. This project exists because the community 
makes it better — every bug report, prompt improvement, or new reviewer counts.

## How to contribute

### Report a bug or missing finding
Open an issue with:
- The architecture you submitted (anonymized if needed)
- What you expected the tool to find
- What it actually reported

### Improve a prompt
The core review prompt lives in `src/arch_review/prompts/review.py`. 
If you know of a class of architectural issue the tool consistently misses, 
open a PR improving the prompt with a test case.

### Add a new output format
See `src/arch_review/output/formatter.py`. Add a new branch in `print_review()` 
and a corresponding test.

### Add a new example architecture
Drop a `.md` file in `examples/` with a real (anonymized) architecture. 
These are used in the docs and as test fixtures.

## Development setup

```bash
git clone https://github.com/your-org/arch-review-assistant
cd arch-review-assistant
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:
```bash
pytest
```

Run linting:
```bash
ruff check src/ tests/
mypy src/
```

## Pull request checklist

- [ ] Tests pass (`pytest`)
- [ ] Linting passes (`ruff check`)
- [ ] New features have tests
- [ ] Prompt changes include a before/after example in the PR description
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

## Code of conduct

Be kind. We're all here to build something useful for the architecture community.
