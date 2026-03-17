"""CLI entry point for Architecture Review Assistant."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from arch_review import __version__
from arch_review.engine import DEFAULT_MODEL, SUPPORTED_MODELS, ReviewEngine
from arch_review.models import ArchitectureInput, FindingCategory
from arch_review.output import print_review

console = Console()
err_console = Console(stderr=True)


def _list_models() -> str:
    lines = ["\nSupported models:\n"]
    for model, provider in SUPPORTED_MODELS.items():
        lines.append(f"  [{provider}] {model}")
    return "\n".join(lines)


@click.group()
@click.version_option(version=__version__, prog_name="arch-review")
def main() -> None:
    """Architecture Review Assistant — AI-powered architecture reviews.

    Run 'arch-review review --help' to get started.
    """


@main.command()
@click.option(
    "--input", "-i",
    "input_source",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to architecture file (text, Mermaid .mmd, or JSON).",
)
@click.option(
    "--stdin",
    is_flag=True,
    default=False,
    help="Read architecture description from stdin.",
)
@click.option(
    "--context", "-c",
    default=None,
    help="Business context, constraints, or goals (inline string).",
)
@click.option(
    "--context-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to context file.",
)
@click.option(
    "--model", "-m",
    default=DEFAULT_MODEL,
    show_default=True,
    help="LLM model to use. Run 'arch-review models' to list all options.",
)
@click.option(
    "--focus",
    multiple=True,
    type=click.Choice([c.value for c in FindingCategory]),
    help="Focus the review on specific categories (can be used multiple times).",
)
@click.option(
    "--output", "-o",
    type=click.Choice(["terminal", "markdown", "json"]),
    default="terminal",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Save output to file instead of stdout.",
)
@click.option(
    "--temperature",
    type=float,
    default=0.2,
    show_default=True,
    help="LLM temperature (0.0–1.0). Lower = more consistent.",
)
def review(
    input_source: Path | None,
    stdin: bool,
    context: str | None,
    context_file: Path | None,
    model: str,
    focus: tuple[str, ...],
    output: str,
    output_file: Path | None,
    temperature: float,
) -> None:
    """Run an architecture review.

    \b
    Examples:
      arch-review review -i architecture.md
      arch-review review -i system.mmd --focus security --focus scalability
      arch-review review --stdin < architecture.txt
      arch-review review -i arch.md -o markdown --output-file review.md
      arch-review review -i arch.md --model gpt-4o -o json
    """
    # --- Gather architecture description ---
    architecture_text = ""

    if stdin or (not input_source and not sys.stdin.isatty()):
        architecture_text = click.get_text_stream("stdin").read().strip()
    elif input_source:
        architecture_text = input_source.read_text(encoding="utf-8").strip()
    else:
        # Interactive fallback: open $EDITOR or prompt
        architecture_text = click.edit(
            "# Paste your architecture description here\n# Lines starting with # are ignored\n"
        ) or ""
        architecture_text = "\n".join(
            line for line in architecture_text.splitlines()
            if not line.startswith("#")
        ).strip()

    if not architecture_text:
        err_console.print("[red]Error:[/red] No architecture description provided.")
        raise click.Abort()

    # --- Gather context ---
    full_context = context or ""
    if context_file:
        full_context = context_file.read_text(encoding="utf-8").strip()

    # --- Build input model ---
    focus_categories = [FindingCategory(f) for f in focus]
    arch_input = ArchitectureInput(
        description=architecture_text,
        context=full_context or None,
        focus_areas=focus_categories,
    )

    # --- Run review ---
    console.print(f"\n[bold blue]Running architecture review[/bold blue] with [cyan]{model}[/cyan]...")

    engine = ReviewEngine(model=model, temperature=temperature)

    try:
        result = engine.review(arch_input)
    except ValueError as exc:
        err_console.print(f"[red]Review failed:[/red] {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:
        err_console.print(f"[red]Unexpected error:[/red] {exc}")
        raise SystemExit(1) from exc

    # --- Output ---
    if output_file:
        # Redirect console output to file
        from rich.console import Console as RichConsole
        RichConsole(file=output_file.open("w", encoding="utf-8"), highlight=False)
        # Re-use formatter but write to file
        if output == "json":
            output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        else:
            print_review(result, output_format=output)
        console.print(f"\n[green]Report saved to:[/green] {output_file}")
    else:
        print_review(result, output_format=output)

    # Exit with non-zero if critical findings
    if result.summary.critical_count > 0:
        raise SystemExit(2)


@main.command()
def models() -> None:
    """List all supported LLM models."""
    console.print(_list_models())


@main.command()
def example() -> None:
    """Print an example architecture description to use as input."""
    example_arch = """
# E-commerce Order Processing System

## Components
- **API Gateway**: Single entry point, handles auth via JWT
- **Order Service**: Accepts orders, validates inventory, publishes to RabbitMQ
- **Inventory Service**: Manages stock, reads from a single PostgreSQL instance
- **Payment Service**: Calls Stripe API synchronously during order flow
- **Notification Service**: Listens to RabbitMQ, sends email via SMTP
- **Database**: Single PostgreSQL instance shared between Order and Inventory services

## Flow
1. Client → API Gateway → Order Service
2. Order Service validates inventory (sync call to Inventory Service)
3. Order Service charges payment (sync call to Payment Service → Stripe)
4. Order Service publishes OrderPlaced event to RabbitMQ
5. Notification Service consumes event, sends confirmation email

## Infrastructure
- All services deployed on a single EC2 instance (t3.medium)
- No CDN, no caching layer
- Logs written to local files
- RabbitMQ also on same EC2 instance
- No staging environment
""".strip()
    console.print(example_arch)
