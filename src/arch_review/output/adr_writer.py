"""ADR writer — outputs MADR-formatted markdown files to disk."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from arch_review.models_adr import ADR, ADRGenerationResult

console = Console()


MADR_TEMPLATE = """\
# {number_padded}. {title}

Date: {date}

## Status

{status}

## Context and Problem Statement

{context}

## Decision Drivers

{decision_drivers}

## Considered Options

{options_list}

## Decision Outcome

Chosen option: **{chosen_option_title}**

{decision}

### Positive Consequences

{consequences_positive}

### Negative Consequences

{consequences_negative}

{neutral_section}\
{links_section}\
"""


def write_adrs(
    result: ADRGenerationResult,
    output_dir: Path,
    starting_number: int = 1,
) -> list[Path]:
    """Write all ADRs to markdown files in output_dir. Returns list of written paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for i, adr in enumerate(result.adrs):
        # Allow custom starting number for sequencing in existing ADR directories
        adr.number = starting_number + i
        path = _write_adr(adr, output_dir)
        written.append(path)
        console.print(f"  [green]✓[/green] {path.name}")

    return written


def _write_adr(adr: ADR, output_dir: Path) -> Path:
    """Render one ADR to a MADR markdown file."""
    number_padded = str(adr.number).zfill(4)
    slug = _slugify(adr.title)
    filename = f"{number_padded}-{slug}.md"
    path = output_dir / filename

    # Decision drivers
    drivers_md = "\n".join(f"* {d}" for d in adr.decision_drivers) if adr.decision_drivers else "* _(not specified)_"

    # Options list (summary)
    if adr.considered_options:
        options_list = "\n".join(
            f"* [{o.title}](#{_slugify(o.title)})" for o in adr.considered_options
        )
    else:
        options_list = "* _(no alternatives documented)_"

    # First option is the chosen one by convention
    chosen_title = adr.considered_options[0].title if adr.considered_options else "See decision below"

    # Full options detail
    options_detail = _render_options(adr)

    # Consequences
    pos = "\n".join(f"* {c}" for c in adr.consequences_positive) or "* _(none identified)_"
    neg = "\n".join(f"* {c}" for c in adr.consequences_negative) or "* _(none identified)_"

    # Neutral / follow-up
    neutral_section = ""
    if adr.consequences_neutral:
        neutral_md = "\n".join(f"* {c}" for c in adr.consequences_neutral)
        neutral_section = f"### Neutral Consequences / Follow-up Actions\n\n{neutral_md}\n\n"

    # Links
    links_section = ""
    if adr.links:
        links_md = "\n".join(f"* {link}" for link in adr.links)
        links_section = f"## Links\n\n{links_md}\n"

    content = MADR_TEMPLATE.format(
        number_padded=number_padded,
        title=adr.title,
        date=adr.date,
        status=adr.status.value.capitalize(),
        context=adr.context,
        decision_drivers=drivers_md,
        options_list=options_list,
        chosen_option_title=chosen_title,
        decision=adr.decision,
        consequences_positive=pos,
        consequences_negative=neg,
        neutral_section=neutral_section,
        links_section=links_section,
    )

    # Append the full options detail after the template
    content += "\n## Options Detail\n\n" + options_detail

    path.write_text(content, encoding="utf-8")
    return path


def _render_options(adr: ADR) -> str:
    """Render detailed options section."""
    if not adr.considered_options:
        return "_No options documented._\n"

    parts = []
    for opt in adr.considered_options:
        lines = [f"### {opt.title}\n", f"{opt.description}\n"]
        if opt.pros:
            lines.append("**Pros:**\n" + "\n".join(f"* {p}" for p in opt.pros))
        if opt.cons:
            lines.append("\n**Cons:**\n" + "\n".join(f"* {c}" for c in opt.cons))
        parts.append("\n".join(lines))

    return "\n\n---\n\n".join(parts) + "\n"


def print_adr_preview(result: ADRGenerationResult) -> None:
    """Print a terminal preview of generated ADRs."""
    from rich.panel import Panel
    from rich.text import Text

    console.print()
    for adr in result.adrs:
        number_padded = str(adr.number).zfill(4)

        header = Text()
        header.append(f"ADR-{number_padded} ", style="bold cyan")
        header.append(adr.title, style="bold")
        header.append(f"  [{adr.status.value}]", style="dim")

        body = Text()
        body.append("Context\n", style="bold")
        body.append(adr.context + "\n\n")

        if adr.decision_drivers:
            body.append("Decision drivers\n", style="bold")
            for d in adr.decision_drivers:
                body.append(f"  • {d}\n")
            body.append("\n")

        if adr.considered_options:
            body.append("Options considered\n", style="bold")
            for o in adr.considered_options:
                body.append(f"  • {o.title}\n")
            body.append("\n")

        body.append("Decision\n", style="bold green")
        body.append(adr.decision)

        if adr.consequences_negative:
            body.append("\n\nRisks to accept\n", style="bold yellow")
            for c in adr.consequences_negative:
                body.append(f"  • {c}\n", style="yellow")

        console.print(Panel(body, title=header, border_style="cyan"))

    console.print(
        f"\n[bold green]{result.total_generated} ADR(s) generated[/bold green] "
        f"using [cyan]{result.model_used}[/cyan]"
    )


def _slugify(text: str) -> str:
    """Convert title to filename-safe slug."""
    import re
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = text.strip("-")
    return text[:60]  # Keep filenames reasonable
