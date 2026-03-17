"""Rich terminal output for architecture review results."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from arch_review.models import Finding, ReviewResult, Severity

console = Console()

SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "cyan",
    Severity.INFO: "dim",
}

SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "⚪",
}


def print_review(result: ReviewResult, output_format: str = "terminal") -> None:
    """Print the review result in the chosen format."""
    if output_format == "json":
        console.print_json(result.model_dump_json(indent=2))
        return
    if output_format == "markdown":
        _print_markdown(result)
        return
    _print_terminal(result)


def _print_terminal(result: ReviewResult) -> None:
    s = result.summary

    # Header
    console.print()
    console.print(Panel(
        f"[bold]Architecture Review Report[/bold]\n"
        f"Model: [dim]{result.model_used}[/dim]",
        style="bold blue",
        expand=False,
    ))

    # Summary bar
    summary_text = Text()
    summary_text.append(f"  {SEVERITY_ICONS[Severity.CRITICAL]} Critical: ", style="bold red")
    summary_text.append(f"{s.critical_count}  ")
    summary_text.append(f"{SEVERITY_ICONS[Severity.HIGH]} High: ", style="red")
    summary_text.append(f"{s.high_count}  ")
    summary_text.append(f"{SEVERITY_ICONS[Severity.MEDIUM]} Medium: ", style="yellow")
    summary_text.append(f"{s.medium_count}  ")
    summary_text.append(f"{SEVERITY_ICONS[Severity.LOW]} Low: ", style="cyan")
    summary_text.append(f"{s.low_count}  ")
    summary_text.append(f"{SEVERITY_ICONS[Severity.INFO]} Info: ", style="dim")
    summary_text.append(f"{s.info_count}  ")
    summary_text.append(f"  Total: {s.total_findings}", style="bold")
    console.print(Panel(summary_text, title="Summary", box=box.ROUNDED))

    # Overall assessment
    if s.overall_assessment:
        console.print(Panel(
            s.overall_assessment,
            title="[bold]Overall Assessment[/bold]",
            border_style="blue",
        ))

    # Senior architect opening questions
    if result.senior_architect_questions:
        console.print("\n[bold yellow]Opening Questions for the Architecture Review:[/bold yellow]")
        for i, q in enumerate(result.senior_architect_questions, 1):
            console.print(f"  [yellow]{i}.[/yellow] {q}")

    # Findings
    console.print(f"\n[bold]Findings ({result.summary.total_findings})[/bold]")

    for finding in result.findings:
        _print_finding(finding)

    # Recommended ADRs
    if result.recommended_adrs:
        console.print("\n[bold]Recommended Architecture Decision Records (ADRs)[/bold]")
        for i, adr in enumerate(result.recommended_adrs, 1):
            console.print(f"  [bold cyan]{i}.[/bold cyan] {adr}")

    console.print()


def _print_finding(finding: Finding) -> None:
    color = SEVERITY_COLORS[finding.severity]
    icon = SEVERITY_ICONS[finding.severity]
    category_label = finding.category.value.upper().replace("_", " ")

    title_text = Text()
    title_text.append(f"{icon} [{finding.severity.value.upper()}] ", style=color)
    title_text.append(finding.title, style="bold")
    title_text.append(f"  [{category_label}]", style="dim")

    content = Text()
    content.append(finding.description)

    if finding.affected_components:
        content.append("\n\n[Affected] ", style="bold")
        content.append(", ".join(finding.affected_components), style="italic")

    content.append("\n\n[Recommendation] ", style="bold green")
    content.append(finding.recommendation)

    if finding.questions_to_ask:
        content.append("\n\n[Questions to ask]\n", style="bold yellow")
        for q in finding.questions_to_ask:
            content.append(f"  • {q}\n", style="yellow")

    if finding.references:
        content.append("\n[References] ", style="bold dim")
        content.append(", ".join(finding.references), style="dim")

    console.print(Panel(
        content,
        title=title_text,
        border_style=color,
        expand=True,
    ))


def _print_markdown(result: ReviewResult) -> None:
    """Output as a Markdown report."""
    s = result.summary
    lines = [
        "# Architecture Review Report",
        f"\n> Model: `{result.model_used}`\n",
        "## Summary\n",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 Critical | {s.critical_count} |",
        f"| 🟠 High | {s.high_count} |",
        f"| 🟡 Medium | {s.medium_count} |",
        f"| 🔵 Low | {s.low_count} |",
        f"| ⚪ Info | {s.info_count} |",
        f"| **Total** | **{s.total_findings}** |",
        f"\n## Overall Assessment\n\n{s.overall_assessment}",
    ]

    if result.senior_architect_questions:
        lines.append("\n## Opening Questions\n")
        for q in result.senior_architect_questions:
            lines.append(f"- {q}")

    lines.append("\n## Findings\n")
    for f in result.findings:
        icon = SEVERITY_ICONS[f.severity]
        lines.append(f"\n### {icon} {f.title}")
        lines.append(f"\n**Severity:** {f.severity.value} | **Category:** {f.category.value}\n")
        lines.append(f"{f.description}\n")
        if f.affected_components:
            lines.append(f"**Affected components:** {', '.join(f.affected_components)}\n")
        lines.append(f"**Recommendation:** {f.recommendation}\n")
        if f.questions_to_ask:
            lines.append("**Questions to ask:**")
            for q in f.questions_to_ask:
                lines.append(f"- {q}")
        if f.references:
            lines.append(f"\n**References:** {', '.join(f.references)}")

    if result.recommended_adrs:
        lines.append("\n## Recommended ADRs\n")
        for i, adr in enumerate(result.recommended_adrs, 1):
            lines.append(f"{i}. {adr}")

    console.print("\n".join(lines))
